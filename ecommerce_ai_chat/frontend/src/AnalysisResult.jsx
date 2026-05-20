import { useState, useRef } from "react";
import "./AnalysisResult.css";

const TYPE_LABEL = { text: "📝 文案", image: "🖼 图片", video: "🎬 视频" };
const MODEL_LABEL = { chatgpt: "ChatGPT", deepseek: "DeepSeek" };

export default function AnalysisResult({
  analysis, generating, result,
  outputType, model,
  onRegenerate, onReanalyze, onCombine,
}) {
  const [reImg, setReImg]       = useState(null);
  const [rePreview, setRePreview] = useState(null);
  const [reText, setReText]     = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const reFileRef      = useRef(null);
  const dragCounterRef = useRef(0);

  const pickRe = (file) => {
    if (!file || !file.type.startsWith("image/")) return;
    if (rePreview) URL.revokeObjectURL(rePreview);
    setReImg(file);
    setRePreview(URL.createObjectURL(file));
  };
  const clearRe = () => {
    if (rePreview) URL.revokeObjectURL(rePreview);
    setReImg(null); setRePreview(null); setReText("");
  };

  const handleDragEnter = (e) => {
    e.preventDefault(); dragCounterRef.current += 1;
    if (e.dataTransfer.items?.[0]?.type.startsWith("image/")) setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault(); dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) setIsDragging(false);
  };
  const handleDrop = (e) => {
    e.preventDefault(); dragCounterRef.current = 0; setIsDragging(false);
    pickRe(e.dataTransfer.files?.[0]);
  };

  const submitRe = () => {
    if (!reImg) return;
    onReanalyze([{ file: reImg, previewUrl: rePreview, isVideo: false }], reText);
    clearRe();
  };

  const ctx = analysis?.context;
  if (!ctx) return null;

  const isGenerating = !!generating;
  const genLabel = TYPE_LABEL[generating?.type] ?? "生成";

  return (
    <div className="ar-wrap">
      {/* 分析结果 */}
      <div className="ar-section">
        <div className="ar-section-header">
          <span className="ar-section-title">🔍 分析结果</span>
          <div className="ar-meta">
            {outputType && (
              <span className="ar-meta-badge">{TYPE_LABEL[outputType]} · {MODEL_LABEL[model] || model}</span>
            )}
            <button className="ar-regen-btn" onClick={onRegenerate} disabled={isGenerating}>
              ↻ 重新生成
            </button>
          </div>
        </div>

        {ctx.keywords?.length > 0 && (
          <div className="ar-row">
            <span className="ar-label">关键词</span>
            <div className="ar-keywords">
              {ctx.keywords.map(k => <span key={k} className="ar-keyword">{k}</span>)}
            </div>
          </div>
        )}
        {ctx.product_type && <div className="ar-row"><span className="ar-label">产品类型</span><span className="ar-value">{ctx.product_type}</span></div>}
        {ctx.target_audience && <div className="ar-row"><span className="ar-label">目标客群</span><span className="ar-value">{ctx.target_audience}</span></div>}
        {ctx.core_appeal && <div className="ar-row"><span className="ar-label">核心卖点</span><span className="ar-value">{ctx.core_appeal}</span></div>}
        {ctx.emotional_trigger && <div className="ar-row"><span className="ar-label">情感触发</span><span className="ar-value">{ctx.emotional_trigger}</span></div>}
        {ctx.brand_positioning && <div className="ar-row"><span className="ar-label">品牌定位</span><span className="ar-value">{ctx.brand_positioning}</span></div>}
        {ctx.scene && <div className="ar-row"><span className="ar-label">营销场景</span><span className="ar-value">{ctx.scene}</span></div>}
        {ctx.optimization_direction && (
          <div className="ar-row ar-row-col">
            <span className="ar-label">🔄 优化方向</span>
            <p className="ar-optimize">{ctx.optimization_direction}</p>
          </div>
        )}
        {ctx.image_analysis && (
          <div className="ar-row ar-row-col">
            <span className="ar-label">📷 参考图分析</span>
            <p className="ar-img-analysis">{ctx.image_analysis}</p>
          </div>
        )}
        {ctx.ecommerce_prompt && (
          <div className="ar-row ar-row-col">
            <span className="ar-label">电商提示词</span>
            <p className="ar-eprompt">{ctx.ecommerce_prompt}</p>
          </div>
        )}
      </div>

      {/* 生成中提示 */}
      {isGenerating && (
        <div className="ar-generating">
          <span className="ar-gen-dot" /><span className="ar-gen-dot" /><span className="ar-gen-dot" />
          <span>{genLabel}中，请稍候…</span>
        </div>
      )}

      {/* 生成结果 */}
      {result && (
        <div className="ar-result">
          {result.error ? (
            <p className="ar-result-error">{result.error}</p>
          ) : result.type === "text" ? (
            <div className="ar-result-text">
              <div className="ar-result-label">✅ 生成文案</div>
              <pre>{result.content}</pre>
            </div>
          ) : result.type === "image" ? (
            <div className="ar-result-media">
              <div className="ar-result-label">✅ 生成图片</div>
              <img src={result.url} alt="生成图片" className="ar-result-img" />
            </div>
          ) : (
            <div className="ar-result-media">
              <div className="ar-result-label">✅ 生成视频</div>
              <video src={result.url} controls className="ar-result-video" />
            </div>
          )}
        </div>
      )}

      {/* 上传新图重新分析 */}
      <div className="ar-section">
        <div className="ar-section-title">🔄 上传新参考图重新分析</div>
        <div
          className={`ar-re-dropzone ${isDragging ? "dragging" : ""}`}
          onDragEnter={handleDragEnter} onDragLeave={handleDragLeave}
          onDragOver={e => e.preventDefault()} onDrop={handleDrop}
        >
          {isDragging && <div className="ar-re-drag-overlay">🖼 松开鼠标上传参考图</div>}
          <input ref={reFileRef} type="file" accept="image/*" style={{ display:"none" }}
            onChange={e => { pickRe(e.target.files?.[0]); e.target.value = ""; }} />
          <div className="ar-re-row">
            {rePreview ? (
              <div className="ar-re-preview">
                <img src={rePreview} className="ar-re-thumb" alt="新参考图" />
                <button className="ar-re-clear" onClick={clearRe}>✕</button>
              </div>
            ) : (
              <button className="ar-re-upload" onClick={() => reFileRef.current?.click()}>
                📎 选择或拖入图片
              </button>
            )}
            <input className="ar-re-text" type="text" placeholder="补充说明（选填）"
              value={reText} onChange={e => setReText(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") submitRe(); }} />
            <button className="ar-re-submit"
              onClick={submitRe}
              disabled={!reImg || isGenerating}>
              提交分析 →
            </button>
            {result?.type === "image" && reImg && (
              <button className="ar-re-combine"
                onClick={() => { onCombine(reImg, reText); clearRe(); }}
                disabled={isGenerating}>
                🔀 合并生成
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
