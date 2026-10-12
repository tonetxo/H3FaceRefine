#!/usr/bin/env python3
"""Diagnostic runner: H3 FaceRefine extension wiring variants on one source video."""
import json, sys, time, urllib.request

BASE = "http://127.0.0.1:7822"
VIDEO = "0856001-Single continuous handheld shot, 34 ver-minimaxh3minimax_h3_fused_refdelta_r102.mp4"
REF = "seoanes.jpeg"
PROMPT = "<Picture 1> photorealistic face of this person, realistic eyes, detailed facial features, natural skin texture"
UNet = "minimaxh3/minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors"
Clip = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VaeV = "MiniMaxH3/minimax_h3_video_vae_int8_convrot.safetensors"
VaeA = "MiniMaxH3/minimax_h3_audio_vae_fp32.safetensors"


def build(v):
    n = {}
    def node(class_type, inputs):
        i = len(n) + 1
        n[str(i)] = {"class_type": class_type, "inputs": inputs}
        return str(i)
    unet = node("UNETLoader", {"unet_name": UNet, "weight_dtype": "default"})
    shift = node("MiniMaxH3SigmaShift", {"model": [unet, 0], "shift_video": 12.0, "shift_audio": 3.0})
    clip = node("CLIPLoader", {"clip_name": Clip, "type": "minimax"})
    vaev = node("VAELoader", {"vae_name": VaeV})
    vaea = node("VAELoader", {"vae_name": VaeA})
    video = node("LoadVideo", {"file": VIDEO})
    comp = node("GetVideoComponents", {"video": [video, 0]})
    ref = node("LoadImage", {"image": REF})
    track = node("H3FaceTrackCrop", {
        "images": [comp, 0], "detector": "bbox/face_yolov8m.pt", "confidence": 0.35,
        "crop_factor": 3.0, "canvas_width": 768, "canvas_height": 768,
        "canvas_mode": "auto_capped_768", "smooth_window": 21, "size_smooth_window": 51,
        "smooth_method": "gaussian", "size_mode": "per_frame", "identity_track": False,
        "identity_threshold": 0.28, "select": "largest_face",
        "fallback_detector": "segm/person_yolov8m-seg.pt", "fallback_head_frac": 0.5,
        "select_index": 0, "identity_model": "insightface", "cut_detection": "none"})
    r2v = node("MiniMaxH3ReferenceToVideo", {
        "clip": [clip, 0], "vae": [vaev, 0], "audio_vae": [vaea, 0], "prompt": PROMPT,
        "width": [track, 4], "height": [track, 5], "length": [track, 6],
        "ref_image_size": v["ref_size"], "ref_images.ref_image_0": [ref, 0]})
    inject = node("H3InjectVideoLatent", {"av_latent": [r2v, 1], "images": [track, 0], "vae": [vaev, 0]})
    model, latent = [shift, 0], [inject, 0]
    audio_in = None
    if v["audio_lock"]:
        lock = node("MiniMaxH3NativeAudioLock", {"model": [shift, 0], "av_latent": [inject, 0],
                                                 "audio_vae": [vaea, 0], "audio": [comp, 1]})
        model, latent, audio_in = [lock, 0], [lock, 1], [comp, 1]
    perframe = node("H3PerFrameDenoise", {
        "model": model, "av_latent": latent, "transform": [track, 1],
        "denoise_multiplier_small_face": v["mult_small"], "denoise_multiplier_large_face": v["mult_large"],
        "scale_mode": "absolute_px", "face_px_small": 30.0, "face_px_large": 120.0,
        "gamma": 1.0, "smooth_frames": 9})
    sched = node("BasicScheduler", {"model": [perframe, 2], "scheduler": "simple",
                                    "steps": v["steps"], "denoise": v["denoise"]})
    guider = node("BasicGuider", {"model": [perframe, 2], "conditioning": [r2v, 0]})
    ksel = node("KSamplerSelect", {"sampler_name": "euler"})
    noise = node("RandomNoise", {"noise_seed": v["seed"]})
    samp = node("SamplerCustomAdvanced", {"noise": [noise, 0], "guider": [guider, 0],
                                          "sampler": [ksel, 0], "sigmas": [sched, 0],
                                          "latent_image": [perframe, 0]})
    dec = node("VAEDecode", {"samples": [samp, 0], "vae": [vaev, 0]})
    stitch = node("H3FaceStitch", {
        "base_images": [comp, 0], "refined_crops": [dec, 0], "transform": [track, 1],
        "paste_region": v["paste_region"], "mask_dilation": 24, "feather": v["feather"],
        "colour_match": 1.0, "blend": 1.0, "undetected_frames": "fade_out"})
    cv_inputs = {"images": [stitch, 0], "fps": [comp, 2]}
    if audio_in is not None:
        cv_inputs["audio"] = audio_in
    node("SaveText", {"text": [track, 3], "filename_prefix": f"diag/V{v['name']}_track_report", "format": "txt"})
    cv = node("CreateVideo", cv_inputs)
    node("SaveVideo", {"video": [cv, 0], "filename_prefix": f"diag/V{v['name']}", "format": "mp4", "format.codec": "h264"})
    return {"prompt": {k: v2 for k, v2 in n.items()}}


def submit(graph):
    req = urllib.request.Request(BASE + "/prompt",
        data=json.dumps({"client_id": "diag", **graph}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["prompt_id"]


def save_graphs():
    for v in VARIANTS:
        with open(f"/tmp/opencode/diag/V{v['name']}.json", "w") as f:
            json.dump(build(v)["prompt"], f, indent=1)
        print(f"wrote V{v['name']}.json  denoise={v['denoise']} lock={v['audio_lock']} ref={v['ref_size']} paste={v['paste_region']}/{v['feather']}")


def wait(pid, timeout=1200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with urllib.request.urlopen(BASE + f"/history/{pid}", timeout=30) as r:
            h = json.load(r)
        if pid in h:
            e = h[pid]
            err = [o for o in e.get("status", {}).get("messages", []) if o[0] == "execution_error"]
            return (e.get("outputs", {}), err)
        time.sleep(3)
    raise TimeoutError(pid)


VARIANTS = [
    {"name": "A_extasis", "audio_lock": False, "denoise": 0.27, "steps": 6, "mult_small": 1.0,
     "mult_large": 0.65, "ref_size": "match", "paste_region": "face_ellipse", "feather": 22, "seed": 77},
    {"name": "B_lock", "audio_lock": True, "denoise": 0.27, "steps": 6, "mult_small": 1.0,
     "mult_large": 0.65, "ref_size": "match", "paste_region": "face_ellipse", "feather": 22, "seed": 77},
    {"name": "C_pack", "audio_lock": True, "denoise": 0.40, "steps": 8, "mult_small": 1.0,
     "mult_large": 0.35, "ref_size": "match", "paste_region": "face_only", "feather": 24, "seed": 77},
    {"name": "D_refmax", "audio_lock": True, "denoise": 0.40, "steps": 8, "mult_small": 1.0,
     "mult_large": 0.35, "ref_size": "max", "paste_region": "face_only", "feather": 24, "seed": 77},
]

if __name__ == "__main__":
    save_graphs()