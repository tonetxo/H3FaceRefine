# MiniMax H3 Face Refine Extension for SwarmUI

Adds an on-demand **H3 Face Refine** action button to completed videos in SwarmUI history and media viewer, powered by `ComfyUI-H3-FaceRefine`.

## Features
- **On-Demand Processing**: Refines faces in already-rendered videos without re-running the entire scene.
- **Multi-Person / Chained Support**:
  - `Both Faces (Chained)`: Sequentially detects and enhances two subjects in a single pass.
  - `Primary Face (Largest)`: Focuses on the closest/largest face in frame.
  - `Secondary Face`: Enhances background or secondary characters.
  - `Left Person` / `Right Person`: Tailored for two-person dialogue shots.
  - `Center Person`: Focuses on central subjects.
- **Prompt Sanitization**: The original video prompt's `<Picture i>`/`<Video k>`/`<Audio j>` reference tags point at references of the original generation, which a refine pass never sees. They are stripped before conditioning, and any reference portrait is re-anchored as the pass's own `<Picture 1>` - otherwise the dangling ordinals misguide the DiT and the face repaints into a generic, expressionless result (pasted "mask" look).
- **Source Audio Lock**: When the `ComfyUI-H3-NativeAudioLock` pack is installed, the video's real soundtrack is locked into the joint AV latent (`MiniMaxH3NativeAudioLock`), so H3 denoises video only while attending to the original audio instead of inventing its own. This keeps the regenerated mouth aligned to the original performance.
- **Identity Fidelity Control**: `H3 Face Ref Image Size` chooses whether a reference portrait is conditioned at the generation's canvas resolution (`match`, fast) or at the reference pipeline's full 2048px (`max` - best identity fidelity for replacing a face with a different person, slower).
- **Per-Frame Denoise Multipliers**: `H3 Face Denoise Small Face` (default 1.0) and `H3 Face Denoise Large Face` (default 0.65) scale how much the pass repaints faces by their size in the source. For restoring a close-up, the low Large-Face multiplier protects the real detail; for substituting a face with a reference of a DIFFERENT person, set the Large-Face multiplier to 1.0 and the denoise to 0.5-0.65 - verified empirically on the same clip: 0.5 already transfers distinguishing features (eg a transferred mustache/goatee), 0.65 transfers a fully different identity (full beard) while keeping the original head motion, and lower values (eg 0.38 x 0.65 ~= 0.13 effective) are imperceptible.
- **Reference Portrait Used Raw (important)**: the reference is fed to MiniMax H3 exactly as supplied. Two earlier mechanisms - re-normalizing the ref through the tracker (composition match) and anchoring the first frame as a keyframe - were measured to DESTROY identity transfer (the temporal attention is dragged back to the source person); with both removed, facial hair and face structure from the reference transfer reliably. Do not re-add them.
- **Auto-Align Paste**: `H3 Face Auto-Align Paste` (on by default) detects the face in each regenerated crop and in the matching source crop, then shifts the regenerated one so the two faces coincide before stitching, cancelling the few-pixel content offset H3 leaves inside the paste that reads as the refined face "sliding" over the original head. Translation only, so a substituted identity is not distorted. Implemented as the Swarm `SwarmH3FaceRealign` node.
- **Clean VRAM Isolation**: Executes as a lightweight standalone post-process pass using normalized 768px face crops, keeping VRAM comfortably under 10 GB.
- **Audio & Metadata Preserved**: Retains the original audio and embeds complete ComfyUI workflow metadata in the output MP4.

## Notes
- Videos longer than ~15 seconds (362 frames at 24fps) exceed MiniMax H3's trained range; the extension logs a warning and runs anyway, but quality beyond that range is untested by the model itself.
- Denoise values do not transfer from SDXL: on H3's flow-matching shift, the value is the noise fraction per frame. 0.27-0.35 preserves expression; ~0.40+ starts letting the model invent a generic face.
