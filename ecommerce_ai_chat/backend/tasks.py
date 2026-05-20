"""
视频处理全流水线 Celery 任务

Layer 1  上传接收        (main.py 侧完成)
Layer 2  Celery 异步处理  (本文件)
Layer 3  FFmpeg 拆解视频  stage_extract_audio
Layer 4  Whisper 识别字幕 stage_transcribe
Layer 5  GPT 分析卖点     stage_analyze_frames + stage_generate_overlay
Layer 6  FFmpeg 自动剪辑  stage_auto_edit  (保留完整视频，可后续扩展剪辑规则)
Layer 7  自动加字幕        stage_render_overlays (MoviePy 烧录)
Layer 8  自动加 BGM        stage_mix_bgm
Layer 9  导出宣传片        输出到 outputs/ 目录

启动 worker (Windows):
  cd ecommerce_ai_chat/backend
  venv\\Scripts\\celery -A tasks worker --loglevel=info --pool=threads -c 2
"""
import os, json, base64, shutil, subprocess, glob, tempfile
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

os.environ.setdefault("HTTP_PROXY",  "http://127.0.0.1:7890")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")

from openai import OpenAI
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from celery_app import celery_app

# ── DB (mirrors main.py schema, same SQLite file) ─────────────
_DB_FILE = os.path.join(os.path.dirname(__file__), "ecommerce_chat.db")
_engine  = create_engine(f"sqlite:///{_DB_FILE}", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)
_Base    = declarative_base()

class VideoJob(_Base):
    __tablename__ = "video_jobs"
    id             = Column(String(36), primary_key=True)
    user_id        = Column(Integer, nullable=False, index=True)
    status         = Column(String(20),  default="pending")
    stage          = Column(String(80),  default="")
    progress       = Column(Integer,     default=0)
    error_msg      = Column(Text,        default="")
    input_path     = Column(String(500), default="")
    output_path    = Column(String(500), default="")
    transcript     = Column(Text,        default="")
    marketing_copy = Column(Text,        default="")
    overlay_json   = Column(Text,        default="{}")
    srt_content    = Column(Text,        default="")
    created_at     = Column(DateTime,    default=datetime.utcnow)
    updated_at     = Column(DateTime,    default=datetime.utcnow)

_Base.metadata.create_all(bind=_engine)

def _update_job(job_id: str, **kwargs):
    db = _Session()
    try:
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()

# ── FFmpeg discovery ───────────────────────────────────────────
def _find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    patterns = [
        r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe",
        r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            return sorted(matches)[-1]
    return "ffmpeg"

FFMPEG = _find_ffmpeg()

def _run_ffmpeg(*args, timeout=600):
    cmd = [FFMPEG, "-y", "-loglevel", "error"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 失败: {(result.stderr or result.stdout)[-600:]}")
    return result

# ── OpenAI client ─────────────────────────────────────────────
gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Pipeline stage functions ───────────────────────────────────

def stage_extract_audio(input_path: str, work_dir: str) -> str:
    """Layer 3 — FFmpeg 拆解视频，提取 16kHz 单声道 WAV 供 Whisper 使用。"""
    audio_path = os.path.join(work_dir, "audio.wav")
    _run_ffmpeg(
        "-i", input_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
    )
    return audio_path


def stage_transcribe(audio_path: str) -> dict:
    """Layer 4 — OpenAI Whisper 识别字幕，返回 {text, segments}。"""
    with open(audio_path, "rb") as f:
        resp = gpt_client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    segments = [
        {"text": seg.text.strip(), "start": float(seg.start), "end": float(seg.end)}
        for seg in (resp.segments or [])
        if seg.text.strip()
    ]
    return {"text": resp.text.strip(), "segments": segments}


def stage_analyze_frames(input_path: str) -> str:
    """Layer 5a — 场景变化关键帧提取（优先），GPT-4o 分析画面卖点。"""
    from PIL import Image
    import io as _io

    frames = []

    # 优先：FFmpeg 场景变化检测，提取真正有内容切换的帧
    with tempfile.TemporaryDirectory() as tmp_dir:
        frame_pat = os.path.join(tmp_dir, "scene_%04d.jpg")
        try:
            _run_ffmpeg(
                "-i", input_path,
                "-vf", "select='gt(scene,0.40)',scale=720:-1",
                "-vsync", "vfr",
                "-q:v", "3",
                frame_pat,
                timeout=60,
            )
            scene_files = sorted(glob.glob(os.path.join(tmp_dir, "scene_*.jpg")))
            # 超过 12 帧时均匀抽取
            if len(scene_files) > 12:
                step = len(scene_files) / 12
                scene_files = [scene_files[int(i * step)] for i in range(12)]
            for fp in scene_files:
                with open(fp, "rb") as fh:
                    frames.append(base64.b64encode(fh.read()).decode())
        except Exception:
            pass

    # 降级：场景帧不足 4 帧时，用均匀采样补足
    if len(frames) < 4:
        frames = []
        from moviepy import VideoFileClip
        clip     = VideoFileClip(input_path)
        duration = clip.duration
        n        = min(12, max(4, int(duration * 1.2)))
        times    = [duration * i / n for i in range(n)]
        for t in times:
            try:
                import numpy as np
                arr = clip.get_frame(t)
                img = Image.fromarray(arr)
                mx  = max(img.width, img.height)
                if mx > 720:
                    r   = 720 / mx
                    img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
                buf = _io.BytesIO()
                img.save(buf, format="JPEG", quality=78)
                frames.append(base64.b64encode(buf.getvalue()).decode())
            except Exception:
                continue
        clip.close()

    if not frames:
        return "[帧提取失败，跳过视觉分析]"

    PROMPT = (
        "你是电商视频分析专家。分析这些视频关键场景帧，提取：产品类型、视觉特征与色调、"
        "具体可量化的产品参数与卖点（如材质/尺寸/颜色/功能细节）、目标受众、场景氛围。"
        "输出连贯中文分析，150~250字，尽量包含具体数字和参数。"
    )
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}}
        for b64 in frames
    ]
    content.append({"type": "text", "text": PROMPT})
    resp = gpt_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=800,
    )
    return resp.choices[0].message.content.strip()


def stage_generate_overlay(transcript_text: str, analysis: str) -> dict:
    """Layer 5b — GPT-4o 综合转录与视觉分析，生成营销文案 + 叠加层数据。"""
    PROMPT = """你是电商视频营销专家。结合视频画面分析和语音转录，生成以下JSON（不含markdown代码块）：
{
  "headline": "主标题（8-14字，必须含具体数字或核心参数，如：20000mAh超薄充电宝 重量仅180g）",
  "features": [
    "卖点1（必须含数字/材质/规格，如：航空铝合金机身 耐磨防刮）",
    "卖点2（必须含具体参数，如：IPX7防水 1米深水30分钟无忧）",
    "卖点3（必须含可量化指标）",
    "卖点4（必须含可量化指标）"
  ],
  "cta": "行动号召（4-10字）",
  "marketing_copy": "完整营销文案（抖音/小红书风格，100-150字，结尾含3-5个话题标签）"
}
重要规则：
1. features 每条必须包含具体数字、材质名称、规格参数或可量化对比，禁止使用"超强""完美""极致""高品质"等空洞形容词
2. headline 突出最有说服力的核心数字卖点
3. 所有数据只能来自视频画面或语音转录中已提及的信息，不得编造"""
    user_msg = f"【视频画面分析】\n{analysis}\n\n【语音转录】\n{transcript_text or '（无语音）'}"
    resp = gpt_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user",   "content": user_msg},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return {"headline": "", "features": [], "cta": "", "marketing_copy": ""}


def stage_auto_edit(input_path: str, work_dir: str) -> str:
    """Layer 6 — FFmpeg 自动剪辑（当前保留完整视频；可扩展去静音/高光片段）。"""
    out = os.path.join(work_dir, "edited.mp4")
    # 重新封装，确保时间戳干净，便于后续滤镜处理
    _run_ffmpeg(
        "-i", input_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        out,
    )
    return out


def stage_render_overlays(input_path: str, overlay: dict, segments: list, work_dir: str) -> str:
    """Layer 7 — MoviePy + PIL 烧录：主标题、卖点标签、字幕、CTA。"""
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    out_path = os.path.join(work_dir, "with_overlays.mp4")
    clip     = VideoFileClip(input_path)
    vw, vh   = int(clip.w), int(clip.h)
    duration = clip.duration

    def _font(size: int):
        for fp in [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _render(text: str, fs: int, fg, bg, alpha, pad=14):
        font = _font(fs)
        bb   = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        iw = min(tw + pad * 2, int(vw * 0.88))
        ih = th + pad * 2
        img  = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([(0,0),(iw-1,ih-1)], radius=min(ih//3,18), fill=(*bg, int(255*alpha)))
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            draw.text((pad+dx, pad+dy), text, font=font, fill=(0,0,0,180))
        draw.text((pad, pad), text, font=font, fill=(*fg, 255))
        arr = np.array(img)
        return arr[:,:,:3], arr[:,:,3].astype(float) / 255.0

    def _clip(text, fs, fg, bg, alpha, t0, dur, x, y):
        rgb, mask = _render(text, fs, fg, bg, alpha)
        fh, fw = rgb.shape[0], rgb.shape[1]
        cx = int(vw/2 - fw/2) if x == "center" else max(0, min(int(x), vw-fw))
        cy = max(0, min(int(y), vh-fh))
        ic = ImageClip(rgb,  duration=dur).with_start(t0)
        mc = ImageClip(mask, is_mask=True, duration=dur).with_start(t0)
        return ic.with_mask(mc).with_position((cx, cy))

    all_clips = [clip]

    # ── Headline ──
    headline = (overlay.get("headline") or "").strip()
    if headline:
        hl_dur = min(4.0, duration * 0.30)
        try:
            all_clips.append(_clip(
                headline, max(28, vh//18), (255,255,255), (15,23,42), 0.80,
                0, hl_dur, "center", int(vh*0.06),
            ))
        except Exception:
            pass

    # ── Features（顺序出现，每个卖点独占时间槽，不重叠，淡入淡出）──
    features = [str(f).strip() for f in (overlay.get("features") or []) if str(f).strip()]
    if features:
        fs   = max(22, vh // 24)
        n    = len(features)
        FADE = 0.25
        # 片头标题占用区段 & CTA 占用区段，中间留给卖点
        hl_end  = min(4.0, duration * 0.30)
        cta_dur = min(4.0, duration * 0.25)
        cta_s   = max(hl_end + 1.0, duration - cta_dur)
        avail   = max(1.0, cta_s - hl_end)
        slot    = avail / n
        for i, feat in enumerate(features):
            t_s = hl_end + i * slot
            dur = max(FADE * 2 + 0.5, slot - 0.15)
            t_s = min(t_s, duration - dur - 0.1)
            if t_s < 0:
                continue
            x = int(vw * 0.04) if i % 2 == 0 else int(vw * 0.52)
            y = min(int(vh * 0.32) + (i % 3) * max(int(vh * 0.09), 1), vh - int(vh * 0.22))
            try:
                ic = _clip(feat, fs, (255, 255, 255), (249, 115, 22), 0.90, t_s, dur, x, y)
                try:
                    from moviepy import vfx
                    ic = ic.with_effects([vfx.FadeIn(FADE), vfx.FadeOut(FADE)])
                except Exception:
                    pass
                all_clips.append(ic)
            except Exception:
                continue

    # ── Subtitles ──
    sub_fs = max(20, vh//22)
    for seg in segments:
        txt = seg["text"].strip()
        if not txt or seg["end"] <= seg["start"]:
            continue
        try:
            rgb, mask = _render(txt, sub_fs, (255,255,255), (0,0,0), 0.65)
            fh  = rgb.shape[0]
            dur = seg["end"] - seg["start"]
            ic  = ImageClip(rgb,  duration=dur).with_start(seg["start"])
            mc  = ImageClip(mask, is_mask=True, duration=dur).with_start(seg["start"])
            all_clips.append(ic.with_mask(mc).with_position(("center", vh - fh - int(vh*0.06))))
        except Exception:
            continue

    # ── CTA ──
    cta = (overlay.get("cta") or "").strip()
    if cta:
        cta_dur = min(4.0, duration * 0.25)
        cta_s   = max(0.0, duration - cta_dur)
        cta_fs  = max(26, vh//17)
        try:
            rgb, _ = _render(cta, cta_fs, (255,255,255), (220,38,38), 0.92)
            fh_cta = rgb.shape[0]
            y_sub  = vh - sub_fs - int(vh*0.06)
            cta_y  = y_sub - fh_cta - int(vh*0.025)
            all_clips.append(_clip(cta, cta_fs, (255,255,255), (220,38,38), 0.92, cta_s, cta_dur, "center", cta_y))
        except Exception:
            pass

    final = CompositeVideoClip(all_clips, size=(vw, vh))
    final.write_videofile(out_path, codec="libx264", audio_codec="aac", logger=None, threads=2)
    clip.close()
    final.close()
    return out_path


def stage_mix_bgm(video_path: str, work_dir: str) -> str:
    """Layer 8 — FFmpeg 混入 BGM（assets/bgm.mp3 存在时生效）。"""
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    bgm_candidates = [
        os.path.join(assets_dir, "bgm.mp3"),
        os.path.join(assets_dir, "bgm.wav"),
        os.path.join(assets_dir, "bgm.m4a"),
    ]
    bgm_path = next((p for p in bgm_candidates if os.path.exists(p)), None)
    if not bgm_path:
        return video_path  # 无 BGM 文件则跳过

    out_path = os.path.join(work_dir, "with_bgm.mp4")
    try:
        _run_ffmpeg(
            "-i", video_path,
            "-i", bgm_path,
            "-filter_complex",
            "[0:a]volume=0.80[orig];"
            "[1:a]volume=0.20,aloop=loop=-1:size=2000000000[bgm];"
            "[orig][bgm]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            out_path,
        )
        return out_path
    except Exception:
        return video_path  # 失败时回退到无 BGM 版本


def _build_srt(segments: list) -> str:
    def _ts(s):
        h, r = divmod(int(s), 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d},{int((s%1)*1000):03d}"
    parts = []
    for i, seg in enumerate(segments, 1):
        parts.append(f"{i}\n{_ts(seg['start'])} --> {_ts(seg['end'])}\n{seg['text']}\n")
    return "\n".join(parts)


# ── Main Celery task ───────────────────────────────────────────

@celery_app.task(bind=True, max_retries=0)
def process_video(self, job_id: str, input_path: str):
    """
    Layer 2 — Celery 异步处理，串联 Layer 3-9 全流水线。
    进度 0-100 实时写入 SQLite，前端轮询 /api/pipeline/job/{id} 显示。
    """
    work_dir = tempfile.mkdtemp(prefix=f"vp_{job_id[:8]}_")

    try:
        # Layer 3: FFmpeg 拆解音频
        _update_job(job_id, status="processing", stage="FFmpeg 拆解音频轨道", progress=8)
        audio_path = stage_extract_audio(input_path, work_dir)

        # Layer 4: Whisper 字幕识别
        _update_job(job_id, stage="Whisper 识别语音字幕", progress=22)
        try:
            transcript_data = stage_transcribe(audio_path)
        except Exception:
            transcript_data = {"text": "", "segments": []}
        srt_content = _build_srt(transcript_data["segments"])

        # Layer 5: GPT 分析卖点
        _update_job(job_id, stage="GPT-4o 分析视频卖点", progress=40)
        analysis = stage_analyze_frames(input_path)

        _update_job(job_id, stage="GPT-4o 生成营销文案", progress=60)
        overlay_full  = stage_generate_overlay(transcript_data["text"], analysis)
        marketing_copy = overlay_full.pop("marketing_copy", "")
        overlay       = overlay_full  # headline / features / cta

        # Layer 6: FFmpeg 自动剪辑（重新封装）
        _update_job(job_id, stage="FFmpeg 自动剪辑重封装", progress=70)
        edited_path = stage_auto_edit(input_path, work_dir)

        # Layer 7: 自动加字幕（MoviePy 烧录）
        _update_job(job_id, stage="自动烧录字幕与文字叠加", progress=80)
        overlaid_path = stage_render_overlays(edited_path, overlay, transcript_data["segments"], work_dir)

        # Layer 8: 自动加 BGM
        _update_job(job_id, stage="FFmpeg 混入背景音乐", progress=93)
        final_tmp = stage_mix_bgm(overlaid_path, work_dir)

        # Layer 9: 导出宣传片
        _update_job(job_id, stage="导出宣传片", progress=98)
        outputs_dir = os.path.join(os.path.dirname(__file__), "outputs")
        os.makedirs(outputs_dir, exist_ok=True)
        suffix   = Path(input_path).suffix or ".mp4"
        out_file = os.path.join(outputs_dir, f"{job_id}{suffix}")
        shutil.copy2(final_tmp, out_file)

        _update_job(
            job_id,
            status="completed",
            stage="完成",
            progress=100,
            output_path=out_file,
            transcript=transcript_data["text"],
            marketing_copy=marketing_copy,
            overlay_json=json.dumps(overlay, ensure_ascii=False),
            srt_content=srt_content,
        )

    except Exception as exc:
        _update_job(job_id, status="failed", stage="处理失败", error_msg=str(exc)[:1000])
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
