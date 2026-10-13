# MiniMax H3 Face Refine — SwarmUI Extension

Adds an on-demand **H3 Face Refine** action button to completed videos in the SwarmUI history and
media viewer, powered by the [`ComfyUI-H3-FaceRefine`](https://github.com/Carasibana/ComfyUI-H3-FaceRefine)
node pack. It tracks faces across frames, regenerates them with the MiniMax H3 DiT at a controlled
per-frame denoise, and stitches them back seamlessly — without re-running the whole scene.

- **Version:** 1.0.0 · **Author:** Tonetxo · **License:** MIT
- **Target:** .NET 8 (`Microsoft.NET.Sdk.Web`), SwarmUI extension (`SwarmUI.extension.props`)

---

## Table of contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Parameters](#parameters)
6. [Recipes: restore vs. substitute](#recipes-restore-vs-substitute)
7. [How it works (pipeline)](#how-it-works-pipeline)
8. [Important design notes — do not re-add removed mechanisms](#important-design-notes--do-not-re-add-removed-mechanisms)
9. [Limitations & model range](#limitations--model-range)
10. [Troubleshooting](#troubleshooting)
11. [Repository layout](#repository-layout)
12. [Development notes](#development-notes)
13. [License](#license)

---

## Features
- **On-demand processing**: refine faces in already-rendered videos, no full-scene re-generation.
- **Multi-person / chained support** (`H3 Face Target`):
  - `Both Faces (Chained)` — sequentially detects and enhances two subjects in one pass (left stage → right stage).
  - `Primary Face (Largest)` — closest/largest face in frame (default).
  - `Secondary Face` — background or secondary characters.
  - `Left Person` / `Right Person` — for two-person dialogue shots.
  - `Center Person` — central subject.
  - `Identity Match (Reference Image)` — locks onto the subject matching Reference Image 1 via InsightFace embeddings.
- **Prompt sanitization**: the original video prompt's `<Picture i>` / `<Video k>` / `<Audio j>` tags point
  at references of the *original* generation, which a refine pass never sees. They are stripped before
  conditioning, and any reference portrait is re-anchored as the pass's own `<Picture 1>`. Dangling ordinals
  otherwise misguide the DiT and repaint the face into a generic, expressionless result (the pasted "mask" look).
- **Source audio lock**: when the `ComfyUI-H3-NativeAudioLock` pack is installed, the video's real soundtrack
  is locked into the joint AV latent (`MiniMaxH3NativeAudioLock`), so H3 denoises video only while attending to
  the original audio instead of inventing its own — keeping the regenerated mouth aligned to the original performance.
- **Identity fidelity control**: `H3 Face Ref Image Size` chooses whether a reference portrait is conditioned at
  the generation's canvas resolution (`match`, fast) or at the reference pipeline's full 2048px (`max` — best
  identity fidelity when replacing a face with a different person, slower).
- **Per-frame denoise multipliers**: `H3 Face Denoise Small Face` (default 1.0) and `H3 Face Denoise Large Face`
  (default 0.65) scale how much the pass repaints faces according to their size in the source (absolute px
  thresholds: small ≤ 30px, large ≥ 120px, gamma + temporal smoothing over 9 frames).
- **Auto-align paste**: `H3 Face Auto-Align Paste` (on by default) detects the face in each regenerated crop and
  in the matching source crop (eye landmarks so a substituted identity is not distorted), then shifts the
  regenerated one so the two faces coincide before stitching — cancelling the few-pixel content offset H3 leaves
  inside the paste that reads as the refined face "sliding" over the original head. Implemented as the Swarm
  `SwarmH3FaceRealign` node.
- **Two reference portraits**: Reference Image 1 → Person 1 / Left; Reference Image 2 → Person 2 / Right.
- **Clean VRAM isolation**: runs as a lightweight standalone post-process using normalized 768px face crops,
  keeping VRAM comfortably under 10 GB.
- **Audio & metadata preserved**: retains the original audio track and embeds the complete ComfyUI workflow
  metadata in the output MP4 (useful for forensics of your own runs).
- **Live in-pipeline mode**: the same refinement can be appended automatically at the end of a normal MiniMax H3
  video generation (workflow step priority 45), no button required.

---

## Requirements
- **SwarmUI** (the extension builds against `SwarmUI.csproj` / `SwarmUI.extension.props` at the repo root).
- A **MiniMax H3** model available in SwarmUI (model class `CompatMiniMaxH3`), plus its CLIP/text encoder and
  video (+audio) VAEs.
- **ComfyUI backend** with these node packs installed (both are registered as SwarmUI *installable features*,
  so you can install them from the Server tab → Features):

| Feature ID | Node pack | Provides |
|---|---|---|
| `h3_face_refine` | [ComfyUI-H3-FaceRefine](https://github.com/Carasibana/ComfyUI-H3-FaceRefine) | `H3FaceTrackCrop`, `H3InjectVideoLatent`, `H3PerFrameDenoise`, `H3FaceStitch` |
| `h3_audio_lock` | [MiniMax-H3-NativeAudio-MusicVideo-Workflow](https://github.com/Shrek3OnVH5/MiniMax-H3-NativeAudio-MusicVideo-Workflow) (nodes under `custom_nodes/ComfyUI-H3-NativeAudioLock`) | `MiniMaxH3NativeAudioLock` (optional but strongly recommended) |

- Detectors used by the tracker: `bbox/face_yolov8m.pt` (primary) and `segm/person_yolov8m-seg.pt`
  (person fallback when no face is detected); InsightFace for identity tracking.

---

## Installation
1. Place this folder inside your SwarmUI extensions directory, e.g.
   `src/Extensions/H3FaceRefine/` (the `.csproj` expects to find `../../SwarmUI.csproj`).
2. Build/restart. SwarmUI compiles extensions **at launch only**.
3. In **Server → Backends**, make sure the ComfyUI backend reports the `h3_face_refine` feature
   (install it from **Server → Features** if missing).
4. Select a MiniMax H3 model in the model dropdown.

> ⚠️ **Known gotcha:** SwarmUI names the compiled extension DLL after the current git HEAD hash
> (e.g. `src/bin/extensions/SwarmExtensionH3FaceRefine/SwarmExtensionH3FaceRefine-5cc57d13.dll`) and will
> **not** recompile it if that file already exists. After pulling changes, delete the extension's build
> folder and restart SwarmUI to force a fresh compile.

---

## Usage

### A) On-demand refine from history (the button)
1. Open the **Generate** panel, expand **H3 Face Refine** and configure the parameters you want
   (target, denoise, steps, reference images…). The group does **not** need to be toggled on for the
   button to work — the button reads the values straight from the panel.
2. Go to **User History** (or the media viewer) and open a completed **video**.
3. Click **H3 Face Refine**. The extension:
   - resolves the video path (`Output/…` or `View/…` → real file on disk),
   - disarms standard refiners and init images so nothing contaminates the pass,
   - switches to a MiniMax H3 model if needed,
   - runs the refine pipeline and saves `video/H3_FaceRefined_XXXXX_.mp4` with the original audio.
4. If the backend lacks the node pack, a toast warns you instead of starting a doomed generation.

### B) Live refine during generation
Enable the **H3 Face Refine** group and generate a MiniMax H3 video as usual. At priority 45 the extension
converts the decoded frames to raw images, runs the same pipeline on `CurrentMedia`, and reconnects the
refined frames (audio/FPS metadata preserved).

---

## Parameters

| Parameter | Default | Range / options | Notes |
|---|---|---|---|
| `H3 Face Target` | `Primary Face (Largest)` | see [Features](#features) | Which face(s) to refine. |
| `H3 Face Denoise` | `0.27` | 0.05 – 0.80 | Noise fraction per frame on H3's flow-matching schedule (**not** SDXL semantics). |
| `H3 Face Denoise Small Face` | `1.0` | 0 – 1 | Multiplier for the smallest faces (advanced). Keep at 1.0. |
| `H3 Face Denoise Large Face` | `0.65` | 0 – 1 | Multiplier for large/close-up faces (advanced). Low = protect real detail; 1.0 = substitution. |
| `H3 Face Steps` | `6` | 1 – 20 | DiT sampling steps (4–8 typical). |
| `H3 Face Canvas Size` | `auto_capped_768` | `auto_capped_768`, `768`, `512` | Normalized face canvas; 768 for detail, 512 for speed. |
| `H3 Face Feather` | `22` | 2 – 64 | Gaussian feather radius (source px) on the paste mask. 18–24 blends invisibly. |
| `H3 Face Detection Confidence` | `0.35` | 0.10 – 0.90 | YOLO threshold; lower catches occluded/distant faces. |
| `H3 Face Prompt` | *(empty)* | text | Facial prompt override. Empty ⇒ original video prompt + face-quality suffix. |
| `H3 Face Reference Image` | *(unset)* | image | Portrait for Person 1 / Left; also the identity anchor for `Identity Match`. |
| `H3 Face Reference Image Two` | *(unset)* | image | Portrait for Person 2 / Right. |
| `H3 Face Ref Image Size` | `match` | `match`, `max` | `max` conditions the ref at 2048px short edge — stronger identity, several times slower. |
| `H3 Face Refine Video File` | *(hidden)* | string | Internal parameter set by the history button. |

---

## Recipes: restore vs. substitute

**Restore a face (same person, fix blur/ghosting):**
- `H3 Face Denoise` **0.27 – 0.35** (≈0.40+ starts letting the model invent a generic face).
- `H3 Face Denoise Large Face` left at default **0.65** (protects real close-up detail).
- No reference image needed; optionally set `H3 Face Prompt` to a face-quality description.

**Substitute a face with a DIFFERENT person (verified empirically):**
- `H3 Face Reference Image` = large, centered portrait of the target person.
- `H3 Face Ref Image Size` = **`max`**.
- `H3 Face Denoise` = **0.5** (transfers distinguishing features, e.g. mustache/goatee) or **0.65**
  (transfers a fully different identity, e.g. full beard) — head motion is preserved either way.
- `H3 Face Denoise Large Face` = **1.0**. Leaving it at 0.65 makes the effective denoise far too gentle
  (e.g. `0.38 × 0.65 ≈ 0.13` → imperceptible change).
- Keep `H3 Face Target` on `Primary Face (Largest)` — identity-tracking with a reference of another person
  is conceptually wrong for substitution.

---

## How it works (pipeline)
Per face stage (`ProcessFaceStage`):
1. **`H3FaceTrackCrop`** — YOLO face detection (InsightFace identity lock only in `Identity Match`),
   gaussian-smoothed crop trajectory (window 21 / size window 51), person-segm fallback, normalized canvas.
2. **`MiniMaxH3ReferenceToVideo`** — builds positive conditioning + empty AV latent from the sanitized
   prompt (`<Picture 1> …` when a reference is wired), `ref_image_size` from `H3 Face Ref Image Size`.
3. **`H3InjectVideoLatent`** — VAE-encodes the crops into the AV latent.
4. **`MiniMaxH3NativeAudioLock`** *(if available)* — locks the source soundtrack into the AV latent,
   returns a video-only-denoise model.
5. **`H3PerFrameDenoise`** — per-frame denoise scaled by face size (small/large multipliers, absolute px).
6. **`BasicScheduler` (simple) → `BasicGuider` → `KSamplerSelect(euler)` → `RandomNoise` →
   `SamplerCustomAdvanced`** — the DiT repaint (seed = base seed + per-stage offset 77 / 78).
7. **`VAEDecode` → `H3FaceStitch`** — paste back into the source frames with `face_ellipse` region,
   dilation 24, feather from params, colour match 1.0, undetected frames fade out.
8. **`CreateVideo` → `SaveVideo`** — container/codec taken from SwarmUI's video format setting (forced to
   `mp4`, codec `h264`/`auto`), prefix `video/H3_FaceRefined`.

---

## Important design notes — do not re-add removed mechanisms
Two earlier mechanisms were measured (runs 39–45 + directed tests P1–P7) to **DESTROY identity transfer**
and have been **removed**:
- **Re-normalizing the reference portrait through `H3FaceTrackCrop`** ("composition match"): shrinking the
  ref's face into the video crop's composition kills the transfer.
- **Anchoring the first frame as a keyframe** (`SwarmMiniMaxH3AddKeyframes`): a real first-frame keyframe pins
  the *original* person's face and drags temporal attention back to the source identity.

The reference portrait is therefore fed to MiniMax H3 **exactly as supplied**. The old "cat on the bust"
hallucination was fixed by the prompt sanitizer + denoise recipe, not by those two mechanisms. Likewise,
automatic identity tracking now only applies to the explicit `Identity Match` mode. See `PROGRESS.md` for the
full forensic log.

---

## Limitations & model range
- Videos longer than ~15 seconds (**>362 frames @ 24fps**) exceed MiniMax H3's trained range (~124–362).
  The extension logs a warning and runs anyway; quality beyond that range is untested by the model itself.
  Consider splitting long clips before refining.
- Denoise values **do not transfer from SDXL**: on H3's flow-matching shift the value is the noise fraction
  per frame.
- When the tracker falls back to person segmentation (no real face detection), crop placement is estimated
  from the body and can be misaligned — visible as slight sliding of the refined patch. Lowering the
  detection confidence helps catch distant/partial faces.
- `H3 Face Ref Image Size = max` is several times slower because reference tokens ride through every step.

---

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| *"requires the ComfyUI-H3-FaceRefine node pack"* | Install feature `h3_face_refine` (Server → Features) and restart the backend. |
| *"requires a MiniMax H3 model"* | Pick a MiniMax H3 checkpoint in the Models dropdown. |
| *"Video file not found"* | The button passes `Output/<path>`; make sure the clip still exists in the user's output folder. |
| Refined face looks generic/expressionless ("mask") | Dangling `<Picture>/<Video>/<Audio>` refs (already sanitized) or denoise too high — drop to 0.27–0.35, or wire a reference portrait. |
| Mouth out of sync with audio | Install `h3_audio_lock` so the source soundtrack is locked into the AV latent. |
| Identity from reference doesn't appear | Use `Ref Image Size = max`, `Denoise Large Face = 1.0`, denoise 0.5–0.65. |
| Edges of the pasted face visible | Raise `H3 Face Feather` (18–24 typical), check canvas size. |
| Changes not taking effect after editing code | Delete `src/bin/extensions/SwarmExtensionH3FaceRefine/` and restart SwarmUI (see Installation note). |

---

## Repository layout
```
.
├── H3FaceRefineExtension.cs      # Extension: parameters, workflow generators, face pipeline
├── H3FaceRefineExtension.csproj  # net8.0 SwarmUI extension project
├── assets/h3_facerefine.js       # History/media-viewer action button + param forwarding
├── PROGRESS.md                   # Diagnostic sessions, evidence and fix log (Galician)
├── .diag-backup/                 # Durable copies of diagnostic workflows + runner
│   ├── run_diag.py               # Direct-to-ComfyUI API test runner
│   └── VA_extasis.json, VB_lock.json, VC_pack.json, VD_refmax.json
├── LICENSE                       # MIT
└── README.md
```

---

## Development notes
- Build standalone (inside a SwarmUI checkout):
  `dotnet build src/Extensions/H3FaceRefine/H3FaceRefineExtension.csproj -c Release` (last verified: 0 errors).
- Workflow steps registered: priority **-5.9** (standalone on-demand video request, intercepts before
  sampler/refiner and sets `SkipFurtherSteps`) and **45** (live in-pipeline refinement).
- Node→feature mapping lives in `ComfyUIBackendExtension.NodeToFeatureMap` (`H3FaceTrackCrop` →
  `h3_face_refine`, `MiniMaxH3NativeAudioLock` → `h3_audio_lock`).
- The JS forwards parameters using SwarmUI's clean input IDs derived from the registered param
  names (`h3facetarget`, `h3facedenoisesmallface`, ...; the hidden video-file param is
  `h3facerefinevideofile`) and clears stale state for that param on load.
- **Shared-default constants**: numeric parameter defaults live once in `H3FaceRefineExtension.H3FaceRefineDefaults`
  (C#); the JS defaults in `assets/h3_facerefine.js` mirror them manually (keep in sync when changing either side).
- **Fragile internal-API coupling** (compile against SwarmUI master after core updates): `g.IsMiniMaxH3()`,
  `T2IModelClassSorter.CompatMiniMaxH3`, and `WorkflowGenerator.CurrentCompat()`/`AttachedAudio` are treated as
  stable by this extension but are not established public API — a SwarmUI update can rename them. The H3 model
  fallback intentionally scans `Program.T2IModelSets.Values` (no hardcoded set names) to survive set renaming.
- **`.diag-backup/`** is a *diagnostic aid, not product code*: `run_diag.py` and its `V*.json` workflows hardcode
  the author's host (port 7822, specific safetensor filenames) to batch-run A/B experiments against a running
  SwarmUI. They are git-ignored; do not rely on their paths or model names in production.
- Planned improvements (see `PROGRESS.md`): segmenting >362-frame videos into windows, SAM-based paste masks
  (`H3FaceMaskSAM`, feather 4–8).

---

## License
MIT © 2026 Toño Pita — see [LICENSE](LICENSE).
