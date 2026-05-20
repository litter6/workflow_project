import { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import "./VideoProcessor.css";

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("auth_token") || ""}` });

/* ─── SVG Icon System ─────────────────────────────────── */
const Ico = ({ size = 14, stroke = 2, children }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
    style={{ flexShrink: 0 }}>
    {children}
  </svg>
);

const VideoIcon    = (p) => <Ico {...p}><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></Ico>;
const ZapIcon      = (p) => <Ico {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></Ico>;
const CheckIcon    = (p) => <Ico {...p}><polyline points="20 6 9 17 4 12"/></Ico>;
const DownloadIcon = (p) => <Ico {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></Ico>;
const CopyIcon     = (p) => <Ico {...p}><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></Ico>;
const MicIcon      = (p) => <Ico {...p}><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></Ico>;
const FileIcon     = (p) => <Ico {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></Ico>;
const AlertIcon    = (p) => <Ico {...p}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Ico>;
const CheckCircle  = (p) => <Ico {...p}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></Ico>;
const ChevDownIcon = (p) => <Ico {...p}><polyline points="6 9 12 15 18 9"/></Ico>;
const ChevUpIcon   = (p) => <Ico {...p}><polyline points="18 15 12 9 6 15"/></Ico>;

const Spinner = () => <div className="vp-spinner" />;

/* ─── Pipeline stage definitions ─── */
const PIPELINE_STAGES = [
  { label: "FFmpeg 拆解音频轨道",    range: [8,  22] },
  { label: "Whisper 识别语音字幕",   range: [22, 40] },
  { label: "GPT-4o 分析视频卖点",    range: [40, 60] },
  { label: "GPT-4o 生成营销文案",    range: [60, 70] },
  { label: "FFmpeg 自动剪辑重封装",  range: [70, 80] },
  { label: "自动烧录字幕与文字叠加", range: [80, 93] },
  { label: "FFmpeg 混入背景音乐",    range: [93, 98] },
  { label: "导出宣传片",             range: [98, 100] },
];

function stageIndex(stageName) {
  if (!stageName) return -1;
  return PIPELINE_STAGES.findIndex(s => stageName.includes(s.label.slice(0, 6)));
}

/* ══════════════════════════════════════════════════════ */
export default function VideoProcessor() {
  const [file, setFile]         = useState(null);
  const [preview, setPreview]   = useState(null);
  const [phase, setPhase]       = useState("upload"); // upload | uploading | processing | done | failed
  const [jobId, setJobId]       = useState(null);
  const [jobData, setJobData]   = useState(null);
  const [error, setError]       = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [copied, setCopied]     = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [downloading, setDownloading]       = useState(false);

  const fileInputRef   = useRef(null);
  const dragCounterRef = useRef(0);
  const previewUrlRef  = useRef(null);
  const pollTimerRef   = useRef(null);
  const jobIdRef       = useRef(null);

  /* ── Preview management ── */
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
    setError(null);
    setJobId(null);
    setJobData(null);
    setPhase("upload");
  };

  /* ── Drag & drop ── */
  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounterRef.current += 1;
    if (e.dataTransfer.items?.[0]?.type.startsWith("video/")) setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) setIsDragging(false);
  };
  const handleDrop = (e) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  };

  /* ── Poll job status ── */
  const pollJob = useCallback(async (id) => {
    try {
      const res = await axios.get(`/api/pipeline/job/${id}`, { headers: authHeader() });
      const d = res.data;
      setJobData(d);
      if (d.status === "completed") {
        setPhase("done");
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      } else if (d.status === "failed") {
        setPhase("failed");
        setError(d.error_msg || "处理失败，请重试");
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    } catch (e) {
      // network hiccup, keep polling
    }
  }, []);

  useEffect(() => {
    if (phase === "processing" && jobId) {
      jobIdRef.current = jobId;
      pollJob(jobId);
      pollTimerRef.current = setInterval(() => pollJob(jobIdRef.current), 2000);
    }
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [phase, jobId, pollJob]);

  /* ── Upload + dispatch ── */
  const handleStart = async () => {
    if (!file) return;
    setError(null);
    setPhase("uploading");
    try {
      const form = new FormData();
      form.append("video", file);
      const res = await axios.post("/api/pipeline/upload", form, {
        headers: { ...authHeader() },
        timeout: 120000,
      });
      const { job_id } = res.data;
      setJobId(job_id);
      jobIdRef.current = job_id;
      setJobData({ status: "pending", stage: "等待处理", progress: 0 });
      setPhase("processing");
    } catch (e) {
      setPhase("upload");
      const detail = e.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "上传失败，请检查后端服务是否启动");
    }
  };

  /* ── Download processed video ── */
  const handleDownload = async () => {
    if (!jobId || downloading) return;
    setDownloading(true);
    try {
      const res = await axios.get(`/api/pipeline/download/${jobId}`, {
        headers: authHeader(),
        responseType: "blob",
        timeout: 120000,
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `processed_${file?.name || "video.mp4"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError("下载失败，请重试");
    } finally {
      setDownloading(false);
    }
  };

  /* ── Download SRT ── */
  const handleDownloadSrt = () => {
    if (!jobData?.srt_content) return;
    const blob = new Blob([jobData.srt_content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "subtitles.srt";
    a.click();
    URL.revokeObjectURL(url);
  };

  /* ── Copy marketing copy ── */
  const copyMarketing = () => {
    if (!jobData?.marketing_copy) return;
    navigator.clipboard.writeText(jobData.marketing_copy).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  /* ── Reset ── */
  const handleReset = () => {
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
    revokePreview();
    setFile(null); setPreview(null); setPhase("upload");
    setJobId(null); setJobData(null); setError(null);
    setShowTranscript(false);
  };

  const progress = jobData?.progress ?? 0;
  const currentStage = jobData?.stage ?? "";
  const curStageIdx = stageIndex(currentStage);

  /* ══════════════════════════════════════════════════════ */
  return (
    <div className="vp-wrap">

      {/* ─── Upload phase ─── */}
      {(phase === "upload" || phase === "uploading") && (
        <>
          <div
            className={`vp-dropzone ${isDragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => phase === "upload" && fileInputRef.current?.click()}
          >
            {isDragging && (
              <div className="vp-drag-overlay">
                <VideoIcon size={18}/>松开上传视频
              </div>
            )}
            <input
              ref={fileInputRef} type="file" accept="video/*" style={{ display: "none" }}
              onChange={e => { pickFile(e.target.files?.[0]); e.target.value = ""; }}
            />
            {file ? (
              <div className="vp-file-info">
                <video src={preview} className="vp-preview" controls onClick={e => e.stopPropagation()} />
                <div className="vp-file-meta">
                  <VideoIcon size={12}/>
                  <span className="vp-filename">{file.name}</span>
                  <button
                    className="vp-change-btn" disabled={phase === "uploading"}
                    onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}
                  >更换</button>
                </div>
              </div>
            ) : (
              <div className="vp-empty">
                <div className="vp-empty-icon"><VideoIcon size={22} stroke={1.5}/></div>
                <p>拖入或点击上传视频</p>
                <span>MP4 / MOV / AVI · 最大 500MB</span>
              </div>
            )}
          </div>

          <button
            className={`vp-analyze-btn ${phase === "uploading" ? "loading" : ""}`}
            onClick={handleStart}
            disabled={!file || phase === "uploading"}
          >
            {phase === "uploading"
              ? <><Spinner />&nbsp;正在上传，分配处理任务…</>
              : <><ZapIcon size={15}/>&nbsp;启动 AI 视频处理流水线</>
            }
          </button>
        </>
      )}

      {/* ─── Processing phase ─── */}
      {phase === "processing" && (
        <div className="vp-pipeline-wrap">
          <div className="vp-file-badge">
            <VideoIcon size={13}/>
            <span>{file?.name}</span>
          </div>

          {/* Progress bar */}
          <div className="vp-progress-block">
            <div className="vp-progress-header">
              <span className="vp-progress-stage">{currentStage || "正在处理…"}</span>
              <span className="vp-progress-pct">{progress}%</span>
            </div>
            <div className="vp-progress-bar">
              <div className="vp-progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Stage timeline */}
          <div className="vp-steps">
            {PIPELINE_STAGES.map((s, idx) => {
              const isDone   = progress >= s.range[1];
              const isActive = !isDone && progress >= s.range[0];
              return (
                <div key={idx} className={`vp-step ${isActive ? "active" : ""} ${isDone ? "done" : ""}`}>
                  <span className="vp-step-dot">
                    {isDone   ? <CheckIcon size={10}/> : null}
                    {isActive ? <div className="vp-spinner-sm" /> : null}
                  </span>
                  <span>{s.label}</span>
                </div>
              );
            })}
          </div>

          <p className="vp-pipeline-hint">后端正在处理中，请耐心等待，完成后自动显示结果</p>
        </div>
      )}

      {/* ─── Failed phase ─── */}
      {phase === "failed" && (
        <div className="vp-pipeline-wrap">
          <div className="vp-file-badge">
            <VideoIcon size={13}/><span>{file?.name}</span>
          </div>
          <div className="vp-error">
            <AlertIcon size={14}/>
            <div>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>处理失败</div>
              {error}
            </div>
          </div>
          <button className="vp-analyze-btn" onClick={handleReset}>
            重新上传
          </button>
        </div>
      )}

      {/* ─── Done phase ─── */}
      {phase === "done" && jobData && (
        <div className="vp-pipeline-wrap">
          <div className="vp-file-badge">
            <VideoIcon size={13}/><span>{file?.name}</span>
            <button className="vp-change-btn" onClick={handleReset}>重新处理</button>
          </div>

          {/* Progress bar - completed */}
          <div className="vp-progress-block">
            <div className="vp-progress-header">
              <span className="vp-progress-stage" style={{ color: "#15803d" }}>
                <CheckCircle size={12}/>&nbsp;宣传片处理完成
              </span>
              <span className="vp-progress-pct">100%</span>
            </div>
            <div className="vp-progress-bar">
              <div className="vp-progress-fill done" style={{ width: "100%" }} />
            </div>
          </div>

          <div className="vp-result">
            {/* Video download block */}
            <div className="vp-result-block">
              <div className="vp-result-label">
                <CheckCircle size={13}/>
                已生成电商宣传片（含字幕 &amp; 文字叠加）
              </div>
              {preview && (
                <video src={preview} controls className="vp-result-video" />
              )}
              <div className="vp-result-actions">
                <button
                  className="vp-download-btn"
                  onClick={handleDownload}
                  disabled={downloading}
                >
                  {downloading
                    ? <><div className="vp-spinner" style={{ borderTopColor: "#fff", width: 12, height: 12 }} />&nbsp;下载中…</>
                    : <><DownloadIcon size={12}/>&nbsp;下载宣传片</>
                  }
                </button>
                {jobData.srt_content && (
                  <button className="vp-download-btn secondary" onClick={handleDownloadSrt}>
                    <DownloadIcon size={12}/>&nbsp;下载 SRT 字幕
                  </button>
                )}
              </div>
            </div>

            {/* Overlay data */}
            {jobData.overlay && (jobData.overlay.headline || jobData.overlay.cta) && (
              <div className="vp-result-block">
                <div className="vp-result-label">
                  <ZapIcon size={13}/>视频文字叠加数据
                </div>
                <div style={{ padding: "10px 13px", background: "#fff", fontSize: 13, lineHeight: 1.8 }}>
                  {jobData.overlay.headline && (
                    <div><strong>主标题：</strong>{jobData.overlay.headline}</div>
                  )}
                  {Array.isArray(jobData.overlay.features) && jobData.overlay.features.length > 0 && (
                    <div><strong>卖点：</strong>{jobData.overlay.features.join(" · ")}</div>
                  )}
                  {jobData.overlay.cta && (
                    <div><strong>行动号召：</strong>{jobData.overlay.cta}</div>
                  )}
                </div>
              </div>
            )}

            {/* Marketing copy */}
            {jobData.marketing_copy && (
              <div className="vp-result-block">
                <div className="vp-result-label">
                  <FileIcon size={13}/>营销文案
                  <button className="vp-copy-btn" onClick={copyMarketing}>
                    <CopyIcon size={11}/>{copied ? "已复制" : "复制"}
                  </button>
                </div>
                <pre className="vp-copy-text">{jobData.marketing_copy}</pre>
              </div>
            )}

            {/* Transcript */}
            {jobData.transcript && (
              <div className="vp-result-block">
                <div className="vp-result-label vp-collapsible" onClick={() => setShowTranscript(v => !v)}>
                  <MicIcon size={13}/>语音转录
                  <span className="vp-toggle-icon" style={{ marginLeft: "auto" }}>
                    {showTranscript ? <ChevUpIcon size={11}/> : <ChevDownIcon size={11}/>}
                  </span>
                </div>
                {showTranscript && <p className="vp-transcript">{jobData.transcript}</p>}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Error (upload/general) ─── */}
      {error && phase !== "failed" && (
        <div className="vp-error">
          <AlertIcon size={14}/>{error}
        </div>
      )}
    </div>
  );
}
