"""
extract_keyframes.py — 视频关键帧提取工具

模式一：仅提取时间戳（默认）
  python extract_keyframes.py video.mp4
  → 输出 JSON，只含时间戳 + 视频元数据，无图片数据，文件极小

模式二：GPT-4o 关键帧图像分析
  python extract_keyframes.py video.mp4 --analyze
  → 按时间戳精确抽帧，发送给 GPT-4o，分析结果写入 JSON

其他选项:
  --threshold FLOAT   场景变化阈值 0.0-1.0（默认 0.40，越小越敏感）
  --max-frames INT    最大帧数（默认 12）
  --output PATH       输出 JSON 路径（默认与视频同名 .json）
  --include-images    JSON 中额外保存 base64 图片（仅模式二有效）
  --prompt TEXT       自定义 GPT-4o 分析 prompt（仅模式二有效）

示例:
  # 仅时间戳
  python extract_keyframes.py product.mp4

  # GPT-4o 分析（需 .env 中有 OPENAI_API_KEY）
  python extract_keyframes.py product.mp4 --analyze

  # 调低阈值、最多20帧
  python extract_keyframes.py product.mp4 --analyze --threshold 0.25 --max-frames 20

  # 分析结果同时保存帧图片
  python extract_keyframes.py product.mp4 --analyze --include-images
"""

import argparse
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ── FFmpeg / FFprobe 路径发现 ──────────────────────────────────────

def _find_bin(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    patterns = [
        rf"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\{name}.exe",
        rf"C:\Program Files\FFmpeg\bin\{name}.exe",
        rf"C:\ffmpeg\bin\{name}.exe",
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            return sorted(matches)[-1]
    return name

FFMPEG  = _find_bin("ffmpeg")
FFPROBE = _find_bin("ffprobe")


# ── 视频元数据 ─────────────────────────────────────────────────────

def get_video_meta(video_path: str) -> dict:
    result = subprocess.run(
        [FFPROBE, "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", video_path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {result.stderr[-300:]}")

    info = json.loads(result.stdout)
    fmt  = info.get("format", {})
    duration   = float(fmt.get("duration", 0))
    size_bytes = int(fmt.get("size", 0))

    width = height = fps = None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            width  = stream.get("width")
            height = stream.get("height")
            r = stream.get("r_frame_rate", "0/1")
            if "/" in r:
                n, d = r.split("/")
                fps = round(float(n) / float(d), 2) if int(d) else 0.0
            break

    return {
        "duration_sec": round(duration, 3),
        "width":        width,
        "height":       height,
        "fps":          fps,
        "size_bytes":   size_bytes,
        "format":       fmt.get("format_name", ""),
    }


# ── 场景变化时间戳提取 ─────────────────────────────────────────────

def _get_scene_timestamps(video_path: str, threshold: float) -> list[float]:
    """ffmpeg showinfo 解析每个场景帧的精确 pts_time。"""
    result = subprocess.run(
        [FFMPEG, "-i", video_path,
         "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    timestamps = []
    for line in (result.stdout + result.stderr).splitlines():
        if "pts_time:" in line and "showinfo" in line:
            for part in line.split():
                if part.startswith("pts_time:"):
                    try:
                        timestamps.append(float(part.split(":", 1)[1]))
                    except ValueError:
                        pass
                    break
    return timestamps


def get_keyframe_timestamps(
    video_path: str,
    threshold: float = 0.40,
    max_frames: int = 12,
    duration: float = 0,
) -> tuple[list[float], str]:
    """
    返回 (时间戳列表, 来源标识)。
    场景帧 < 4 时自动降级为均匀采样。
    """
    timestamps = _get_scene_timestamps(video_path, threshold)

    if len(timestamps) >= 4:
        if len(timestamps) > max_frames:
            step = len(timestamps) / max_frames
            timestamps = [timestamps[int(i * step)] for i in range(max_frames)]
        return [round(t, 3) for t in timestamps], "scene_detection"

    # 降级：均匀采样
    n = min(max_frames, max(4, int(duration * 1.2) if duration else 8))
    ts = [round(duration * i / n, 3) for i in range(n)] if duration else []
    return ts, "uniform_sampling"


# ── 按时间戳精确抽帧 ───────────────────────────────────────────────

def extract_frames_at(
    video_path: str,
    timestamps: list[float],
    tmp_dir: str,
    scale: int = 720,
) -> list[str]:
    """
    在指定时间戳处各抽一帧，返回 JPEG 路径列表。
    每帧独立调用 FFmpeg（-ss 精确到毫秒）。
    """
    paths = []
    for i, t in enumerate(timestamps):
        out = os.path.join(tmp_dir, f"frame_{i:04d}.jpg")
        result = subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error",
             "-ss", f"{t:.3f}",
             "-i", video_path,
             "-vframes", "1",
             "-vf", f"scale={scale}:-1",
             "-q:v", "3",
             out],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and os.path.exists(out):
            paths.append(out)
        else:
            paths.append(None)  # 抽帧失败时占位
    return paths


# ── GPT-4o 分析 ────────────────────────────────────────────────────

DEFAULT_PROMPT = (
    "你是电商视频分析专家。分析这些视频关键场景帧，提取："
    "产品类型、视觉特征与色调、具体可量化的产品参数与卖点"
    "（如材质/尺寸/颜色/功能细节）、目标受众、场景氛围。"
    "输出连贯中文分析，150~250字，尽量包含具体数字和参数。"
)


def analyze_with_gpt4o(frame_paths: list[str], prompt: str, api_key: str) -> str:
    """将关键帧图片发送给 GPT-4o，返回分析文本。"""
    from openai import OpenAI

    proxy = os.environ.get("HTTP_PROXY", "http://127.0.0.1:7890")
    os.environ.setdefault("HTTP_PROXY",  proxy)
    os.environ.setdefault("HTTPS_PROXY", proxy)

    client  = OpenAI(api_key=api_key)
    content = []

    for fp in frame_paths:
        if fp and os.path.exists(fp):
            with open(fp, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {
                    "url":    f"data:image/jpeg;base64,{b64}",
                    "detail": "low",
                },
            })

    if not content:
        return "[无可用帧，分析跳过]"

    content.append({"type": "text", "text": prompt})

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=800,
    )
    return resp.choices[0].message.content.strip()


# ── 主函数 ────────────────────────────────────────────────────────

def extract_keyframes(
    video_path:      str,
    threshold:       float = 0.40,
    max_frames:      int   = 12,
    analyze:         bool  = False,
    include_images:  bool  = False,
    custom_prompt:   str   = DEFAULT_PROMPT,
    output_path:     str | None = None,
) -> str:
    """
    核心流程。返回输出 JSON 的绝对路径。

    analyze=False  → 模式一：只存时间戳，无图片，无 AI 调用
    analyze=True   → 模式二：按时间戳抽帧 → GPT-4o 分析 → 结果写 JSON
    include_images → 在模式二结果里额外保存 base64 帧图片
    """
    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    if output_path is None:
        output_path = str(Path(video_path).with_suffix(".json"))

    # ── Step 1: 元数据 ─────────────────────────────────────────
    print("[1/4] 读取视频元数据...")
    meta     = get_video_meta(video_path)
    duration = meta["duration_sec"]
    print(f"      时长 {duration:.1f}s  {meta['width']}x{meta['height']}  {meta['fps']} fps")

    # ── Step 2: 关键帧时间戳 ────────────────────────────────────
    print(f"[2/4] 场景变化检测（阈值 {threshold}）...")
    timestamps, source = get_keyframe_timestamps(video_path, threshold, max_frames, duration)
    print(f"      {len(timestamps)} 帧  来源: {source}")

    frame_records = [
        {"index": i, "timestamp_sec": t}
        for i, t in enumerate(timestamps)
    ]

    # ── Step 3: 抽帧 + 可选分析 ─────────────────────────────────
    analysis_text = None

    if analyze:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            # 尝试从 .env 加载
            env_file = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.exists(env_file):
                for line in open(env_file, encoding="utf-8"):
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not api_key:
            raise RuntimeError("未找到 OPENAI_API_KEY，请在 .env 中配置或设置环境变量")

        print("[3/4] 按时间戳精确抽帧...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_paths = extract_frames_at(video_path, timestamps, tmp_dir)
            ok = sum(1 for p in frame_paths if p)
            print(f"      成功抽取 {ok}/{len(timestamps)} 帧")

            if include_images:
                for i, fp in enumerate(frame_paths):
                    if fp and os.path.exists(fp):
                        with open(fp, "rb") as fh:
                            frame_records[i]["image_base64"] = base64.b64encode(fh.read()).decode()
                            frame_records[i]["image_format"] = "jpeg"

            print("[4/4] 调用 GPT-4o 分析...")
            analysis_text = analyze_with_gpt4o(frame_paths, custom_prompt, api_key)
            print(f"      分析完成（{len(analysis_text)} 字）")
    else:
        print("[3/4] 跳过抽帧（仅时间戳模式）")
        print("[4/4] 写入 JSON...")

    # ── 输出 JSON ────────────────────────────────────────────────
    output: dict = {
        "video_path": video_path,
        "extraction": {
            "source":          source,
            "threshold":       threshold,
            "frame_count":     len(frame_records),
            "analyze_mode":    analyze,
            "include_images":  include_images and analyze,
        },
        "meta":   meta,
        "frames": frame_records,
    }
    if analysis_text is not None:
        output["gpt4o_analysis"] = analysis_text

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n完成 → {output_path}  ({size_kb:.1f} KB)")
    return output_path


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="视频关键帧提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("video",            help="视频文件路径")
    parser.add_argument("--threshold",      type=float, default=0.40,
                        metavar="FLOAT",    help="场景变化阈值 0.0-1.0（默认 0.40）")
    parser.add_argument("--max-frames",     type=int,   default=12,
                        metavar="INT",      help="最大帧数（默认 12）")
    parser.add_argument("--analyze",        action="store_true",
                        help="调用 GPT-4o 分析关键帧图像（需 OPENAI_API_KEY）")
    parser.add_argument("--include-images", action="store_true",
                        help="结果 JSON 中保存 base64 帧图片（仅 --analyze 有效）")
    parser.add_argument("--prompt",         default=DEFAULT_PROMPT,
                        metavar="TEXT",     help="自定义 GPT-4o prompt（仅 --analyze 有效）")
    parser.add_argument("--output",         default=None,
                        metavar="PATH",     help="输出 JSON 路径（默认与视频同目录同名）")

    args = parser.parse_args()

    try:
        extract_keyframes(
            video_path=args.video,
            threshold=args.threshold,
            max_frames=args.max_frames,
            analyze=args.analyze,
            include_images=args.include_images,
            custom_prompt=args.prompt,
            output_path=args.output,
        )
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
