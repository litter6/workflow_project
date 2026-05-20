from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
import os, base64, io, json, asyncio, functools, tempfile, subprocess, uuid
from typing import Optional, List
from pathlib import Path

# 视频分析会话暂存：session_id → 临时文件路径（跨两次请求共享视频文件）
_video_sessions: dict = {}
from dotenv import load_dotenv
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
from jose import JWTError, jwt

load_dotenv()

os.environ["HTTP_PROXY"]  = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_executor = ThreadPoolExecutor(max_workers=8)

async def run_sync(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, functools.partial(fn, *args, **kwargs))

gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com",
)

# ── Database ──────────────────────────────────────────────

DATABASE_URL = "sqlite:///./ecommerce_chat.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id           = Column(Integer, primary_key=True, index=True)
    username     = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, nullable=False, index=True)
    title         = Column(String(100), default="新对话")
    messages_json = Column(Text, default="[]")
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow)

class VideoJob(Base):
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

Base.metadata.create_all(bind=engine)

# ── Auth ──────────────────────────────────────────────────

SECRET_KEY        = os.getenv("SECRET_KEY", "ecommerce-ai-secret-xk9z-2024")
ALGORITHM         = "HS256"
TOKEN_EXPIRE_DAYS = 30
pwd_ctx           = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_pw(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_pw(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def make_token(user_id: int, username: str) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "name": username, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        payload = jwt.decode(authorization[7:], SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "username": payload["name"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

# ── Prompts ──────────────────────────────────────────────

IMAGE_ANALYZE_PROMPT = """你是电商视觉分析专家。深度分析这张图片，用于指导电商内容创作，中文输出以下维度：
1. 构图与布局（产品位置、画面层次、视角）
2. 色调与配色（主色调、辅色、具体颜色描述）
3. 光线与质感（打光方式、阴影、材质表现）
4. 背景与场景（风格、道具、氛围）
5. 产品特征与视觉亮点（形态、细节、差异化）
6. 整体视觉风格定位（高端/亲民/活泼/专业等）
7. 若要生成同款风格图片，必须保留的核心视觉元素（详细列举）
输出连贯段落，重点突出第7点的可复现视觉特征。"""

KEYWORD_EXTRACT_PROMPT = """你是资深电商运营策略专家。结合对话历史和当前用户输入，进行深度分析，返回JSON（不要 markdown 代码块）：
{
  "keywords": ["关键词1","关键词2",...],
  "ecommerce_prompt": "精炼的电商提示词（若有参考图分析，必须提炼其中的视觉卖点）",
  "product_type": "产品类型",
  "target_audience": "目标客群（细分描述）",
  "core_appeal": "核心卖点（若有参考图，结合图片视觉特征提炼）",
  "emotional_trigger": "情感触发点（用户痛点/欲望）",
  "brand_positioning": "品牌定位关键词",
  "scene": "营销场景",
  "optimization_direction": "基于历史的优化方向（如有）"
}
分析要求：
- 若有参考图/参考视频分析数据，关键词必须包含视觉相关词汇（色彩、材质、风格、镜头语言）
- 若是视频素材，核心卖点和电商提示词必须体现视频的动态特征和节奏感
- 若用户提到「上面」「之前」「刚才」等，必须结合对话历史理解其指向
- 关键词要具体、有差异化，避免泛泛的通用词
- 优化方向要指出与上一次的差异和改进点"""

TEXT_GEN_PROMPT = """你是专业电商文案专家。根据结构化分析数据生成高质量电商文案。
若有 image_analysis 字段，必须将图片中的视觉特征（色彩、质感、场景氛围）融入文案的感官描述，让文字能唤起视觉联想。
要求：标题强吸引力、卖点层次分明、情感共鸣、语言符合目标客群。
如果分析数据中有优化方向，必须体现在文案差异上。"""

IMAGE_GEN_PROMPT = """你是电商视觉设计专家。根据分析数据生成精准的英文图片提示词供 gpt-image-2 使用。
若有 image_analysis 字段，必须将其中的构图方式、色调配色（含具体颜色）、光线质感、背景风格、核心视觉元素逐一转化为英文视觉参数，高度还原参考图风格。
要求：商业级产品摄影，产品主体清晰突出，保留参考图的核心视觉语言，体现品牌定位和情感调性。
只输出英文提示词，不超过400词。"""

VIDEO_ANALYZE_PROMPT = """你是电商视频分析专家。我将提供视频中均匀抽取的多帧画面，请基于这些实际帧内容进行深度分析，用于指导电商视频内容创作，中文输出以下维度：
1. 视频主题与核心叙事（产品类型、故事线、核心信息——必须基于画面实际内容）
2. 产品展示手法（出镜角度、动态展示方式、特写细节——描述画面中真实看到的产品）
3. 视觉风格（色调、配色方案、氛围、构图特点——基于实际帧的色彩和构图）
4. 场景与道具（拍摄环境、背景元素、辅助道具——描述画面中实际出现的元素）
5. 人物与情绪（若有人物：外貌、动作、表情、情感传递）
6. 营销卖点与情感诉求（从画面内容中提炼）
7. 若要复刻同款风格，必须还原的核心视觉要素（详细列举：具体色调数值/描述、构图方式、光线特点、景别切换节奏）
请严格基于你看到的画面内容分析，不要凭空推测，输出连贯段落，重点突出第7点的可复现视觉特征。"""

VIDEO_GEN_PROMPT = """你是电商视频策划专家。根据分析数据生成适合Sora的英文视频提示词。
要求：5秒短视频，电商广告级质感，体现情感触发点，只输出英文提示词。"""


def _extract_video_frames(video_path: str, max_frames: int = 16) -> list[str]:
    """均匀抽帧，返回 base64 JPEG 列表。"""
    from moviepy import VideoFileClip
    from PIL import Image
    import io as _io
    import numpy as np

    clip = VideoFileClip(video_path)
    duration = clip.duration
    if duration <= 0:
        clip.close()
        return []

    # 每秒约 1.5 帧，最少 4 帧，最多 max_frames 帧
    n = min(max_frames, max(4, int(duration * 1.5)))
    times = [duration * i / n for i in range(n)]

    frames = []
    for t in times:
        try:
            arr = clip.get_frame(t)          # (H, W, 3) uint8
            img = Image.fromarray(arr)
            # 长边缩到 768px，降低 token 消耗
            mx = max(img.width, img.height)
            if mx > 768:
                ratio = 768 / mx
                img = img.resize(
                    (int(img.width * ratio), int(img.height * ratio)),
                    Image.LANCZOS,
                )
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            frames.append(base64.b64encode(buf.getvalue()).decode())
        except Exception:
            continue

    clip.close()
    return frames


def _analyze_video_from_path(video_path: str) -> str:
    """从已存在的视频文件抽帧并调用 gpt-4o vision 分析。"""
    frames = _extract_video_frames(video_path, max_frames=16)
    if not frames:
        return "[视频帧提取失败，请检查视频格式]"
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}}
        for b64 in frames
    ]
    content.append({"type": "text", "text": VIDEO_ANALYZE_PROMPT})
    resp = gpt_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=2000,
    )
    return resp.choices[0].message.content.strip()


def _analyze_video(vdata: bytes, filename: str, mime: str) -> str:
    """字节流版本：写入临时文件后调用 _analyze_video_from_path，用于 /api/analyze 流程。"""
    suffix = Path(filename or "video.mp4").suffix or ".mp4"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(vdata)
        return _analyze_video_from_path(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


async def _do_analyze_image(img_data: bytes, ct: str):
    img_b64 = base64.b64encode(img_data).decode()
    resp = await run_sync(
        gpt_client.chat.completions.create,
        model="gpt-4o",
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{ct};base64,{img_b64}"}},
            {"type": "text", "text": IMAGE_ANALYZE_PROMPT},
        ]}],
    )
    return img_b64, resp.choices[0].message.content.strip()


async def _do_analyze_video(video_data: bytes, filename: str, mime: str) -> str:
    try:
        return await run_sync(_analyze_video, video_data, filename, mime)
    except Exception as ve:
        return f"[视频解析失败: {ve}]"


VIDEO_MARKETING_PROMPT = """你是专业电商视频文案策划师。根据视频语音转录内容，分析视频主题、产品特点和目标用户，生成以下内容：

【视频标题】（吸引眼球，≤18字）

【短视频文案】（抖音/小红书风格，100-150字，有节奏感，结尾带行动呼吁）

【核心卖点】（3-5条，每条≤20字，突出差异化）

【话题标签】（5个，格式：#话题名）

只输出以上四个部分，不要其他内容。"""

VIDEO_MARKETING_PROMPT_WITH_KEYWORDS = """你是专业电商视频文案策划师。以下提供了视频语音转录内容和从视频画面提取的关键词，请充分利用关键词的视觉信息和转录内容，生成精准的营销内容：

【视频标题】（≤18字，自然融入关键词）

【短视频文案】（抖音/小红书风格，100-150字，节奏感强，关键词有机融入，结尾带行动呼吁）

【核心卖点】（3-5条，每条≤20字，基于关键词提炼差异化卖点）

【话题标签】（5个，优先使用关键词相关话题，格式：#话题名）

只输出以上四个部分，不要其他内容。"""

ECOMMERCE_OVERLAY_PROMPT = """你是电商视频制作专家。根据关键词和视频内容，生成视频文字叠加层数据。

规则：
- headline：产品主标题，8-14字，突出最核心卖点，可包含数字（如"高效祛斑 14天见效"）
- features：3-4个卖点文字，每条6-14字，具体可感，避免空话
- cta：结尾行动号召，4-10字（如"限时折扣 立即抢购"、"点击购买 包邮到家"）

只输出以下 JSON 格式，不要任何其他文字：
{
  "headline": "...",
  "features": ["...", "...", "...", "..."],
  "cta": "..."
}"""


def _seconds_to_srt(s: float) -> str:
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sec:02d},{int((s % 1) * 1000):03d}"


def _transcribe(video_path: str) -> dict:
    with open(video_path, "rb") as f:
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


def _build_srt(segments: list) -> str:
    parts = []
    for i, seg in enumerate(segments, 1):
        parts.append(f"{i}\n{_seconds_to_srt(seg['start'])} --> {_seconds_to_srt(seg['end'])}\n{seg['text']}\n")
    return "\n".join(parts)


def _generate_ecommerce_video(
    video_path: str,
    segments: list,
    overlay_data: dict,
    output_path: str,
) -> None:
    """合成电商新视频：原视频 + 主标题 + 关键词卖点 + 字幕 + CTA。MoviePy 2.x API。"""
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    clip = VideoFileClip(video_path)
    vw, vh = int(clip.w), int(clip.h)
    duration = clip.duration

    def load_font(size: int):
        for fp in [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def render(text: str, font_size: int, text_rgb: tuple, bg_rgb: tuple, bg_alpha: float, pad: int = 14):
        """Render text with rounded-rect background; returns (rgb_array, alpha_array)."""
        font = load_font(font_size)
        probe = Image.new("RGBA", (1, 1))
        bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        iw = min(tw + pad * 2, int(vw * 0.88))
        ih = th + pad * 2
        img = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = min(ih // 3, 18)
        draw.rounded_rectangle([(0, 0), (iw - 1, ih - 1)], radius=r, fill=(*bg_rgb, int(255 * bg_alpha)))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((pad + dx, pad + dy), text, font=font, fill=(0, 0, 0, 180))
        draw.text((pad, pad), text, font=font, fill=(*text_rgb, 255))
        arr = np.array(img)
        return arr[:, :, :3], arr[:, :, 3].astype(float) / 255.0

    def make_clip(text: str, font_size: int, text_rgb, bg_rgb, bg_alpha, t_start: float, dur: float, x, y):
        rgb, alpha = render(text, font_size, text_rgb, bg_rgb, bg_alpha)
        fh, fw = rgb.shape[0], rgb.shape[1]
        # clamp position
        cx = int(vw / 2 - fw / 2) if x == "center" else max(0, min(int(x), vw - fw))
        cy = max(0, min(int(y), vh - fh))
        ic = ImageClip(rgb,   duration=dur).with_start(t_start)
        mc = ImageClip(alpha, is_mask=True, duration=dur).with_start(t_start)
        return ic.with_mask(mc).with_position((cx, cy))

    all_clips = [clip]

    # ── 1. 主标题（前4秒 或 视频前30%，取较小值） ──
    headline = (overlay_data.get("headline") or "").strip()
    if headline:
        hl_dur = min(4.0, duration * 0.30)
        hl_fs  = max(32, vh // 16)
        try:
            all_clips.append(make_clip(
                headline, hl_fs, (255, 255, 255), (20, 20, 20), 0.78,
                t_start=0, dur=hl_dur,
                x="center", y=int(vh * 0.06),
            ))
        except Exception:
            pass

    # ── 2. 关键词卖点（均匀分布在视频 20%~75% 时段，左右交替） ──
    features = [f.strip() for f in (overlay_data.get("features") or []) if str(f).strip()]
    if features:
        feat_fs = max(26, vh // 22)
        n = len(features)
        for i, feat in enumerate(features):
            frac    = 0.20 + 0.55 * (i / max(n - 1, 1))
            t_start = duration * frac
            feat_dur = min(3.0, duration * 0.18)
            t_start  = min(t_start, duration - feat_dur - 0.3)
            if t_start < 0:
                continue
            x = int(vw * 0.04) if i % 2 == 0 else int(vw * 0.96) - int(vw * 0.40)
            y = int(vh * 0.30) + i * max(int(vh * 0.07), 1)
            y = min(y, vh - int(vh * 0.22))
            try:
                all_clips.append(make_clip(
                    feat, feat_fs, (255, 255, 255), (249, 115, 22), 0.90,
                    t_start=t_start, dur=feat_dur, x=x, y=y,
                ))
            except Exception:
                continue

    # ── 3. 字幕（底部，来自 Whisper 分段） ──
    sub_fs = max(24, vh // 20)
    for seg in segments:
        txt = seg["text"].strip()
        if not txt or seg["end"] <= seg["start"]:
            continue
        try:
            rgb, alpha = render(txt, sub_fs, (255, 255, 255), (0, 0, 0), 0.65)
            fh = rgb.shape[0]
            dur = seg["end"] - seg["start"]
            ic = ImageClip(rgb,   duration=dur).with_start(seg["start"])
            mc = ImageClip(alpha, is_mask=True, duration=dur).with_start(seg["start"])
            all_clips.append(ic.with_mask(mc).with_position(("center", vh - fh - int(vh * 0.06))))
        except Exception:
            continue

    # ── 4. CTA（结尾4秒 或 视频后25%，字幕区正上方） ──
    cta = (overlay_data.get("cta") or "").strip()
    if cta:
        cta_dur   = min(4.0, duration * 0.25)
        cta_start = max(0.0, duration - cta_dur)
        cta_fs    = max(30, vh // 15)
        try:
            rgb, _ = render(cta, cta_fs, (255, 255, 255), (220, 38, 38), 0.92)
            fh_cta = rgb.shape[0]
            sub_bottom = vh - max(24, vh // 20) - int(vh * 0.06)
            cta_y = sub_bottom - fh_cta - int(vh * 0.025)
            all_clips.append(make_clip(
                cta, cta_fs, (255, 255, 255), (220, 38, 38), 0.92,
                t_start=cta_start, dur=cta_dur,
                x="center", y=cta_y,
            ))
        except Exception:
            pass

    final = CompositeVideoClip(all_clips, size=(vw, vh))
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None, threads=2)
    clip.close()
    final.close()

COMBINE_PROMPT = """你是电商视觉设计专家。用户提供了两张图片：
- 图1：已生成的产品图（作为主体参考）
- 图2：用户新上传的参考图（提供风格/背景/色调灵感）
请生成英文提示词，指导 gpt-image-2 将两图融合：保留图1的产品主体，融入图2的视觉风格、背景氛围或配色。
只输出英文提示词，不超过300词。"""


# ── 构建历史上下文字符串 ──────────────────────────────────

def build_history_context(history_json: str) -> str:
    if not history_json:
        return ""
    try:
        history = json.loads(history_json)
    except Exception:
        return ""
    if not history:
        return ""

    lines = ["## 对话历史（请结合以下上下文理解用户当前意图）\n"]
    for i, turn in enumerate(history, 1):
        lines.append(f"### 第{i}轮")
        lines.append(f"用户输入：{turn.get('user_text', '')}")
        ctx = turn.get("context", {})
        if ctx:
            lines.append(f"分析关键词：{', '.join(ctx.get('keywords', []))}")
            lines.append(f"产品类型：{ctx.get('product_type', '')}")
            lines.append(f"核心卖点：{ctx.get('core_appeal', '')}")
            lines.append(f"电商提示词：{ctx.get('ecommerce_prompt', '')}")
            if ctx.get("optimization_direction"):
                lines.append(f"优化方向：{ctx.get('optimization_direction', '')}")
        result = turn.get("result")
        if result:
            if result.get("type") == "text":
                snippet = result.get("content", "")[:120]
                lines.append(f"生成结果（文案片段）：{snippet}…")
            elif result.get("type") == "image":
                lines.append(f"生成结果（图片）：使用提示词「{result.get('image_prompt', '')}」生成了图片")
            elif result.get("type") == "video":
                lines.append(f"生成结果（视频）：使用提示词「{result.get('video_prompt', '')}」生成了视频")
        lines.append("")
    return "\n".join(lines)


# ── 1. 分析接口 ───────────────────────────────────────────

@app.post("/api/analyze")
async def analyze(
    text: str = Form(...),
    history: str = Form(default="[]"),
    ref_files: List[UploadFile] = File(default=[]),
):
    try:
        image_items: list[tuple[bytes, str]] = []
        video_items: list[tuple[bytes, str, str]] = []

        for rf in ref_files:
            if not rf.filename:
                continue
            ct = rf.content_type or ""
            if ct.startswith("image/"):
                image_items.append((await rf.read(), ct))
            elif ct.startswith("video/"):
                video_items.append((await rf.read(), rf.filename, ct))

        img_results, vid_results = await asyncio.gather(
            asyncio.gather(*[_do_analyze_image(d, ct) for d, ct in image_items]),
            asyncio.gather(*[_do_analyze_video(d, fn, ct) for d, fn, ct in video_items]),
        )

        img_b64_stored = None
        mime_stored    = None
        image_analyses = []
        for (img_b64, analysis), (img_data, ct) in zip(img_results, image_items):
            if img_b64_stored is None:
                img_b64_stored, mime_stored = img_b64, ct
            image_analyses.append(analysis)
        video_analyses = list(vid_results)

        all_analyses = (
            [f"[图片{i+1}]\n{a}" for i, a in enumerate(image_analyses)] if len(image_analyses) > 1
            else image_analyses
        ) + (
            [f"[视频{i+1}]\n{a}" for i, a in enumerate(video_analyses)] if len(video_analyses) > 1
            else video_analyses
        )

        if len(all_analyses) == 1:
            image_analysis = all_analyses[0]
        elif len(all_analyses) > 1:
            image_analysis = "\n\n---\n\n".join(all_analyses)
        else:
            image_analysis = None

        history_ctx = build_history_context(history)

        user_content = text
        if image_analysis:
            user_content += f"\n\n[参考图视觉分析]\n{image_analysis}"
        if history_ctx:
            user_content = history_ctx + "\n\n## 当前用户输入\n" + user_content

        kw_resp = await run_sync(
            gpt_client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": KEYWORD_EXTRACT_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        raw = kw_resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        kw_data = json.loads(raw)

        context = {
            "keywords":             kw_data.get("keywords", []),
            "ecommerce_prompt":     kw_data.get("ecommerce_prompt", ""),
            "product_type":         kw_data.get("product_type", ""),
            "target_audience":      kw_data.get("target_audience", ""),
            "core_appeal":          kw_data.get("core_appeal", ""),
            "emotional_trigger":    kw_data.get("emotional_trigger", ""),
            "brand_positioning":    kw_data.get("brand_positioning", ""),
            "scene":                kw_data.get("scene", ""),
            "optimization_direction": kw_data.get("optimization_direction", ""),
            "image_analysis":       image_analysis,
            "ref_image_b64":        img_b64_stored,
            "ref_image_mime":       mime_stored,
        }
        return {"context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 2. 生成接口 ───────────────────────────────────────────

class GenerateRequest(BaseModel):
    context: dict
    output_type: str
    model: str = "chatgpt"


@app.post("/api/generate")
async def generate(request: GenerateRequest):
    ctx = request.context
    ctx_for_llm = {k: v for k, v in ctx.items() if k not in ("ref_image_b64", "ref_image_mime")}
    ctx_str = json.dumps(ctx_for_llm, ensure_ascii=False, indent=2)
    otype = request.output_type
    use_deepseek = request.model == "deepseek"

    ai = deepseek_client if use_deepseek else gpt_client
    model_name = "deepseek-v4" if use_deepseek else "gpt-4o-mini"

    try:
        if otype == "text":
            resp = await run_sync(
                ai.chat.completions.create,
                model=model_name,
                messages=[
                    {"role": "system", "content": TEXT_GEN_PROMPT},
                    {"role": "user", "content": f"分析数据：\n{ctx_str}"},
                ],
            )
            return {"type": "text", "content": resp.choices[0].message.content}

        elif otype == "image":
            trans = await run_sync(
                ai.chat.completions.create,
                model=model_name,
                messages=[
                    {"role": "system", "content": IMAGE_GEN_PROMPT},
                    {"role": "user", "content": ctx_str},
                ],
            )
            image_prompt = trans.choices[0].message.content.strip()

            ref_b64 = ctx.get("ref_image_b64")
            if ref_b64:
                mime = ctx.get("ref_image_mime", "image/png")
                ext  = mime.split("/")[-1].split(";")[0] or "png"
                resp = await run_sync(
                    gpt_client.images.edit,
                    model="gpt-image-2",
                    image=(f"reference.{ext}", io.BytesIO(base64.b64decode(ref_b64)), mime),
                    prompt=image_prompt,
                    size="1024x1024",
                    n=1,
                )
            else:
                resp = await run_sync(
                    gpt_client.images.generate,
                    model="gpt-image-2",
                    prompt=image_prompt,
                    size="1024x1024",
                    n=1,
                )
            b64 = resp.data[0].b64_json
            return {"type": "image", "url": f"data:image/png;base64,{b64}", "image_prompt": image_prompt}

        elif otype == "video":
            trans = await run_sync(
                ai.chat.completions.create,
                model=model_name,
                messages=[
                    {"role": "system", "content": VIDEO_GEN_PROMPT},
                    {"role": "user", "content": ctx_str},
                ],
            )
            video_prompt = trans.choices[0].message.content.strip()
            resp = await run_sync(
                gpt_client.video.generations.create,
                model="sora-2", prompt=video_prompt, size="480p", duration=5, n=1,
            )
            return {"type": "video", "url": resp.data[0].url, "video_prompt": video_prompt}

        else:
            raise HTTPException(status_code=400, detail="无效的 output_type")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 3. 合并图片接口 ───────────────────────────────────────

class CombineRequest(BaseModel):
    image1_b64: str
    image2_b64: str
    image2_mime: str = "image/jpeg"
    context: dict = {}
    extra_text: str = ""


@app.post("/api/combine")
async def combine(request: CombineRequest):
    try:
        b64_1 = request.image1_b64.split(",", 1)[1] if "," in request.image1_b64 else request.image1_b64
        img1_bytes = base64.b64decode(b64_1)
        img2_bytes = base64.b64decode(request.image2_b64)

        ctx_str = json.dumps(
            {k: v for k, v in request.context.items() if k not in ("ref_image_b64", "ref_image_mime")},
            ensure_ascii=False
        )
        user_msg = f"分析数据：{ctx_str}"
        if request.extra_text:
            user_msg += f"\n用户补充说明：{request.extra_text}"

        trans = await run_sync(
            gpt_client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": COMBINE_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        combine_prompt_text = trans.choices[0].message.content.strip()

        mime2 = request.image2_mime
        ext2  = mime2.split("/")[-1].split(";")[0] or "jpg"

        resp = await run_sync(
            gpt_client.images.edit,
            model="gpt-image-2",
            image=[
                ("generated.png",       io.BytesIO(img1_bytes), "image/png"),
                (f"reference.{ext2}", io.BytesIO(img2_bytes), mime2),
            ],
            prompt=combine_prompt_text,
            size="1024x1024",
            n=1,
        )
        b64_result = resp.data[0].b64_json
        return {"type": "image", "url": f"data:image/png;base64,{b64_result}", "image_prompt": combine_prompt_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 4. 用户认证接口 ───────────────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/register")
def register(req: AuthRequest, db=Depends(get_db)):
    if len(req.username.strip()) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 位")
    if db.query(User).filter(User.username == req.username.strip()).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=req.username.strip(), password_hash=hash_pw(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": make_token(user.id, user.username), "username": user.username}


@app.post("/api/auth/login")
def login(req: AuthRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.username == req.username.strip()).first()
    if not user or not verify_pw(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    return {"token": make_token(user.id, user.username), "username": user.username}


# ── 5. 会话管理接口 ───────────────────────────────────────

@app.get("/api/sessions")
def list_sessions(user=Depends(require_user), db=Depends(get_db)):
    rows = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user["id"])
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        {"id": r.id, "title": r.title, "updated_at": r.updated_at.isoformat()}
        for r in rows
    ]


@app.post("/api/sessions")
def create_session(user=Depends(require_user), db=Depends(get_db)):
    s = ChatSession(user_id=user["id"])
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title, "updated_at": s.updated_at.isoformat()}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: int, user=Depends(require_user), db=Depends(get_db)):
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user["id"]).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"id": s.id, "title": s.title, "messages": json.loads(s.messages_json)}


class SaveRequest(BaseModel):
    title: str = ""
    messages: list


@app.put("/api/sessions/{session_id}")
def save_session(session_id: int, req: SaveRequest, user=Depends(require_user), db=Depends(get_db)):
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user["id"]).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")

    clean = []
    for m in req.messages:
        if m.get("role") == "user":
            clean.append({**m, "refThumb": None})
        elif m.get("role") == "analysis":
            ctx = dict(m.get("analysis", {}).get("context") or {})
            ctx.pop("ref_image_b64", None)
            ctx.pop("ref_image_mime", None)
            clean.append({**m, "generating": None,
                          "analysis": {**m.get("analysis", {}), "context": ctx}})
        else:
            clean.append(m)

    s.messages_json = json.dumps(clean, ensure_ascii=False)
    if req.title:
        s.title = req.title[:60]
    s.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: int, user=Depends(require_user), db=Depends(get_db)):
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user["id"]).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ── 6. 视频处理流水线（两步式）─────────────────────────────
# Step A  POST /api/video/analyze  上传视频 → 抽帧 → GPT视觉分析 → 提取关键词
# Step B  POST /api/video/process  session_id + 用户关键词 → Whisper + GPT文案 + 字幕

@app.post("/api/video/analyze")
async def video_analyze_phase1(video: UploadFile = File(...), user=Depends(require_user)):
    """Phase 1：抽帧分析视频画面，提取结构化关键词，暂存视频供 Phase 2 使用。"""
    video_data = await video.read()
    if len(video_data) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="视频文件不能超过 200MB")

    suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
    fd, path_in = tempfile.mkstemp(suffix=suffix)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(video_data)

        # 抽帧 + GPT 视觉分析（sync 包在线程池）
        image_analysis = await run_sync(_analyze_video_from_path, path_in)

        # GPT 提取结构化关键词（与现有 analyze 流程复用同一 prompt）
        kw_resp = await run_sync(
            gpt_client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": KEYWORD_EXTRACT_PROMPT},
                {"role": "user", "content": f"[视频画面分析]\n{image_analysis}"},
            ],
        )
        raw = kw_resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        kw_data = json.loads(raw)

        # 暂存视频文件，session_id 作为跨请求引用
        sid = str(uuid.uuid4())
        _video_sessions[sid] = path_in   # 不删除文件，等 Phase 2 用

        return {
            "session_id":      sid,
            "image_analysis":  image_analysis,
            "keywords":        kw_data.get("keywords", []),
            "product_type":    kw_data.get("product_type", ""),
            "core_appeal":     kw_data.get("core_appeal", ""),
            "target_audience": kw_data.get("target_audience", ""),
            "emotional_trigger": kw_data.get("emotional_trigger", ""),
            "ecommerce_prompt": kw_data.get("ecommerce_prompt", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        try:
            os.remove(path_in)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/video/process")
async def video_process(
    session_id:   str = Form(...),
    keywords:     str = Form(default="[]"),   # JSON 数组字符串
    extra_prompt: str = Form(default=""),
    user=Depends(require_user),
):
    """Phase 2：用用户确认的关键词驱动 Whisper 转录 + 并行生成文案和叠加层数据 + MoviePy 合成电商新视频。"""
    path_in = _video_sessions.get(session_id)
    if not path_in or not os.path.exists(path_in):
        raise HTTPException(status_code=404, detail="视频会话已过期，请重新上传并分析")

    suffix = Path(path_in).suffix or ".mp4"
    fd_out, path_out = tempfile.mkstemp(suffix=suffix)
    os.close(fd_out)
    success = False

    try:
        kw_list = json.loads(keywords) if keywords else []

        # Whisper 转录
        transcript = await run_sync(_transcribe, path_in)
        if not transcript["text"]:
            raise HTTPException(status_code=422, detail="未能从视频中识别到语音内容")

        # 构建 GPT 输入，融合关键词
        kw_str = "、".join(kw_list) if kw_list else ""
        shared_content = f"视频转录内容：\n{transcript['text']}"
        if kw_str:
            shared_content += f"\n\n产品关键词：{kw_str}"
        if extra_prompt:
            shared_content += f"\n\n用户补充要求：{extra_prompt}"

        # 并行：① 长文案  ② 视频叠加层 JSON（主标题 + 卖点 + CTA）
        prompt_key = VIDEO_MARKETING_PROMPT_WITH_KEYWORDS if kw_list else VIDEO_MARKETING_PROMPT
        copy_resp, overlay_resp = await asyncio.gather(
            run_sync(
                gpt_client.chat.completions.create,
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt_key},
                    {"role": "user",   "content": shared_content},
                ],
            ),
            run_sync(
                gpt_client.chat.completions.create,
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": ECOMMERCE_OVERLAY_PROMPT},
                    {"role": "user",   "content": shared_content},
                ],
            ),
        )

        # 解析叠加层 JSON
        raw_overlay = overlay_resp.choices[0].message.content.strip()
        if raw_overlay.startswith("```"):
            raw_overlay = raw_overlay.split("```")[1]
            if raw_overlay.startswith("json"):
                raw_overlay = raw_overlay[4:]
        try:
            overlay_data = json.loads(raw_overlay)
        except Exception:
            overlay_data = {"headline": "", "features": kw_list[:4], "cta": ""}

        # MoviePy 合成电商新视频（主标题 + 卖点 + 字幕 + CTA）
        await run_sync(
            _generate_ecommerce_video,
            path_in, transcript["segments"], overlay_data, path_out,
        )

        out_file = path_out if os.path.exists(path_out) and os.path.getsize(path_out) > 0 else path_in
        with open(out_file, "rb") as f:
            out_b64 = base64.b64encode(f.read()).decode()

        success = True
        _video_sessions.pop(session_id, None)   # 成功后才消费 session

        return {
            "transcript":     transcript["text"],
            "segments":       transcript["segments"],
            "marketing_copy": copy_resp.choices[0].message.content.strip(),
            "overlay_data":   overlay_data,
            "video_b64":      out_b64,
            "video_mime":     f"video/{suffix.lstrip('.')}",
            "srt":            _build_srt(transcript["segments"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 输出文件总是清理；输入文件只在成功时清理（失败可重试）
        try:
            if os.path.exists(path_out):
                os.remove(path_out)
        except Exception:
            pass
        if success:
            try:
                if os.path.exists(path_in):
                    os.remove(path_in)
            except Exception:
                pass


# ── 7. Celery 视频处理流水线 ──────────────────────────────────
# POST /api/pipeline/upload   上传视频 → 分配 job_id → 异步处理
# GET  /api/pipeline/job/{id} 查询任务状态与结果
# GET  /api/pipeline/download/{id} 下载已处理视频

_UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
_OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(_UPLOADS_DIR, exist_ok=True)
os.makedirs(_OUTPUTS_DIR, exist_ok=True)


@app.post("/api/pipeline/upload")
async def pipeline_upload(
    video: UploadFile = File(...),
    user=Depends(require_user),
    db=Depends(get_db),
):
    video_data = await video.read()
    if len(video_data) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="视频文件不能超过 500MB")

    job_id = str(uuid.uuid4())
    suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
    save_path = os.path.join(_UPLOADS_DIR, f"{job_id}{suffix}")
    with open(save_path, "wb") as f:
        f.write(video_data)

    job = VideoJob(
        id=job_id,
        user_id=user["id"],
        status="pending",
        stage="等待处理",
        progress=0,
        input_path=save_path,
    )
    db.add(job)
    db.commit()

    try:
        from celery_app import celery_app as _celery
        _celery.send_task("tasks.process_video", args=[job_id, save_path])
    except Exception as e:
        db.query(VideoJob).filter(VideoJob.id == job_id).update(
            {"status": "failed", "error_msg": f"Celery 调度失败: {str(e)[:200]}"}
        )
        db.commit()
        raise HTTPException(status_code=503, detail=f"任务调度失败，请确保 Celery Worker 已启动: {e}")

    return {"job_id": job_id, "status": "pending"}


@app.get("/api/pipeline/job/{job_id}")
def pipeline_job_status(
    job_id: str,
    user=Depends(require_user),
    db=Depends(get_db),
):
    job = db.query(VideoJob).filter(VideoJob.id == job_id, VideoJob.user_id == user["id"]).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在或无权限查看")

    result = {
        "job_id":        job.id,
        "status":        job.status,
        "stage":         job.stage,
        "progress":      job.progress,
        "error_msg":     job.error_msg,
        "created_at":    job.created_at.isoformat() if job.created_at else None,
        "updated_at":    job.updated_at.isoformat() if job.updated_at else None,
    }
    if job.status == "completed":
        result["transcript"]     = job.transcript
        result["marketing_copy"] = job.marketing_copy
        result["srt_content"]    = job.srt_content
        try:
            result["overlay"] = json.loads(job.overlay_json or "{}")
        except Exception:
            result["overlay"] = {}
        result["has_output"] = bool(job.output_path and os.path.exists(job.output_path))
    return result


@app.get("/api/pipeline/download/{job_id}")
def pipeline_download(
    job_id: str,
    user=Depends(require_user),
    db=Depends(get_db),
):
    job = db.query(VideoJob).filter(VideoJob.id == job_id, VideoJob.user_id == user["id"]).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在或无权限访问")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"视频尚未处理完成，当前状态: {job.status}")
    if not job.output_path or not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="输出文件不存在")

    suffix = Path(job.output_path).suffix or ".mp4"
    mime   = f"video/{suffix.lstrip('.')}"
    return FileResponse(
        job.output_path,
        media_type=mime,
        filename=f"processed_{job_id[:8]}{suffix}",
    )


# ── 7. 关键帧提取与 GPT-4o 分析 ──────────────────────────────
# POST /api/keyframes/start  上传视频 → 启动异步任务 → 返回 job_id
# GET  /api/keyframes/{job_id}  轮询任务状态和结果

_kf_jobs: dict = {}   # job_id → {status, stage, progress, result, error}


async def _run_kf_job(job_id: str, tmp_path: str, threshold: float, max_frames: int):
    """异步执行关键帧提取流水线，按阶段更新 _kf_jobs。"""
    import sys as _sys
    _backend = os.path.dirname(os.path.abspath(__file__))
    if _backend not in _sys.path:
        _sys.path.insert(0, _backend)
    from extract_keyframes import (
        get_video_meta, get_keyframe_timestamps,
        extract_frames_at, analyze_with_gpt4o, DEFAULT_PROMPT,
    )

    def _upd(**kw):
        _kf_jobs[job_id].update(kw)

    try:
        _upd(stage="读取视频元数据...", progress=10)
        meta = await run_sync(get_video_meta, tmp_path)

        _upd(stage=f"场景变化检测（阈值 {threshold}）...", progress=30)
        timestamps, source = await run_sync(
            get_keyframe_timestamps, tmp_path, threshold, max_frames, meta["duration_sec"]
        )

        _upd(stage=f"精确抽取 {len(timestamps)} 帧...", progress=55)
        api_key = os.environ.get("OPENAI_API_KEY", "")

        with tempfile.TemporaryDirectory() as tmp_frames:
            frame_paths = await run_sync(extract_frames_at, tmp_path, timestamps, tmp_frames)

            _upd(stage="GPT-4o 分析关键帧...", progress=72)
            analysis = await run_sync(analyze_with_gpt4o, frame_paths, DEFAULT_PROMPT, api_key)

        _upd(
            status="completed", stage="分析完成", progress=100,
            result={
                "meta": meta,
                "extraction": {"source": source, "threshold": threshold, "frame_count": len(timestamps)},
                "frames": [{"index": i, "timestamp_sec": t} for i, t in enumerate(timestamps)],
                "gpt4o_analysis": analysis,
            },
        )
    except Exception as exc:
        _upd(status="failed", stage="处理出错", progress=0, error=str(exc))
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.post("/api/keyframes/start")
async def keyframes_start(
    video: UploadFile = File(...),
    threshold: float  = Form(default=0.40),
    max_frames: int   = Form(default=12),
    user=Depends(require_user),
):
    data = await video.read()
    if len(data) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="视频不能超过 500MB")
    suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)

    job_id = str(uuid.uuid4())
    _kf_jobs[job_id] = {"status": "processing", "stage": "上传完成，准备分析...", "progress": 5, "result": None, "error": None}
    asyncio.create_task(_run_kf_job(job_id, tmp_path, threshold, max_frames))
    return {"job_id": job_id}


@app.get("/api/keyframes/{job_id}")
async def keyframes_status(job_id: str, user=Depends(require_user)):
    job = _kf_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
