import {
  AbsoluteFill,
  Video,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";

const FONT = `"PingFang SC","Microsoft YaHei","SimHei",sans-serif`;

/* ── Headline: top-center, springs in, fades out at endFrame ── */
function Headline({ text, endFrame }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter   = spring({ frame, fps, config: { damping: 22, stiffness: 240, mass: 0.7 } });
  const fadeOut = endFrame > 0
    ? interpolate(frame, [endFrame - fps, endFrame], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 1;

  return (
    <div style={{
      position: "absolute", top: "7%", left: 0, right: 0,
      display: "flex", justifyContent: "center",
      transform: `scale(${Math.min(enter, 1)})`,
      opacity: Math.min(enter * 2, 1) * fadeOut,
    }}>
      <div style={{
        background: "rgba(15,23,42,0.82)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        borderRadius: 14,
        padding: "10px 24px",
        color: "#fff",
        fontFamily: FONT,
        fontSize: 28,
        fontWeight: 800,
        letterSpacing: "0.4px",
        boxShadow: "0 10px 36px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.12)",
        border: "1px solid rgba(255,255,255,0.1)",
        whiteSpace: "nowrap",
        maxWidth: "90%",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}>
        {text}
      </div>
    </div>
  );
}

/* ── Feature badge: slides in from left or right, fades out ── */
function FeatureBadge({ text, startFrame, endFrame, isLeft, topPct }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < startFrame || frame >= endFrame) return null;

  const t   = frame - startFrame;
  const dur = endFrame - startFrame;

  const enter = spring({ frame: t, fps, config: { damping: 16, stiffness: 200 } });
  const exit  = interpolate(t, [dur - fps * 0.4, dur], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  const slideX = isLeft
    ? interpolate(enter, [0, 1], [-130, 0])
    : interpolate(enter, [0, 1], [130, 0]);
  const opacity = Math.min(enter * 3, 1) * exit;

  return (
    <div style={{
      position: "absolute",
      [isLeft ? "left" : "right"]: "4%",
      top: `${topPct}%`,
      transform: `translateX(${slideX}px)`,
      opacity,
      background: "rgba(249,115,22,0.90)",
      backdropFilter: "blur(10px)",
      WebkitBackdropFilter: "blur(10px)",
      borderRadius: 11,
      padding: "9px 17px",
      color: "#fff",
      fontFamily: FONT,
      fontSize: 21,
      fontWeight: 700,
      boxShadow: "0 4px 22px rgba(249,115,22,0.50), inset 0 1px 0 rgba(255,255,255,0.2)",
      border: "1px solid rgba(255,255,255,0.18)",
      maxWidth: "44%",
      lineHeight: 1.3,
    }}>
      {text}
    </div>
  );
}

/* ── CTA: bottom-center, springs in with pulse loop ── */
function CTABadge({ text, startFrame }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < startFrame) return null;

  const t     = frame - startFrame;
  const enter = spring({ frame: t, fps, config: { damping: 12, stiffness: 250, mass: 0.65 } });
  const pulse = interpolate(
    Math.sin((t / (fps * 1.4)) * Math.PI * 2),
    [-1, 1],
    [0.96, 1.04],
  );

  return (
    <div style={{
      position: "absolute", bottom: "14%", left: 0, right: 0,
      display: "flex", justifyContent: "center",
      transform: `scale(${Math.min(enter, 1) * pulse})`,
      opacity: Math.min(enter * 2, 1),
    }}>
      <div style={{
        background: "linear-gradient(135deg,#ef4444,#dc2626)",
        borderRadius: 14,
        padding: "11px 30px",
        color: "#fff",
        fontFamily: FONT,
        fontSize: 25,
        fontWeight: 800,
        letterSpacing: "1.5px",
        boxShadow: "0 6px 30px rgba(220,38,38,0.62), inset 0 1px 0 rgba(255,255,255,0.2)",
        border: "1px solid rgba(255,255,255,0.2)",
        whiteSpace: "nowrap",
      }}>
        {text}
      </div>
    </div>
  );
}

/* ── Main composition ── */
export function EcommerceComposition({ videoSrc, headline, features, cta }) {
  const { fps, durationInFrames } = useVideoConfig();

  const hlEndFrame   = Math.floor(durationInFrames * 0.30);
  const ctaStart     = Math.max(0, durationInFrames - fps * 4);
  const featureFracs = [0.20, 0.38, 0.56, 0.72];
  const featDurFr    = Math.round(fps * 3);

  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <Video src={videoSrc} />

      {headline && <Headline text={headline} endFrame={hlEndFrame} />}

      {(features || []).slice(0, 4).map((feat, i) => {
        const frac = featureFracs[i] ?? (0.20 + i * 0.15);
        const t0   = Math.floor(durationInFrames * frac);
        const t1   = Math.min(t0 + featDurFr, durationInFrames - 5);
        return (
          <FeatureBadge
            key={i}
            text={feat}
            startFrame={t0}
            endFrame={t1}
            isLeft={i % 2 === 0}
            topPct={30 + i * 10}
          />
        );
      })}

      {cta && ctaStart > 0 && <CTABadge text={cta} startFrame={ctaStart} />}
    </AbsoluteFill>
  );
}
