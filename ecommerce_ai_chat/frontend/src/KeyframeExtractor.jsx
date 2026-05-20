import { useState, useRef, useCallback } from "react";
import axios from "axios";
import "./KeyframeExtractor.css";

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("auth_token") || ""}` });

/* ─── Icons ─── */
const Ico = ({ size = 14, stroke = 2, children }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
    style={{ flexShrink: 0 }}>{children}</svg>
);
const UploadIcon   = (p) => <Ico {...p}><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></Ico>;
const FilmIcon     = (p) => <Ico {...p}><rect x="2" y="2" width="20" height="20" rx="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></Ico>;
const DownloadIcon = (p) => <Ico {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></Ico>;
const CheckIcon    = (p) => <Ico {...p}><polyline points="20 6 9 17 4 12"/></Ico>;
const AlertIcon    = (p) => <Ico {...p}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Ico>;
const ScanIcon     = (p) => <Ico {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></Ico>;

const POLL_MS = 2000;

const STAGES = [
  { label: "读取视频元数据",      pct: [5,  30] },
  { label: "场景变化检测",        pct: [30, 55] },
  { label: "精确抽帧",            pct: [55, 72] },
  { label: "GPT-4o 分析关键帧",   pct: [72, 100] },
];

function stageIdx(progress) {
  for (let i = STAGES.length - 1; i >= 0; i--) {
    if (progress >= STAGES[i].pct[0]) return i;
  }
  return 0;
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(2).padStart(5, "0");
  return `${m}:${s}`;
}

function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

/* ══════════════════════════════════════════════════════ */
export default function KeyframeExtractor() {
  const [file, setFile]         = useState(null);
  const [preview, setPreview]   = useState(null);
  const [threshold, setThreshold] = useState(0.40);
  const [maxFrames, setMaxFrames] = useState(12);
  const [phase, setPhase]       = useState("upload"); // upload | processing | done | failed
  const [progress, setProgress] = useState(0);
  const [stage, setStage]       = useState("");
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [copied, setCopied]     = useState(false);

  const fileInputRef   = useRef(null);
  const dragCounter    = useRef(0);
  const previewUrlRef  = useRef(null);
  const pollTimer      = useRef(null);
  const jobIdRef       = useRef(null);

  const revokePreview = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  };

  const pickFile = (f) => {
    if (!f || !f.type.startsWith("video/")) return;
    revokePreview();
    const url = URL.createObjectURL(f);
    previewUrlRef.current = url;
    setFile(f);
    setPreview(url);
    setPhase("upload");
    setResult(null);
    setError(null);
  };

  const onFileChange = (e) => { pickFile(e.target.files?.[0]); e.target.value = ""; };

  const onDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current += 1;
    if ([...e.dataTransfer.items].some(i => i.type.startsWith("video/"))) setIsDragging(true);
  };
  const onDragLeave = (e) => { e.preventDefault(); dragCounter.current -= 1; if (dragCounter.current === 0) setIsDragging(false); };
  const onDragOver  = (e) => e.preventDefault();
  const onDrop      = (e) => { e.preventDefault(); dragCounter.current = 0; setIsDragging(false); pickFile(e.dataTransfer.files?.[0]); };

  const stopPoll = () => { if (pollTimer.current) { clearInterval(pollTimer.current); pollTimer.current = null; } };

  const poll = useCallback(async (jobId) => {
    try {
      const { data } = await axios.get(`/api/keyframes/${jobId}`, { headers: authHeader() });
      setProgress(data.progress || 0);
      setStage(data.stage || "");
      if (data.status === "completed") {
        stopPoll();
        setResult(data.result);
        setPhase("done");
      } else if (data.status === "failed") {
        stopPoll();
        setError(data.error || "处理失败");
        setPhase("failed");
      }
    } catch (e) {
      stopPoll();
      setError(e.response?.data?.detail || "轮询失败");
      setPhase("failed");
    }
  }, []);

  const startJob = async () => {
    if (!file) return;
    setPhase("processing");
    setProgress(5);
    setStage("上传中...");
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("threshold", threshold);
      fd.append("max_frames", maxFrames);
      const { data } = await axios.post("/api/keyframes/start", fd, {
        headers: { ...authHeader(), "Content-Type": "multipart/form-data" },
      });
      jobIdRef.current = data.job_id;
      setStage("分析启动...");
      pollTimer.current = setInterval(() => poll(data.job_id), POLL_MS);
    } catch (e) {
      setError(e.response?.data?.detail || "上传失败");
      setPhase("failed");
    }
  };

  const reset = () => {
    stopPoll();
    revokePreview();
    setFile(null); setPreview(null);
    setPhase("upload"); setProgress(0); setStage("");
    setResult(null); setError(null);
    jobIdRef.current = null;
  };

  const downloadJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `keyframes_${Date.now()}.json`;
    a.click(); URL.revokeObjectURL(url);
  };

  const copyAnalysis = () => {
    if (!result?.gpt4o_analysis) return;
    navigator.clipboard.writeText(result.gpt4o_analysis);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /* ── Render ── */
  return (
    <div className="kf-wrap">

      {/* ── Upload Zone ── */}
      {(phase === "upload" || phase === "failed") && (
        <>
          <div
            className={`kf-dropzone ${isDragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
            onClick={() => !file && fileInputRef.current?.click()}
            onDragEnter={onDragEnter} onDragLeave={onDragLeave}
            onDragOver={onDragOver}   onDrop={onDrop}
          >
            <input type="file" accept="video/*" ref={fileInputRef} onChange={onFileChange} style={{ display: "none" }} />
            {isDragging && <div className="kf-drag-overlay"><UploadIcon size={16}/>松开上传视频</div>}

            {file ? (
              <div className="kf-file-preview">
                {preview && <video src={preview} className="kf-video-thumb" muted />}
                <div className="kf-file-info">
                  <div className="kf-file-name">{file.name}</div>
                  <div className="kf-file-meta">{fmtSize(file.size)}</div>
                </div>
                <button className="kf-change-btn" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>更换</button>
              </div>
            ) : (
              <div className="kf-empty">
                <FilmIcon size={28} stroke={1.5} />
                <div className="kf-empty-title">拖入视频或点击上传</div>
                <div className="kf-empty-hint">MP4 / MOV / AVI · 最大 500MB</div>
              </div>
            )}
          </div>

          {/* ── Settings ── */}
          <div className="kf-settings">
            <div className="kf-setting-item">
              <label>场景阈值</label>
              <div className="kf-slider-row">
                <input type="range" min="0.10" max="0.80" step="0.05"
                  value={threshold} onChange={e => setThreshold(parseFloat(e.target.value))} />
                <span className="kf-setting-val">{threshold.toFixed(2)}</span>
              </div>
              <div className="kf-setting-hint">越小越多帧 · 推荐 0.35–0.45</div>
            </div>
            <div className="kf-setting-item">
              <label>最大帧数</label>
              <div className="kf-slider-row">
                <input type="range" min="4" max="20" step="1"
                  value={maxFrames} onChange={e => setMaxFrames(parseInt(e.target.value))} />
                <span className="kf-setting-val">{maxFrames}</span>
              </div>
              <div className="kf-setting-hint">发送给 GPT-4o 的最多帧数</div>
            </div>
          </div>

          {phase === "failed" && error && (
            <div className="kf-error-bar"><AlertIcon size={14}/>{error}</div>
          )}

          <button className="kf-start-btn" onClick={startJob} disabled={!file}>
            <ScanIcon size={14}/>提取关键帧并分析
          </button>
        </>
      )}

      {/* ── Processing ── */}
      {phase === "processing" && (
        <div className="kf-processing">
          <div className="kf-prog-header">
            <span className="kf-prog-label">{stage}</span>
            <span className="kf-prog-pct">{progress}%</span>
          </div>
          <div className="kf-prog-track"><div className="kf-prog-bar" style={{ width: `${progress}%` }} /></div>
          <div className="kf-stages">
            {STAGES.map((s, i) => {
              const cur = stageIdx(progress);
              const state = i < cur ? "done" : i === cur ? "active" : "pending";
              return (
                <div key={i} className={`kf-stage-item ${state}`}>
                  <div className="kf-stage-dot" />
                  <span>{s.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Done ── */}
      {phase === "done" && result && (
        <div className="kf-result">
          {/* Meta card */}
          <div className="kf-meta-card">
            <div className="kf-meta-item"><span>时长</span><strong>{result.meta.duration_sec}s</strong></div>
            <div className="kf-meta-item"><span>分辨率</span><strong>{result.meta.width}×{result.meta.height}</strong></div>
            <div className="kf-meta-item"><span>帧率</span><strong>{result.meta.fps} fps</strong></div>
            <div className="kf-meta-item"><span>大小</span><strong>{fmtSize(result.meta.size_bytes)}</strong></div>
            <div className="kf-meta-item"><span>检测源</span><strong>{result.extraction.source === "scene_detection" ? "场景检测" : "均匀采样"}</strong></div>
            <div className="kf-meta-item"><span>帧数</span><strong>{result.extraction.frame_count}</strong></div>
          </div>

          {/* Timeline */}
          <div className="kf-section-title"><FilmIcon size={13}/>关键帧时间轴</div>
          <div className="kf-timeline">
            <div className="kf-timeline-bar">
              {result.frames.map((f) => {
                const pct = result.meta.duration_sec > 0
                  ? (f.timestamp_sec / result.meta.duration_sec) * 100 : 0;
                return (
                  <div key={f.index} className="kf-marker" style={{ left: `${pct}%` }}
                    title={`帧 ${f.index}  ${fmtTime(f.timestamp_sec)}`}>
                    <div className="kf-marker-line" />
                    <div className="kf-marker-label">{fmtTime(f.timestamp_sec)}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Timestamps list */}
          <div className="kf-ts-grid">
            {result.frames.map((f) => (
              <div key={f.index} className="kf-ts-chip">
                <span className="kf-ts-idx">#{f.index}</span>
                <span className="kf-ts-val">{fmtTime(f.timestamp_sec)}</span>
              </div>
            ))}
          </div>

          {/* GPT-4o analysis */}
          {result.gpt4o_analysis && (
            <>
              <div className="kf-section-title"><ScanIcon size={13}/>GPT-4o 分析结果</div>
              <div className="kf-analysis-box">
                <p>{result.gpt4o_analysis}</p>
                <button className="kf-copy-btn" onClick={copyAnalysis}>
                  {copied ? <><CheckIcon size={12}/>已复制</> : "复制文本"}
                </button>
              </div>
            </>
          )}

          {/* Actions */}
          <div className="kf-actions">
            <button className="kf-dl-btn" onClick={downloadJson}>
              <DownloadIcon size={13}/>下载 JSON
            </button>
            <button className="kf-reset-btn" onClick={reset}>重新分析</button>
          </div>
        </div>
      )}
    </div>
  );
}
