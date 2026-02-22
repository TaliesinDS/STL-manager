# A Small Book: Building a 200px Anime Assistant (Free Tools, Beginner‑Friendly)

This guide shows several free, practical paths to create a small, animated “assistant” character for your app. It assumes:
- You prefer generating art with AI, not drawing by hand
- You have a 12GB VRAM GPU and use ComfyUI
- You can use only free software (no time‑limited trials)
- You want layered clothing/props and click reactions (e.g., startle → drop books → annoyed → idle)

The goal: ship something cute and responsive fast, then grow into richer rigs later.

---

## TL;DR: Quick Recommendation (fastest path)
- Style: High‑res anime frames scaled down to ~200px, low FPS (8–12).
- Make art: Generate key poses with SDXL (preferred if you can run it comfortably) or SD 1.5 in ComfyUI + ControlNet OpenPose for consistency (lock seed for identity).
- Layers: Cut body/clothes/props with Krita or `rembg` (transparent PNGs).
- Animate: Hand-pick a few frames per action; optionally add 1–2 AI‑interpolated in‑betweens with RIFE.
- Pack: Export PNG strips and pack into sprite sheets (Krita export or Free Texture Packer).
- Implement: Layered sprite stepping in HTML/CSS/JS (simple state machine). Low CPU/GPU, portable.

You’ll find a runnable web snippet in this guide.

---

## Step 0 — Define Interaction & Scope (pick any)
1. Click reactions only (idle loop; click → reaction → annoyed → back to idle).
2. Hover hints (subtle eyes/ear twitch when hovered; click still triggers full reaction).
3. Idle variety (random short idles every 10–20s to keep it lively).
4. Context hooks (assistant reacts to app events: long DB job, error toast, success).
5. Audio/Caption toggle (short SFX + on‑screen caption; accessible and optional).

---

## Step 1 — Choose a Visual Style (5 options)
1. Pixel art (sharp, few frames; Piskel/Krita). Simple to animate, nostalgic look.
2. Flat anime vectors (SVG or flat‑shade PNG; clean lines, crisp at 200px).
3. High‑res anime painted frames (generated at 512–1024px, scaled down; focus on strong key poses).
4. Skeletal 2D rig (free DragonBones). Great for reusable motions; needs clean cut parts.
5. Live2D‑style rig (Live2D Cubism Free edition). Very expressive; steeper setup but still free.

Tip: Style 3 (high‑res painted, scaled down) is the easiest with AI art + looks great at 200px.

---

## Step 2 — Generate Base Art with AI (ComfyUI‑friendly, 12GB)
Five practical approaches; mix as needed:
1. Text‑to‑Image for the character: SD 1.5 anime model (e.g., Anything/Counterfeit/Toonish SD1.5 variants) at 768×768 or 896×896. Use consistent prompts and a fixed seed for multiple poses.
2. ControlNet OpenPose: Drive pose explicitly (idle, startled, bending to drop books, annoyed). Keeps proportions consistent across frames.
3. Reference locking: Use IP‑Adapter (FaceID/Image) or ReferenceOnly to keep facial identity stable across prompts.
4. Inpaint variations: Generate a clean idle image; inpaint to produce startle/annoyed expressions or hand/arm moves while preserving outfit.
5. Batch render: Generate 3–6 key frames (idle, startle A/B, drop start, drop impact, annoyed) in one session with fixed seed + ControlNet.

Notes for 12GB:
- Prefer SD 1.5 over SDXL for comfort (lower VRAM); 768–896 square is usually fine. You’ll scale down later.
- Use `fp16`, 20–28 steps with a good sampler (DPM++ 2M Karras is a safe default).

---

## Step 3 — Split into Layers (Body, Clothing, Props)
You want transparent PNG layers so each piece can animate independently.

Five free ways:
1. Krita manual cut: Lasso/Bezier selection → copy to new layer → export PNGs.
2. `rembg` (open‑source background removal) to isolate the character from background, then duplicate & erase for per‑part layers.
3. Segment Anything (SAM/SAM2) UI to auto‑segment clothing/props, then refine in Krita.
4. ComfyUI mask workflows (segment models) to extract regions, then export PNGs.
5. Piskel quick edits for pixel/flat art: import a large image, cut into layers with transparency.

Pro tip: For a “books drop” prop, create two prop layers: `books_idle` (held) and `books_drop` (falling), so animation swaps are easy.

---

## Step 4 — Create Animation Frames (5 approaches)
1. Hand‑select keyframes only (fast): 2–6 frames per action at 8–12 FPS looks anime‑snappy. You don’t need silky smooth.
2. AI interpolation (video‑style in‑between): Arrange 2–3 keyframes into a tiny video and run RIFE frame interpolation (ComfyUI or Flowframes) to add 1–2 extra frames.
3. AnimateDiff (diffusion video): Generate short 0.5–1.5s loops; use strong prompts + pose conditioning; upscale best frames and extract to PNGs.
4. Skeletal animation (DragonBones): Rig cut parts (upper arm, forearm, hand, skirt, hair). Export sprite frames or run‑time JSON.
5. Live2D (Free): Rig meshes for face/body; export motions. Best for expressive eyes/mouth without many raster frames.

Pick a single approach per action at first (e.g., manual keyframes + optional RIFE in‑betweens).

---

## Step 5 — Pack Frames into Sprite Sheets (5 options)
1. Krita: Animation → Export as Sprite Sheet (rows/cols; PNG with transparency).
2. Aseprite (free if built from source): Export Sprite Sheet; choose “By Row” for simple stepping.
3. Piskel: Export PNG sheet from an animation.
4. Free Texture Packer (CodeAndWeb free edition): Drag frames → export a packed PNG + JSON (you can ignore JSON if using fixed grid).
5. DIY Python (Pillow) if you like scripts; not required.

Recommended grid: one row per animation. Example at 220×220 per frame, 8 frames → 1760×220 PNG.

---

## Step 6 — Implement on the Web (5 runtime choices)
1. Pure HTML/CSS/JS sprite stepping (background‑position). Easiest; great for 200px.
2. `<video>` or WebM (no transparency unless WebM + alpha). Simple control, but layering is harder.
3. Canvas 2D (drawImage frames). Slightly more code; good control, easy layering.
4. PixiJS (WebGL): Great for many sprites, filters, or blend modes. Overkill for one assistant, but future‑proof.
5. Live2D web viewer (pixi‑live2d‑display). For rigged models; most expressive.

The simplest (1) is provided below as a ready‑to‑paste snippet.

---

## Ready‑to‑Use Layered Sprite Snippet (HTML/CSS/JS)
Paste this into any page. Replace file paths with your sprite sheets.

```html
<!-- Assistant mount -->
<div id="assistant" aria-label="assistant" role="button" tabindex="0"></div>

<style>
  #assistant { position: fixed; right: 16px; bottom: 16px; width: 200px; height: 200px; cursor: pointer; user-select: none; }
  .ass-wrapper { position: relative; width: 200px; height: 200px; }
  .ass-layer { position: absolute; left: 0; top: 0; width: 200px; height: 200px; image-rendering: pixelated; background-repeat: no-repeat; background-position: 0 0; }
</style>

<script>
(() => {
  const FPS = 10;                      // 8–12 feels anime-ish
  const FRAME_MS = 1000 / FPS;
  const FRAME_W = 220, FRAME_H = 220;  // sprite frame size
  const BOX_W = 200, BOX_H = 200;      // visible box size
  const HOLD_ANNOYED_MS = 1200;

  const sheets = {
    body: {
      idle:    { url: 'docs/ui/img/assistant/body_idle.png', frames: 8 },
      startle: { url: 'docs/ui/img/assistant/body_startle.png', frames: 6 },
      annoyed: { url: 'docs/ui/img/assistant/body_annoyed.png', frames: 6 }
    },
    clothes: {
      idle:    { url: 'docs/ui/img/assistant/clothes_idle.png', frames: 8 },
      startle: { url: 'docs/ui/img/assistant/clothes_startle.png', frames: 6 },
      annoyed: { url: 'docs/ui/img/assistant/clothes_annoyed.png', frames: 6 }
    },
    props: {
      idle: { url: 'docs/ui/img/assistant/books_idle.png', frames: 4 },
      drop: { url: 'docs/ui/img/assistant/books_drop.png', frames: 8 }
    }
  };

  const mount = document.getElementById('assistant');
  const wrapper = document.createElement('div');
  wrapper.className = 'ass-wrapper';
  mount.appendChild(wrapper);

  const L = { body: document.createElement('div'), clothes: document.createElement('div'), props: document.createElement('div') };
  for (const k of Object.keys(L)) {
    const el = L[k];
    el.className = 'ass-layer';
    const offsetX = Math.floor((BOX_W - FRAME_W) / 2);
    const offsetY = Math.floor((BOX_H - FRAME_H) / 2);
    el.style.backgroundPosition = `${-offsetX}px ${-offsetY}px`;
    wrapper.appendChild(el);
  }

  function setSheet(layerEl, sheet) {
    layerEl.style.backgroundImage = `url("${sheet.url}")`;
    layerEl.dataset.frames = sheet.frames;
    layerEl.dataset.index = '0';
    layerEl.style.backgroundPositionX = '0px';
  }

  function setFrame(layerEl, idx) {
    layerEl.dataset.index = String(idx);
    layerEl.style.backgroundPositionX = (-idx * FRAME_W) + 'px';
  }

  let state = 'idle';
  let lastTick = 0;
  let rafId = 0;
  let fidx = { body:0, clothes:0, props:0 };
  let stepFn = () => {};

  function playIdle() {
    state = 'idle';
    setSheet(L.body, sheets.body.idle);
    setSheet(L.clothes, sheets.clothes.idle);
    setSheet(L.props, sheets.props.idle);
    stepFn = () => {
      const nf = (el) => (parseInt(el.dataset.index||'0') + 1) % parseInt(el.dataset.frames||'1');
      fidx.body = nf(L.body);   setFrame(L.body, fidx.body);
      fidx.clothes = nf(L.clothes); setFrame(L.clothes, fidx.clothes);
      fidx.props = nf(L.props); setFrame(L.props, fidx.props);
    };
  }

  async function playReaction() {
    if (state === 'reacting') return;
    state = 'reacting';
    setSheet(L.body, sheets.body.startle);
    setSheet(L.clothes, sheets.clothes.startle);
    setSheet(L.props, sheets.props.drop);
    let i = 0; const maxFrames = Math.max( parseInt(L.body.dataset.frames), parseInt(L.clothes.dataset.frames), parseInt(L.props.dataset.frames));
    await new Promise(resolve => {
      stepFn = () => {
        setFrame(L.body, Math.min(i, parseInt(L.body.dataset.frames)-1));
        setFrame(L.clothes, Math.min(i, parseInt(L.clothes.dataset.frames)-1));
        setFrame(L.props, Math.min(i, parseInt(L.props.dataset.frames)-1));
        i++; if (i >= maxFrames) resolve();
      };
    });
    setSheet(L.body, sheets.body.annoyed);
    setSheet(L.clothes, sheets.clothes.annoyed);
    setFrame(L.props, parseInt(L.props.dataset.frames)-1); // hold dropped
    state = 'annoyed';
    await new Promise(r => setTimeout(r, HOLD_ANNOYED_MS));
    playIdle();
  }

  function loop(ts) {
    if (!lastTick) lastTick = ts;
    const dt = ts - lastTick;
    if (dt >= FRAME_MS) { lastTick = ts; stepFn(dt); }
    rafId = requestAnimationFrame(loop);
  }

  const trigger = () => { if (state === 'idle' || state === 'annoyed') playReaction(); };
  mount.addEventListener('click', trigger);
  mount.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); trigger(); } });

  playIdle();
  rafId = requestAnimationFrame(loop);
})();
</script>
```

Place your sprite sheets where the `url(...)` paths point, or change the paths.

---

## Step 7 — FPS, Resolution, and “Feel” (5 guiding choices)
1. Low FPS (8–12) with strong key poses (classic anime snappiness).
2. Moderate FPS (15) if you want smoother facial changes but still lightweight.
3. High‑res sources (512–1024) scaled down to 200px for crisp edges.
4. Native pixel art at 200px if you prefer sharp, blocky charm.
5. Motion arcs over frames: exaggerate starting and ending poses; fewer in‑betweens.

---

## Composition & Staging (200px UI)
Keep it readable and grounded—no cartoon physics required.

- One action at a time: pause idle while a reaction plays.
- Clear silhouette: avoid busy patterns; keep edge contrast high so tiny moves read.
- Eye line and head turn: point toward the cursor or current UI event.
- Micro‑anticipation (1 short frame) before the main move; brief settle after.
- Anchor the character: use small arcs for props rather than straight teleports.

Preset timings that feel “real enough”
- Anticipation: 60–80 ms
- Main move: 120–220 ms total (few frames, front‑loaded speed)
- Settle: 120–200 ms with 1‑frame overshoot then return

---

## Step 8 — Interaction & State Logic (5 patterns)
1. Linear chain: idle → reaction → annoyed → idle (as in snippet).
2. Randomized reactions: choose among 3 startle variants.
3. Cooldowns: ignore clicks during reaction to prevent spam.
4. Event queue: enqueue reactions from app events.
5. Modular layers: swap outfit layers on demand without touching the body animation.

---

## Step 9 — Performance & Packaging (5 tactics)
1. Preload images (create Image() objects before showing assistant).
2. Keep sprite sheets small (200–300KB each is typical at 200px if optimized PNG).
3. Use `requestAnimationFrame` (already in snippet) for efficient timing.
4. Cache with a Service Worker if you want offline readiness.
5. Prefer PNG‑8/PNG‑24 depending on gradients; avoid unnecessary alpha where possible.

---

## Modern motion for UI sprites (no Looney‑Tunes)
Use grounded motion cues instead of squash/stretch:

- Timing curves, not many frames: quick ease‑in to the beat, linger near the settle.
- Overlap/latency: clothes/hair trail body by 1–2 frames; very small.
- Spatial anchoring: props follow a slight arc; no big bounces.
- Interruptibility: reactions should cancel if the user clicks again or focus changes.
- Accessibility: honor `prefers-reduced-motion` and keep semantics (role/aria) clear.

Tiny code additions

```css
/* Respect users who prefer reduced motion */
@media (prefers-reduced-motion: reduce) {
  #assistant { transition: none; }
}
```

```js
// Allow cancellation: a new click during reaction jumps to annoyed then back to idle sooner
let cancelRequested = false;
mount.addEventListener('click', () => { if (state === 'reacting') cancelRequested = true; });

async function playReaction() {
  if (state === 'reacting') return;
  state = 'reacting'; cancelRequested = false;
  // ... set sheets as before ...
  let i = 0; const maxFrames = Math.max(parseInt(L.body.dataset.frames), parseInt(L.clothes.dataset.frames), parseInt(L.props.dataset.frames));
  await new Promise(resolve => {
    stepFn = () => {
      if (cancelRequested) return resolve();
      // advance frames (as in existing code)
      i++; if (i >= maxFrames) resolve();
    };
  });
  // Jump to annoyed briefly if cancelled mid‑way
  setSheet(L.body, sheets.body.annoyed);
  setSheet(L.clothes, sheets.clothes.annoyed);
  setFrame(L.props, Math.max(0, parseInt(L.props.dataset.frames||'1') - 1));
  state = 'annoyed';
  await new Promise(r => setTimeout(r, cancelRequested ? 400 : HOLD_ANNOYED_MS));
  playIdle();
}
```

These give you realistic, snappy motion without bouncy, elastic “cartoon” physics.

---

## Expressive tiers: serious vs gag (Aqua‑inspired)
You can keep motion grounded most of the time, then “turn up” facial/expression exaggeration only when something goes wrong—very anime.

Concept
- Two tiers: `serious` (normal UI) and `gag` (failures/mishaps). Switch on triggers.
- Bodies/props stay mostly real; faces/overlays exaggerate briefly with stronger holds.
- Use overlays (sweat drop, exclamation, speed lines) as separate top layer.

Asset plan
- Serious sheets: body/clothes/props with subtle idles and calm expressions.
- Gag sheets: alternate face/clothes accents for startled/annoyed micro‑pose.
- Overlays (PNG, transparent): `ovr_exclaim.png`, `ovr_sweat.png`, `ovr_speedlines.png`, `ovr_anger_vein.png`, `ovr_tears.png`.

Triggers
- Serious by default; gag on: click mis-hit, error toast, task failure, or rare random event (e.g., 1/20).
- Auto‑cooldown back to serious after 0.8–1.6s, or next user action.

Timing presets (guideline)
- Serious: anticipation 60 ms, main 140–180 ms, settle 140 ms, overshoot 1 px, hold 600–900 ms.
- Gag: anticipation 50 ms, main 120–150 ms, settle 160–200 ms, overshoot 2–3 px, hold 1000–1400 ms.

File layout additions
```
/docs/ui/img/assistant/
  overlays/
    ovr_exclaim.png
    ovr_sweat.png
    ovr_speedlines.png
    ovr_anger_vein.png
    ovr_tears.png
```

Minimal wiring (JS)
```js
// Mode knobs – tweak to taste per tier
const MODE = {
  serious: { timingScale: 1.0, overshootPx: 1, holdMs: 800, overlays: [] },
  gag:     { timingScale: 0.85, overshootPx: 3, holdMs: 1300, overlays: ['exclaim','sweat'] }
};
let currentMode = 'serious';
function setMode(m){ currentMode = m; }

// Add an overlay layer element once
const overlay = document.createElement('div');
overlay.className = 'ass-layer';
wrapper.appendChild(overlay);
const overlayMap = {
  exclaim: 'docs/ui/img/assistant/overlays/ovr_exclaim.png',
  sweat:   'docs/ui/img/assistant/overlays/ovr_sweat.png',
  speed:   'docs/ui/img/assistant/overlays/ovr_speedlines.png',
  anger:   'docs/ui/img/assistant/overlays/ovr_anger_vein.png',
  tears:   'docs/ui/img/assistant/overlays/ovr_tears.png'
};
function showOverlays(keys){
  if (!keys || !keys.length) { overlay.style.backgroundImage = 'none'; return; }
  const imgs = keys.map(k => `url("${overlayMap[k]}")`).join(',');
  overlay.style.backgroundImage = imgs; // stacked backgrounds
}

// Example: choose gag on certain events
function onErrorEvent(){ setMode('gag'); playReaction(); }
function onNormalClick(){ setMode(Math.random()<0.05 ? 'gag' : 'serious'); playReaction(); }

// Inside playReaction(), apply mode to timings/hold and overlays
async function playReaction(){
  if (state === 'reacting') return;
  state = 'reacting'; cancelRequested = false;
  const M = MODE[currentMode];
  // choose overlays for gag; none for serious
  showOverlays(M.overlays);
  // ... set sheets ...
  let i = 0; const maxFrames = Math.max(parseInt(L.body.dataset.frames), parseInt(L.clothes.dataset.frames), parseInt(L.props.dataset.frames));
  let nextAt = performance.now();
  stepFn = (dt, now) => {
    if (now < nextAt) return;
    // advance frames (same as before) ...
    // schedule next frame scaled by mode
    nextAt = now + FRAME_MS * (M.timingScale || 1.0);
    i++;
    if (i >= maxFrames) {
      // overshoot by a few px based on mode, then settle
      L.props.style.transform = `translate(${M.overshootPx}px, 0px)`;
      const endAt = now + (M.holdMs || HOLD_ANNOYED_MS);
      stepFn = (dt2, now2) => {
        if (now2 >= endAt) { L.props.style.transform = 'translate(0px, 0px)'; showOverlays([]); playIdle(); }
      };
    }
  };
}
```

Legal note: take inspiration from the energy/comedy beats of named characters, but design and render your own original assistant to avoid likeness/IP issues.

---

## Step 10 — Accessibility & Settings (5 items)
1. Keyboard activation (Enter/Space) and `role="button"`, `aria-label`.
2. Respect reduced motion: pause or simplify when `prefers-reduced-motion: reduce` is set.
3. Captions: show a short on‑screen text for reactions (e.g., “Hey!”).
4. Mute/Volume: a small settings toggle if you add SFX later.
5. Hide/Pin: let users hide or pin the assistant position.

---

## Free Toolchain Catalog (no trials)
- Painting/Animation: **Krita** (free), **Piskel** (web), **Aseprite** (build from source).
- Cut/Layer/Compositing: **Krita**, **GIMP**, **rembg** (`pip install rembg`).
- Skeletal 2D: **DragonBones** (open‑source).
- Live2D‑style: **Live2D Cubism Free** (feature‑limited but free, no time limit).
- Frame Interpolation: **RIFE** (ComfyUI nodes) or **Flowframes** (free).
- Sprite sheet packing: **Krita export**, **Piskel export**, **Free Texture Packer**.

Optional installs (PowerShell examples):
```powershell
# rembg (background removal)
python -m pip install rembg

# Pillow if you later script packing
python -m pip install pillow
```

---

## ComfyUI Recipes for 12GB (sketches)
1. Consistent Poses with Identity
   - Loader(SD1.5 anime) → IP‑Adapter(FaceID or image) → ControlNet(OpenPose) → KSampler → SaveImage
   - Fixed seed + prompt template; render 3–6 key poses at 768–896 px.
2. Inpainting Expressions/Hands
   - Load idle → Mask face/hands → KSampler Inpaint with prompt tweaks → SaveImage (repeat for “startle”, “annoyed”).
3. AnimateDiff Short Loop
   - Loader(SD1.5) → AnimateDiff (8–16 frames @ 512) → Save frames → Upscale best frames → Use as sprite.
4. RIFE Interpolation
   - Take 2–3 keyframes → Assemble tiny MP4/WebP → RIFE node → Extract PNGs → Keep 1–2 in‑betweens.
5. Segmentation to Layers
   - Use SAM/Semantic segmentation node → Export masks → Apply masks to produce body/clothes/props PNGs.

Tip: If VRAM is tight, drop resolution to 640–704 square for keys; detail doesn’t matter after downscale to 200px.

---

## 2025 Updates & Vetted Alternatives (researched 2025‑09‑16)

You said you can comfortably run SDXL and barely run WAN 2.2, and you have Adobe apps. Here are up‑to‑date options and links:

### Models & Nodes
- SDXL for stills (preferred for you): use SDXL base for keyframes; refiner optional at 0.2–0.4 denoise for faces at higher res.
- AnimateDiff for short motion: the actively maintained fork is “AnimateDiff Evolved” for ComfyUI.
  - GitHub: https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved
- Frame interpolation (in‑betweens) with RIFE (GPU‑friendly, no training):
  - RIFE ncnn Vulkan: https://github.com/nihui/rife-ncnn-vulkan
- Stable Video Diffusion (SVD/Turbo) for micro‑clips: usable at modest res on 12GB; extract best frames to sprite sheets. Check license terms for redistribution.
- WAN 2.2: heavy on VRAM; use sparingly (e.g., reference stills) unless you upgrade.

### Free Editors (actively maintained)
- Pixelorama (open‑source, Godot) — solid for pixel and small sprites:
  - GitHub: https://github.com/Orama-Interactive/Pixelorama
  - Docs: https://www.oramainteractive.com/Pixelorama-Docs/
- PixiEditor 2.0 (released 2025; “Universal 2D Editor”) — raster/vector, sprite‑friendly:
  - Site/Blog: https://pixieditor.net/blog/2025/07/30/20-release/
  - Download: https://pixieditor.net/download/
- LibreSprite — community‑maintained Aseprite fork, free forever:
  - https://libresprite.github.io/

### Rigging (free)
- DragonBones (skeletal 2D; editor + JS runtimes still available):
  - Download: https://dragonbones.github.io/en/download.html
- Godot 4’s 2D skeleton + sprite exporters (alt to DragonBones) — fully free.
- Live2D Cubism Free — excellent expressiveness; free edition (feature‑limited) still suitable for assistants.

### Adobe (optional, since you have it)
- Photoshop: timeline animation for layering and quick sprite sheet export (via scripts/actions or the Spritesheet Exporter plug‑ins/community scripts). Great for cutting layers with Select Subject/Refine Edge.
- After Effects: puppet/mesh deforms; export frames to sprite sheets (via Bodymovin for Lottie if vector, or PNG sequence → packer). DUIK Bassel 2 is a powerful free rigging toolset for AE.

### Practical guidance specific to SDXL vs SD1.5
- Use SDXL for still keyframes (portraits, expressions, hands) at 768–1024px and downscale to 200px; lock seed + use IP‑Adapter/Reference to keep identity.
- Use SD1.5 with AnimateDiff Evolved for short motion clips if you want AI‑generated motion; then pick 4–8 representative frames for the sprite.
- Prefer ControlNet OpenPose in both SDXL and SD1.5 pipelines to match body posture across frames.

These updates slot directly into Steps 2, 4, and 5 in this guide without changing your implementation code.


## File & Naming Layout (suggested)
```
/your-app
  /docs/ui/img/assistant/
    body_idle.png          # strip: 220x220 x 8
    body_startle.png       # strip: 220x220 x 6
    body_annoyed.png       # strip: 220x220 x 6
    clothes_idle.png       # strip: 220x220 x 8
    clothes_startle.png    # strip: 220x220 x 6
    clothes_annoyed.png    # strip: 220x220 x 6
    books_idle.png         # strip: 220x220 x 4
    books_drop.png         # strip: 220x220 x 8
```

---

## Troubleshooting
- Character looks inconsistent between frames → lock seed, use ControlNet OpenPose and IP‑Adapter; avoid heavy prompt changes.
- Edges shimmer at 200px → render at higher res and scale down; avoid sub‑pixel movement when cutting layers.
- Animation feels too stiff → add one in‑between via RIFE or insert a holds/anticipation frame.
- Performance spikes → reduce sheet size/frames; lower FPS; preload assets.
- Layer misalignment → ensure all sheets share the exact frame box and anchor (e.g., 220×220) and export with same origin.

---

## Where to Go Next
- Swap outfits by replacing the clothes sheet in code.
- Add more reactions (wave, wink, point at UI updates).
- Try DragonBones for reusable motions (blink, hair sway) with few PNG parts.
- Move to Live2D Free if you want facial nuance (eye/mouth phonemes, physics).

Happy building!

---

## Opt‑in gating & safety (mature content)
If you plan to ship any mature‑only reactions, keep them strictly opt‑in and off by default. This section covers only the mechanics, not the content.

Design principles
- Off by default: require an explicit user toggle in settings.
- Age/region aware: show the toggle only where permitted (e.g., `age_verified === true`).
- Explicit consent: short, plain‑language description and confirmation step.
- Clear labeling: UI shows when mature reactions are enabled and can be turned off anytime.
- Partitioned assets: store mature sheets in a separate folder and do not preload unless enabled.
- Telemetry privacy: never log exact frames; only coarse on/off state if needed.

Suggested file layout
```
/docs/ui/img/assistant/
  base/                      # always-on assets
  overlays/                  # neutral emphasis overlays
  mature/                    # loaded only if enabled (do not preload)
```

Minimal settings wiring (HTML/JS)
```html
<label style="display:block;margin:8px 0;">
  <input id="optMature" type="checkbox" /> Enable mature reactions (opt‑in)
</label>
```

```js
// Persisted user preference (localStorage example)
const OPT_KEY = 'assistant_mature_enabled_v1';
function isMatureEnabled(){ return localStorage.getItem(OPT_KEY) === '1'; }
function setMatureEnabled(v){ localStorage.setItem(OPT_KEY, v ? '1' : '0'); }

// Hook checkbox to preference
const optEl = document.getElementById('optMature');
if (optEl) {
  optEl.checked = isMatureEnabled();
  optEl.addEventListener('change', () => setMatureEnabled(optEl.checked));
}

// Lazy-load partitioned assets only when enabled
async function loadMatureSheetsIfNeeded() {
  if (!isMatureEnabled()) return;
  // Example: pre-create Image() objects so network fetch occurs only after opt‑in
  const imgs = [
    'docs/ui/img/assistant/mature/mature_face_set.png',
    'docs/ui/img/assistant/mature/mature_overlay_set.png'
  ];
  await Promise.all(imgs.map(src => new Promise((res,rej)=>{ const im=new Image(); im.onload=()=>res(); im.onerror=rej; im.src=src; })));
}

// Gate reaction selection
function chooseReactionVariant(baseReason){
  // baseReason examples: 'click', 'error', 'success'
  const matureOK = isMatureEnabled();
  if (matureOK && baseReason === 'error') return 'gag_mature';   // pick a gated variant name
  if (baseReason === 'error') return 'gag';
  return 'serious';
}

// Call once after user toggles or on app start
loadMatureSheetsIfNeeded();
```

Operational notes
- Keep mature and base variants named distinctly (e.g., `gag_mature` vs `gag`).
- Avoid accidental preload: do not reference mature URLs in default CSS/HTML.
- Respect `prefers-reduced-motion` equally in both modes.
- Provide a one‑click “Disable mature reactions” button wherever the assistant appears.

