import { useState } from "react";
import "./PromptBuilder.css";

// ── 各平台专属配置 ─────────────────────────────────────────
const PLATFORM_CONFIG = {
  "淘宝 / 天猫": {
    icon: "🛍",
    color: "#ff4400",
    contentTypes: ["主图文案", "详情页卖点", "标题 + 关键词优化", "买家好评回复", "店铺首页公告", "活动促销文案"],
    audiences: ["18-24 学生党", "25-35 都市白领", "宝妈群体", "中高收入女性", "银发族", "小镇青年"],
    resultStyles: ["简洁清爽型", "促销爆款型", "高端品质型", "故事情感型", "对比利益型", "节日氛围型"],
    extras: [
      { key: "searchKW", label: "关键词侧重", options: ["自然搜索排名", "直通车投放", "淘客推广"] },
      { key: "shopTier", label: "店铺层级", options: ["天猫旗舰店", "天猫专营店", "淘宝C店"] },
      { key: "conversion", label: "转化目标", options: ["提升点击率", "提升加购率", "提升转化率", "提升客单价"] },
    ],
  },
  "京东": {
    icon: "🔴",
    color: "#e1251b",
    contentTypes: ["商品标题优化", "五大卖点提炼", "参数规格说明", "品牌故事文案", "服务承诺文案", "对比竞品文案"],
    audiences: ["科技数码男", "企业采购负责人", "品质生活追求者", "家庭主采购", "学生数码用户", "汽车爱好者"],
    resultStyles: ["严谨技术流", "简洁商务型", "对比分析型", "参数详解型", "服务承诺型", "专家推荐型"],
    extras: [
      { key: "category", label: "商品大类", options: ["3C 数码", "家电", "服装", "食品", "图书", "汽车用品"] },
      { key: "badge", label: "平台标签", options: ["京东自营", "PLUS专享", "闪购", "企业采购"] },
      { key: "logistics", label: "物流卖点", options: ["211限时达", "当日达", "次日达", "全国联保"] },
    ],
  },
  "拼多多": {
    icon: "🟠",
    color: "#e02e24",
    contentTypes: ["爆款标题", "拼团活动文案", "砍价助力文案", "主图文字设计", "限时秒杀文案", "百亿补贴文案"],
    audiences: ["价格敏感型用户", "三四五线城市用户", "家庭主妇", "中老年用户", "学生用户", "农村电商用户"],
    resultStyles: ["接地气口语化", "强促销冲击型", "实惠实用型", "社交裂变型", "紧迫限时型", "工厂直供感"],
    extras: [
      { key: "priceStrat", label: "价格策略", options: ["工厂直销价", "拼团优惠价", "秒杀特价", "百亿补贴"] },
      { key: "urgency", label: "紧迫感类型", options: ["限时限量", "库存告急", "今日最低价", "拼团截止"] },
      { key: "socialProof", label: "社交背书", options: ["已售件数", "好友拼团", "买家实拍", "工厂溯源"] },
    ],
  },
  "抖音": {
    icon: "🎵",
    color: "#161823",
    contentTypes: ["短视频脚本（15秒）", "短视频脚本（60秒）", "直播带货话术", "商品卡文案", "评论区互动话术", "达人种草脚本"],
    audiences: ["Z 世代（18-25）", "追潮族", "宝妈群体", "健身运动党", "美妆爱好者", "吃货美食党"],
    resultStyles: ["娱乐搞笑型", "强情绪共鸣型", "干货种草型", "悬念反转型", "直播促单型", "沉浸场景型"],
    extras: [
      { key: "hook", label: "黄金3秒钩子", options: ["痛点提问", "反常识结论", "福利诱导", "悬念冲突"] },
      { key: "cta", label: "转化引导", options: ["点击购物车", "左下角链接", "评论区置顶", "直播间优惠"] },
      { key: "creator", label: "达人类型", options: ["头部达人", "腰部达人", "素人买家秀", "品牌自播"] },
    ],
  },
  "小红书": {
    icon: "📖",
    color: "#ff2442",
    contentTypes: ["种草笔记", "测评分享", "教程 / 攻略", "封面标题", "话题标签策划", "评论区互动话术"],
    audiences: ["都市白领女性（25-35）", "Z 世代女性", "美妆护肤爱好者", "穿搭时尚博主粉丝", "健康生活追求者", "母婴育儿群体"],
    resultStyles: ["闺蜜聊天感", "精致生活美学", "干货攻略型", "真实测评型", "情感共鸣型", "小众独特风"],
    extras: [
      { key: "noteType", label: "笔记形式", options: ["图文笔记", "视频笔记", "合集笔记"] },
      { key: "emoji", label: "Emoji 风格", options: ["大量 emoji（活泼）", "少量 emoji（精致）", "不用 emoji（专业）"] },
      { key: "hashTag", label: "话题标签", options: ["蹭热门话题", "垂直精准标签", "品牌专属话题", "混合策略"] },
    ],
  },
  "微信私域": {
    icon: "💚",
    color: "#07c160",
    contentTypes: ["朋友圈文案", "社群活动通知", "一对一私信开场", "客户维护消息", "转介绍话术", "复购激励文案"],
    audiences: ["新客首购用户", "3 个月内老客", "沉默半年以上用户", "高净值 VIP 客户", "会员体系用户", "转介绍潜力客户"],
    resultStyles: ["亲切朋友感", "专业顾问感", "节日温情型", "限定稀缺型", "成就激励型", "关怀提醒型"],
    extras: [
      { key: "relation", label: "客户关系", options: ["新客首购", "老客复购", "沉默唤醒", "高净值 VIP"] },
      { key: "channel", label: "私域渠道", options: ["朋友圈", "企业微信群", "个人微信", "公众号推文"] },
      { key: "action", label: "目标行为", options: ["下单购买", "转发裂变", "到店体验", "加入会员"] },
    ],
  },
  "亚马逊": {
    icon: "📦",
    color: "#ff9900",
    contentTypes: ["Listing 标题", "五点描述 (Bullet Points)", "A+ 品牌内容", "后台搜索关键词", "Q&A 问答", "Review 引导话术"],
    audiences: ["北美主流消费者", "欧洲精打细算型", "日本高品质追求者", "Prime 会员用户", "企业批量采购", "礼品选购用户"],
    resultStyles: ["SEO 关键词密集型", "痛点解决导向型", "品牌专业感型", "简洁高转化型", "对比差异化型", "礼品推荐型"],
    extras: [
      { key: "market", label: "目标站点", options: ["美国站", "欧洲站", "日本站", "中东站"] },
      { key: "bsr", label: "排名目标", options: ["新品冲榜", "维持 BSR", "细分类目第一", "Best Seller"] },
      { key: "fulfill", label: "配送模式", options: ["FBA 自发货", "FBM 亚马逊物流", "Prime 专享"] },
    ],
  },
};

const PRODUCT_TYPES = [
  "服装鞋包", "电子数码", "美妆护肤", "家居生活",
  "食品饮料", "运动户外", "母婴玩具", "珠宝配饰", "汽车用品", "其他",
];

export default function PromptBuilder({ onSend, disabled }) {
  const [platform, setPlatform] = useState("");
  const [contentType, setContentType] = useState("");
  const [audience, setAudience] = useState("");
  const [resultStyle, setResultStyle] = useState("");
  const [productType, setProductType] = useState("");
  const [extraSelections, setExtraSelections] = useState({});
  const [extra, setExtra] = useState("");

  const cfg = PLATFORM_CONFIG[platform];

  const setExtraSel = (key, val) =>
    setExtraSelections((prev) => ({ ...prev, [key]: prev[key] === val ? "" : val }));

  const handlePlatformChange = (p) => {
    setPlatform(p);
    setContentType("");
    setAudience("");
    setResultStyle("");
    setExtraSelections({});
  };

  const canSend = platform && contentType && productType;

  const buildPrompt = () => {
    const parts = [
      `平台：${platform}`,
      `产品类型：${productType}`,
      `内容需求：${contentType}`,
    ];
    if (audience) parts.push(`目标受众：${audience}`);
    if (resultStyle) parts.push(`结果风格：${resultStyle}`);
    if (cfg) {
      cfg.extras.forEach(({ key, label }) => {
        if (extraSelections[key]) parts.push(`${label}：${extraSelections[key]}`);
      });
    }
    if (extra.trim()) parts.push(`补充说明：${extra.trim()}`);
    return parts.join("；");
  };

  return (
    <div className="pb-wrap">
      <div className="pb-rows">

        {/* 平台选择 */}
        <div className="pb-row">
          <span className="pb-row-label">目标平台<em>*</em></span>
          <div className="pb-platform-chips">
            {Object.entries(PLATFORM_CONFIG).map(([name, { icon, color }]) => (
              <button
                key={name}
                className={`pb-platform-chip ${platform === name ? "active" : ""}`}
                style={platform === name ? { background: color, borderColor: color } : {}}
                onClick={() => handlePlatformChange(name)}
                type="button"
              >
                <span>{icon}</span>
                <span>{name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 产品类型 */}
        <div className="pb-row">
          <span className="pb-row-label">产品类型<em>*</em></span>
          <div className="pb-chips">
            {PRODUCT_TYPES.map((t) => (
              <button
                key={t}
                className={`pb-chip ${productType === t ? "active" : ""}`}
                onClick={() => setProductType(productType === t ? "" : t)}
                type="button"
              >{t}</button>
            ))}
          </div>
        </div>

        {/* 平台专属内容类型 */}
        {cfg && (
          <div className="pb-row">
            <span className="pb-row-label">内容类型<em>*</em></span>
            <div className="pb-chips">
              {cfg.contentTypes.map((t) => (
                <button
                  key={t}
                  className={`pb-chip ${contentType === t ? "active" : ""}`}
                  onClick={() => setContentType(contentType === t ? "" : t)}
                  type="button"
                >{t}</button>
              ))}
            </div>
          </div>
        )}

        {/* 目标受众 */}
        {cfg && (
          <div className="pb-row">
            <span className="pb-row-label">目标受众</span>
            <div className="pb-chips">
              {cfg.audiences.map((a) => (
                <button
                  key={a}
                  className={`pb-chip ${audience === a ? "active" : ""}`}
                  onClick={() => setAudience(audience === a ? "" : a)}
                  type="button"
                >{a}</button>
              ))}
            </div>
          </div>
        )}

        {/* 结果风格 */}
        {cfg && (
          <div className="pb-row">
            <span className="pb-row-label">结果风格</span>
            <div className="pb-chips">
              {cfg.resultStyles.map((s) => (
                <button
                  key={s}
                  className={`pb-chip ${resultStyle === s ? "active" : ""}`}
                  onClick={() => setResultStyle(resultStyle === s ? "" : s)}
                  type="button"
                >{s}</button>
              ))}
            </div>
          </div>
        )}

        {/* 平台专属扩展选项 */}
        {cfg && cfg.extras.map(({ key, label, options }) => (
          <div key={key} className="pb-row">
            <span className="pb-row-label">{label}</span>
            <div className="pb-chips">
              {options.map((opt) => (
                <button
                  key={opt}
                  className={`pb-chip ${extraSelections[key] === opt ? "active" : ""}`}
                  onClick={() => setExtraSel(key, opt)}
                  type="button"
                >{opt}</button>
              ))}
            </div>
          </div>
        ))}

        {/* 补充说明 */}
        <div className="pb-row">
          <span className="pb-row-label">补充说明</span>
          <input
            className="pb-extra"
            type="text"
            placeholder="品牌名、关键词、竞品参考、特殊要求等（选填）"
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && canSend && !disabled && onSend(buildPrompt())}
          />
        </div>
      </div>

      <div className="pb-footer">
        <span className="pb-tip">
          {!platform ? "请先选择目标平台" :
           !productType ? "请选择产品类型" :
           !contentType ? "请选择内容类型" :
           `${platform} · ${contentType}`}
        </span>
        <button
          className="pb-send"
          onClick={() => { if (canSend && !disabled) { onSend(buildPrompt()); } }}
          disabled={!canSend || disabled}
        >
          {disabled ? "生成中…" : "生成提示词 →"}
        </button>
      </div>
    </div>
  );
}
