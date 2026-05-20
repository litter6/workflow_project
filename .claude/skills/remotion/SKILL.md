---
name: video-generator
description: AI video production workflow using Remotion. Use when creating videos, short films, commercials, or motion graphics. Triggers on requests to make promotional videos, product demos, social media videos, animated explainers, or any programmatic video content. Produces polished motion graphics, not slideshows.
---

# Video Generator (Remotion)

Create professional motion graphics videos programmatically with React and Remotion.

## Default Workflow (ALWAYS follow this)

1. **Scrape brand data** (if featuring a product) using Firecrawl
2. **Create the project** in `output/<project-name>/`
3. **Build all scenes** with proper motion graphics
4. **Install dependencies** with `npm install`
5. **Fix package.json scripts** to use `npx remotion` (not `bun`):
   ```json
   "scripts": {
     "dev": "npx remotion studio",
     "build": "npx remotion bundle"
   }
   ```
6. **Start Remotion Studio** as a background process:
   ```bash
   cd output/<project-name> && npm run dev
   ```
   Wait for "Server ready" on port 3000.
7. **Expose via Cloudflare tunnel** so user can access it:
   ```bash
   bash skills/cloudflare-tunnel/scripts/tunnel.sh start 3000
   ```
8. **Send the user the public URL** (e.g. `https://xxx.trycloudflare.com`)

The user will preview in their browser, request changes, and you edit the source files. Remotion hot-reloads automatically.

### Rendering (only when user explicitly asks to export):

```bash
cd output/<project-name>
npx remotion render CompositionName out/video.mp4
```

## Quick Start

**IMPORTANT:** `create-video@latest` has an interactive CLI that blocks in non-TTY environments. Use manual scaffolding instead:

```bash
mkdir -p output/my-video/src/scenes output/my-video/public/audio output/my-video/public/images
cd output/my-video

# Create package.json manually
cat > package.json << 'EOF'
{
  "name": "my-video",
  "scripts": {
    "dev": "npx remotion studio",
    "build": "npx remotion bundle",
    "render": "npx remotion render"
  },
  "dependencies": {
    "@remotion/cli": "4.0.293",
    "react": "^19",
    "react-dom": "^19",
    "remotion": "4.0.293",
    "lucide-react": "^0.400"
  },
  "devDependencies": {
    "@types/react": "^19",
    "typescript": "^5"
  }
}
EOF

npm install

# Start dev server
npm run dev
```

## Core Architecture

### Scene Management

Use scene-based architecture with proper transitions:

```tsx
const SCENE_DURATIONS: Record<string, number> = {
  intro: 3000, // 3s hook
  problem: 4000, // 4s dramatic
  solution: 3500, // 3.5s reveal
  features: 5000, // 5s showcase
  cta: 3000, // 3s close
};
```

### Video Structure Pattern

```tsx
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Img,
  staticFile,
  Audio,
} from "remotion";

export const MyVideo = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  return (
    <AbsoluteFill>
      <Audio src={staticFile("audio/bg-music.mp3")} volume={0.35} />
      <AnimatedBackground frame={frame} />
      <Sequence from={0} durationInFrames={90}>
        <IntroScene />
      </Sequence>
      <Sequence from={90} durationInFrames={120}>
        <FeatureScene />
      </Sequence>
    </AbsoluteFill>
  );
};
```

## Motion Graphics Principles

### AVOID (Slideshow patterns)

- Fading to black between scenes
- Centered text on solid backgrounds
- Same transition for everything
- Linear/robotic animations
- Static screens
- Emoji icons — NEVER use emoji, always use Lucide React icons

### PURSUE (Motion graphics)

- Overlapping transitions (next starts BEFORE current ends)
- Layered compositions (background/midground/foreground)
- Spring physics for organic motion
- Varied timing (2-5s scenes, mixed rhythms)
- Continuous visual elements across scenes
- Custom transitions with clipPath, 3D transforms, morphs
- Lucide React for ALL icons (`npm install lucide-react`) — never emoji

## Transition Techniques

1. **Morph/Scale** - Element scales up to fill screen, becomes next scene's background
2. **Wipe** - Colored shape sweeps across, revealing next scene
3. **Zoom-through** - Camera pushes into element, emerges into new scene
4. **Clip-path reveal** - Circle/polygon grows from point to reveal
5. **Persistent anchor** - One element stays while surroundings change
6. **Directional flow** - Scene 1 exits right, Scene 2 enters from right
7. **Split/unfold** - Screen divides, panels slide apart
8. **Perspective flip** - Scene rotates on Y-axis in 3D

## Animation Timing Reference

```tsx
const timing = {
  micro: 0.1 - 0.2,
  snappy: 0.2 - 0.4,
  standard: 0.5 - 0.8,
  dramatic: 1.0 - 1.5,
};

const springs = {
  snappy: { stiffness: 400, damping: 30 },
  bouncy: { stiffness: 300, damping: 15 },
  smooth: { stiffness: 120, damping: 25 },
};
```

## Remotion Essentials

### Interpolation

```tsx
const opacity = interpolate(frame, [0, 30], [0, 1], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
});

const scale = spring({
  frame,
  fps,
  from: 0.8,
  to: 1,
  durationInFrames: 30,
  config: { damping: 12 },
});
```

### Sequences with Overlap

```tsx
<Sequence from={0} durationInFrames={100}>
  <Scene1 />
</Sequence>
<Sequence from={80} durationInFrames={100}>
  <Scene2 />
</Sequence>
```

## Quality Tests

Before delivering, verify:

- **Mute test:** Story follows visually without sound?
- **Squint test:** Hierarchy visible when squinting?
- **Timing test:** Motion feels natural, not robotic?
- **Consistency test:** Similar elements behave similarly?
- **Slideshow test:** Does NOT look like PowerPoint?
- **Loop test:** Video loops smoothly back to start?

## Unified Type Scale

**ALWAYS define a shared type scale in `styles.ts`**:

```tsx
export const colors = {
  bg: "#0a0a0f",
  textPrimary: "rgba(255,255,255,0.95)",
  textSecondary: "rgba(255,255,255,0.55)",
  textDim: "rgba(255,255,255,0.3)",
};

export const type = {
  hero: { fontSize: 96, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1.05 },
  h1: { fontSize: 68, fontWeight: 700, letterSpacing: "-0.035em", lineHeight: 1.1 },
  h2: { fontSize: 48, fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.2 },
  body: { fontSize: 28, fontWeight: 400, letterSpacing: "-0.01em", lineHeight: 1.5 },
  stat: { fontSize: 86, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1 },
};
```

## Transcription Overlay

```tsx
const LINES: { start: number; end: number; text: string }[] = [
  { start: 20, end: 140, text: "First caption line." },
];

export const Transcription: React.FC = () => {
  const frame = useCurrentFrame();
  const activeLine = LINES.find((l) => frame >= l.start && frame <= l.end);
  if (!activeLine) return null;

  // Adaptive fade prevents interpolation errors on short captions
  const dur = activeLine.end - activeLine.start;
  const fade = Math.min(10, Math.floor(dur / 3));

  const opacity = interpolate(
    frame,
    [activeLine.start, activeLine.start + fade, activeLine.end - fade, activeLine.end],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div style={{ position: "absolute", bottom: 56, left: 0, right: 0, display: "flex", justifyContent: "center", opacity }}>
      <div style={{ padding: "14px 36px", borderRadius: 14, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(16px)" }}>
        <span style={{ fontSize: 26, fontWeight: 500, color: "#fff" }}>{activeLine.text}</span>
      </div>
    </div>
  );
};
```

## AI Voiceover with Gemini TTS

```bash
export GEMINI_API_KEY="your-key"

curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-tts:generateContent?key=$GEMINI_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [{"parts": [{"text": "Your narration script here..."}]}],
    "generationConfig": {
      "response_modalities": ["AUDIO"],
      "speech_config": { "voiceConfig": { "prebuiltVoiceConfig": { "voiceName": "Orus" } } }
    }
  }' | python3 -c "
import json, sys, base64
r = json.load(sys.stdin)
audio = r['candidates'][0]['content']['parts'][0]['inlineData']['data']
sys.stdout.buffer.write(base64.b64decode(audio))
" > voiceover_raw.pcm

ffmpeg -f s16le -ar 24000 -ac 1 -i voiceover_raw.pcm public/audio/voiceover.wav
```

Voices: Orus (warm, authoritative), Kore (clear, friendly), Puck, Charon, Fenrir, Leda, Aoede, Zephyr
