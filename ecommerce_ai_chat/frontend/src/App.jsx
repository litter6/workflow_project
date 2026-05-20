import { useState, useRef, useEffect, useCallback, Component } from "react";
import axios from "axios";
import PromptBuilder from "./PromptBuilder";
import AnalysisResult from "./AnalysisResult";
import LoginPage from "./LoginPage";
import SessionSidebar from "./SessionSidebar";
import VideoProcessor from "./VideoProcessor";
import KeyframeExtractor from "./KeyframeExtractor";
import "./App.css";

/* ─── SVG Icons ─── */
const Ico = ({ size = 14, stroke = 2, children }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
    style={{ flexShrink: 0 }}>
    {children}
  </svg>
);
const CartIcon    = (p) => <Ico {...p}><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></Ico>;
const PenIcon     = (p) => <Ico {...p}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></Ico>;
const SlidersIcon = (p) => <Ico {...p}><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></Ico>;
const VideoIcon   = (p) => <Ico {...p}><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></Ico>;
const FilmIcon    = (p) => <Ico {...p}><rect x="2" y="2" width="20" height="20" rx="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></Ico>;
const PaperclipIcon = (p) => <Ico {...p}><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></Ico>;
const SparkleIcon = (p) => <Ico {...p}><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></Ico>;
const ZapIcon     = (p) => <Ico {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></Ico>;

const SendIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

/* ─── Constants ─── */
const EXAMPLES = [
  "帮我写一双运动鞋的详情页",
  "夏季连衣裙产品标题",
  "无线耳机的卖点文案",
  "护肤品买家评价回复",
];

const OUTPUT_TYPES = [
  { key: "text",  label: "文案" },
  { key: "image", label: "图片" },
  { key: "video", label: "视频" },
];

const MODELS = [
  { key: "chatgpt",  label: "ChatGPT"     },
  { key: "deepseek", label: "DeepSeek V4" },
];

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("auth_token") || ""}` });

class VideoBoundary extends Component {
  constructor(props) { super(props); this.state = { crashed: false, msg: "" }; }
  static getDerivedStateFromError(err) { return { crashed: true, msg: err?.message || "未知错误" }; }
  componentDidCatch(err) { console.error("[VideoProcessor crashed]", err); }
  render() {
    if (this.state.crashed) {
      return (
        <div style={{
          padding: "20px 16px", textAlign: "center",
          color: "#b91c1c", fontSize: 13, lineHeight: 1.6,
        }}>
          <div style={{ fontSize: 22, marginBottom: 8 }}>⚠️</div>
          视频处理模块发生错误，请刷新页面重试。
          <div style={{ fontSize: 11, color: "#999", marginTop: 6 }}>{this.state.msg}</div>
          <button
            onClick={() => this.setState({ crashed: false, msg: "" })}
            style={{
              marginTop: 12, padding: "6px 16px", borderRadius: 8,
              border: "1px solid #e5e7eb", background: "#fff",
              cursor: "pointer", fontSize: 12,
            }}
          >重试</button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ══════════════════════════════════════════════════════ */
export default function App() {
  const [user, setUser]       = useState(() => localStorage.getItem("auth_username") || null);
  const [sessions, setSessions]   = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const sessionIdRef              = useRef(null);

  const [messages, setMessages]   = useState([]);
  const messagesRef               = useRef([]);

  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [inputMode, setInputMode]     = useState("free");
  const [pendingFiles, setPendingFiles] = useState([]);
  const [isDragging, setIsDragging]   = useState(false);
  const [selectedType, setSelectedType]   = useState("image");
  const [selectedModel, setSelectedModel] = useState("chatgpt");

  const bottomRef    = useRef(null);
  const textareaRef  = useRef(null);
  const fileInputRef = useRef(null);
  const dragCounterRef = useRef(0);
  const saveTimerRef   = useRef(null);

  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { if (user) loadSessions(); }, [user]);

  const loadSessions = async () => {
    try {
      const res = await axios.get("/api/sessions", { headers: authHeader() });
      setSessions(res.data);
      if (res.data.length > 0) selectSession(res.data[0].id);
    } catch (e) { if (e.response?.status === 401) handleLogout(); }
  };

  const selectSession = async (id) => {
    try {
      const res = await axios.get(`/api/sessions/${id}`, { headers: authHeader() });
      setSessionId(id);
      setMessages(res.data.messages || []);
    } catch (e) { if (e.response?.status === 401) handleLogout(); }
  };

  const doSave = useCallback(async (msgs, sid) => {
    if (!sid || msgs.length === 0) return;
    const title = msgs.find(m => m.role === "user")?.content?.slice(0, 30) || "新对话";
    try {
      await axios.put(`/api/sessions/${sid}`, { messages: msgs, title }, { headers: authHeader() });
      setSessions(prev => prev.map(s => s.id === sid ? { ...s, title } : s));
    } catch (e) { if (e.response?.status === 401) handleLogout(); }
  }, []);

  useEffect(() => {
    if (!sessionIdRef.current || messagesRef.current.length === 0) return;
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => doSave(messagesRef.current, sessionIdRef.current), 2000);
    return () => clearTimeout(saveTimerRef.current);
  }, [messages, doSave]);

  const ensureSession = async () => {
    if (sessionIdRef.current) return sessionIdRef.current;
    const res = await axios.post("/api/sessions", {}, { headers: authHeader() });
    setSessionId(res.data.id);
    setSessions(prev => [res.data, ...prev]);
    return res.data.id;
  };

  const handleNew    = () => { setMessages([]); setSessionId(null); setInput(""); clearPendingFiles(); };
  const handleDelete = async (id) => {
    try {
      await axios.delete(`/api/sessions/${id}`, { headers: authHeader() });
      setSessions(prev => prev.filter(s => s.id !== id));
      if (sessionIdRef.current === id) { setMessages([]); setSessionId(null); }
    } catch (e) { /* ignore */ }
  };
  const handleLogout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_username");
    setUser(null); setMessages([]); setSessions([]); setSessionId(null);
  };

  const attachFile = useCallback((file) => {
    if (!file) return;
    const isImage = file.type.startsWith("image/");
    const isVideo = file.type.startsWith("video/");
    if (!isImage && !isVideo) return;
    setPendingFiles(prev => [...prev, { file, previewUrl: URL.createObjectURL(file), isVideo }]);
  }, []);

  const removeFile = (idx) => {
    setPendingFiles(prev => {
      URL.revokeObjectURL(prev[idx].previewUrl);
      return prev.filter((_, i) => i !== idx);
    });
  };

  const clearPendingFiles = () => {
    pendingFiles.forEach(f => URL.revokeObjectURL(f.previewUrl));
    setPendingFiles([]);
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounterRef.current += 1;
    const items = Array.from(e.dataTransfer.items || []);
    if (items.some(i => i.type.startsWith("image/") || i.type.startsWith("video/"))) setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) setIsDragging(false);
  };
  const handleDragOver = (e) => e.preventDefault();
  const handleDrop     = (e) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    Array.from(e.dataTransfer.files || []).forEach(attachFile);
  };

  const buildHistory = (msgs) => {
    const pairs = [];
    for (let i = 0; i < msgs.length; i++) {
      if (msgs[i].role === "user") {
        const next = msgs[i + 1];
        if (next?.role === "analysis") {
          const { ref_image_b64, ref_image_mime, ...ctxText } = next.analysis?.context || {};
          pairs.push({ user_text: msgs[i].content, context: ctxText, result: next.result || null });
        }
      }
    }
    return pairs;
  };

  const send = async (text, extraFiles = []) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;

    const files = extraFiles.length > 0 ? extraFiles : pendingFiles;
    const firstThumb = files[0]?.previewUrl || null;
    const fileCount  = files.length;
    const analysisMsgIndex = messagesRef.current.length + 1;

    setMessages(prev => [...prev, { role: "user", content: msg, refThumb: firstThumb, fileCount }]);
    setInput("");
    if (extraFiles.length === 0) clearPendingFiles();
    setLoading(true);
    textareaRef.current?.focus();

    const outputType = selectedType;
    const model      = selectedModel;

    try {
      await ensureSession();

      const form = new FormData();
      form.append("text", msg);
      form.append("history", JSON.stringify(buildHistory(messagesRef.current)));
      files.forEach(({ file }) => form.append("ref_files", file));

      const analyzeRes = await axios.post("/api/analyze", form, { timeout: 60000 });

      setMessages(prev => [...prev, {
        role: "analysis",
        analysis: analyzeRes.data,
        generating: { type: outputType, model },
        result: null,
        outputType,
        model,
      }]);

      try {
        const genRes = await axios.post("/api/generate", {
          context: analyzeRes.data.context,
          output_type: outputType,
          model,
        }, { timeout: 180000 });

        setMessages(prev => prev.map((m, i) =>
          i === analysisMsgIndex ? { ...m, generating: null, result: genRes.data } : m
        ));
      } catch (genE) {
        const detail = genE.response?.data?.detail || "生成失败，请稍后重试。";
        setMessages(prev => prev.map((m, i) =>
          i === analysisMsgIndex ? { ...m, generating: null, result: { error: detail } } : m
        ));
      }
    } catch (e) {
      const detail = e.response?.data?.detail || "分析失败，请检查后端服务。";
      setMessages(prev => [...prev, { role: "error", content: detail }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  const handleRegenerate = async (msgIndex) => {
    const msg = messages[msgIndex];
    if (!msg || msg.generating) return;
    const outputType = msg.outputType || "text";
    const model      = msg.model      || "chatgpt";

    setMessages(prev => prev.map((m, i) =>
      i === msgIndex ? { ...m, generating: { type: outputType, model }, result: null } : m
    ));
    try {
      const res = await axios.post("/api/generate", {
        context: msg.analysis.context, output_type: outputType, model,
      }, { timeout: 180000 });
      setMessages(prev => prev.map((m, i) => i === msgIndex ? { ...m, generating: null, result: res.data } : m));
    } catch (e) {
      const detail = e.response?.data?.detail || "生成失败";
      setMessages(prev => prev.map((m, i) => i === msgIndex ? { ...m, generating: null, result: { error: detail } } : m));
    }
  };

  const handleCombine = async (msgIndex, file, text) => {
    const msg = messages[msgIndex];
    if (!msg || msg.generating || !msg.result?.url) return;
    setMessages(prev => prev.map((m, i) =>
      i === msgIndex ? { ...m, generating: { type: "image", model: "chatgpt" }, result: null } : m
    ));
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const b64 = btoa(Array.from(bytes, b => String.fromCharCode(b)).join(""));
      const res = await axios.post("/api/combine", {
        image1_b64: msg.result.url,
        image2_b64: b64,
        image2_mime: file.type || "image/jpeg",
        context: msg.analysis?.context || {},
        extra_text: text || "",
      }, { timeout: 180000 });
      setMessages(prev => prev.map((m, i) => i === msgIndex ? { ...m, generating: null, result: res.data } : m));
    } catch (e) {
      const detail = e.response?.data?.detail || "合并生成失败";
      setMessages(prev => prev.map((m, i) => i === msgIndex ? { ...m, generating: null, result: { error: detail } } : m));
    }
  };

  if (!user) return <LoginPage onLogin={setUser} />;

  return (
    <div className="app">
      <header className="header">
        <div className="header-logo"><CartIcon size={16}/></div>
        <div className="header-text">
          <span className="header-title">电商 AI 内容生成器</span>
          <span className="header-subtitle">分析 → 提炼 → 一键生成</span>
        </div>
        <span className="header-tag"><ZapIcon size={11}/>GPT-4o · DeepSeek V4</span>
      </header>

      <div className="app-body">
        <SessionSidebar
          username={user} sessions={sessions} currentId={sessionId}
          onSelect={selectSession} onNew={handleNew}
          onDelete={handleDelete} onLogout={handleLogout}
        />

        <div className="app-main">
          <div className="chat-area">
            <div className="chat-inner">
              {messages.length === 0 && (
                <div className="empty-hint">
                  <div className="empty-hint-icon">
                    <SparkleIcon size={28} stroke={1.5}/>
                  </div>
                  <h2>输入内容，AI 自动分析并生成电商素材</h2>
                  <p>支持多图 / 视频，选择生成类型后一键直达结果</p>
                  <div className="example-chips">
                    {EXAMPLES.map(ex => (
                      <button key={ex} className="chip" onClick={() => send(ex)}>{ex}</button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => {
                if (msg.role === "user") return (
                  <div key={i} className="bubble user">
                    {msg.refThumb && (
                      <div className="user-thumb-wrap">
                        <img src={msg.refThumb} className="user-ref-thumb" alt="参考" />
                        {msg.fileCount > 1 && <span className="user-file-count">+{msg.fileCount - 1}</span>}
                      </div>
                    )}
                    <span>{msg.content}</span>
                  </div>
                );
                if (msg.role === "error") return (
                  <div key={i} className="bubble error">{msg.content}</div>
                );
                if (msg.role === "analysis") return (
                  <div key={i} className="bubble assistant">
                    <AnalysisResult
                      analysis={msg.analysis}
                      generating={msg.generating}
                      result={msg.result}
                      outputType={msg.outputType}
                      model={msg.model}
                      onRegenerate={() => handleRegenerate(i)}
                      onReanalyze={(files, text) => send(text || "基于新参考图重新分析", files)}
                      onCombine={(file, text) => handleCombine(i, file, text)}
                    />
                  </div>
                );
                return null;
              })}

              {loading && (
                <div className="bubble assistant">
                  <div className="analyzing-tip">
                    <div className="bubble loading">
                      <span /><span /><span />
                    </div>
                    <span>正在分析并生成中…</span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* ── 输入区 ── */}
          <div className="input-area">
            <div className="input-tabs">
              <button className={`input-tab ${inputMode === "free" ? "active" : ""}`} onClick={() => setInputMode("free")}>
                <PenIcon size={12}/>自由输入
              </button>
              <button className={`input-tab ${inputMode === "builder" ? "active" : ""}`} onClick={() => setInputMode("builder")}>
                <SlidersIcon size={12}/>标准配置
              </button>
              <button className={`input-tab ${inputMode === "video" ? "active" : ""}`} onClick={() => setInputMode("video")}>
                <VideoIcon size={12}/>视频处理
              </button>
              <button className={`input-tab ${inputMode === "keyframe" ? "active" : ""}`} onClick={() => setInputMode("keyframe")}>
                <FilmIcon size={12}/>关键帧分析
              </button>
            </div>

            {inputMode === "keyframe" ? (
              <KeyframeExtractor />
            ) : inputMode === "video" ? (
              <VideoBoundary><VideoProcessor /></VideoBoundary>
            ) : inputMode === "free" ? (
              <>
                <div className="input-gen-row">
                  <div className="input-gen-group">
                    {OUTPUT_TYPES.map(({ key, label }) => (
                      <button key={key}
                        className={`input-gen-btn ${selectedType === key ? "active" : ""}`}
                        onClick={() => setSelectedType(key)} disabled={loading}
                      >{label}</button>
                    ))}
                  </div>
                  <div className="input-gen-group">
                    {MODELS.map(({ key, label }) => (
                      <button key={key}
                        className={`input-model-btn ${selectedModel === key ? "active" : ""}`}
                        onClick={() => setSelectedModel(key)} disabled={loading}
                      >{label}</button>
                    ))}
                  </div>
                </div>

                <div
                  className={`input-box ${isDragging ? "dragging" : ""}`}
                  onDragEnter={handleDragEnter} onDragLeave={handleDragLeave}
                  onDragOver={handleDragOver}   onDrop={handleDrop}
                >
                  {isDragging && (
                    <div className="drag-overlay"><span>松开上传图片 / 视频</span></div>
                  )}

                  {pendingFiles.length > 0 && (
                    <div className="pending-files">
                      {pendingFiles.map((f, idx) => (
                        <div key={idx} className="pending-file-item">
                          {f.isVideo
                            ? <div className="pending-video-icon"><VideoIcon size={20}/></div>
                            : <img src={f.previewUrl} className="pending-thumb" alt="参考" />
                          }
                          <button className="pending-file-remove" onClick={() => removeFile(idx)}>✕</button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="input-row">
                    <textarea
                      ref={textareaRef}
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder={isDragging ? "" : "输入内容，可拖拽多张图片或视频…"}
                      rows={2}
                    />
                    <div className="input-btns">
                      <input type="file" accept="image/*,video/*" multiple style={{ display:"none" }} ref={fileInputRef}
                        onChange={e => { Array.from(e.target.files || []).forEach(attachFile); e.target.value = ""; }} />
                      <button className="attach-btn" onClick={() => fileInputRef.current?.click()} title="上传图片/视频">
                        <PaperclipIcon size={15}/>
                      </button>
                      <button className="send-btn" onClick={() => send()} disabled={loading || !input.trim()}>
                        <SendIcon />
                      </button>
                    </div>
                  </div>
                </div>
                <p className="input-hint">Enter 发送 · Shift+Enter 换行 · 拖入多张图片或视频</p>
              </>
            ) : (
              <PromptBuilder onSend={prompt => { send(prompt); setInputMode("free"); }} disabled={loading} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
