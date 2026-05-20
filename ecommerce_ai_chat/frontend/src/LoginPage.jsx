import { useState } from "react";
import axios from "axios";
import "./LoginPage.css";

const BagIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
    <line x1="3" y1="6" x2="21" y2="6"/>
    <path d="M16 10a4 4 0 0 1-8 0"/>
  </svg>
);
const EyeIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);
const EyeOffIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
);

export default function LoginPage({ onLogin }) {
  const [mode, setMode]         = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const switchMode = (m) => { setMode(m); setError(""); };

  const submit = async () => {
    if (!username.trim() || !password) return;
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(`/api/auth/${mode}`, {
        username: username.trim(),
        password,
      });
      localStorage.setItem("auth_token",    res.data.token);
      localStorage.setItem("auth_username", res.data.username);
      onLogin(res.data.username);
    } catch (e) {
      setError(e.response?.data?.detail || "操作失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => { if (e.key === "Enter") submit(); };

  return (
    <div className="lp-overlay">
      <div className="lp-card">
        <div className="lp-logo-wrap">
          <div className="lp-logo-icon"><BagIcon /></div>
        </div>
        <h1 className="lp-title">电商 AI 内容生成器</h1>
        <p className="lp-sub">AI 驱动 · 多平台 · 一键生成</p>

        <div className="lp-tabs">
          <button className={mode === "login"    ? "active" : ""} onClick={() => switchMode("login")}>登录</button>
          <button className={mode === "register" ? "active" : ""} onClick={() => switchMode("register")}>注册</button>
        </div>

        <input
          className="lp-input"
          placeholder="用户名"
          value={username}
          onChange={e => setUsername(e.target.value)}
          onKeyDown={onKey}
          autoFocus
        />

        <div className="lp-pwd-wrap">
          <input
            className="lp-input"
            type={showPwd ? "text" : "password"}
            placeholder={mode === "register" ? "密码（至少 4 位）" : "密码"}
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={onKey}
            style={{ paddingRight: 44 }}
          />
          <button className="lp-eye-btn" type="button" onClick={() => setShowPwd(v => !v)}>
            {showPwd ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        </div>

        {error && <p className="lp-error">{error}</p>}

        <button
          className="lp-btn"
          onClick={submit}
          disabled={loading || !username.trim() || !password}
        >
          {loading ? <><span className="lp-spinner" />处理中…</> : mode === "login" ? "登录" : "注册账号"}
        </button>
      </div>
    </div>
  );
}
