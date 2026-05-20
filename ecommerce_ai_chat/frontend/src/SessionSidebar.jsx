import "./SessionSidebar.css";

const LogOutIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

const PlusIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/>
    <line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);

const XIcon = () => (
  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

const MessageIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);

export default function SessionSidebar({
  username, sessions, currentId,
  onSelect, onNew, onDelete, onLogout,
}) {
  const fmt = (iso) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60)     return "刚刚";
    if (diff < 3600)   return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400)  return `${Math.floor(diff / 3600)} 小时前`;
    return d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
  };

  return (
    <div className="ss-wrap">
      <div className="ss-user">
        <div className="ss-avatar">{username?.[0]?.toUpperCase() || "U"}</div>
        <span className="ss-username">{username}</span>
        <button className="ss-logout" onClick={onLogout} title="退出登录">
          <LogOutIcon />
        </button>
      </div>

      <button className="ss-new" onClick={onNew}>
        <PlusIcon /> 新对话
      </button>

      <div className="ss-list">
        {sessions.length === 0 && (
          <p className="ss-empty">暂无历史对话</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`ss-item ${s.id === currentId ? "active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <span className="ss-item-icon"><MessageIcon /></span>
            <div className="ss-item-body">
              <div className="ss-item-title">{s.title || "新对话"}</div>
              <div className="ss-item-time">{fmt(s.updated_at)}</div>
            </div>
            <button
              className="ss-item-del"
              onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
              title="删除"
            ><XIcon /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
