import shutil, subprocess, sys, json
from pathlib import Path
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

OUT = Path("out")
OUT.mkdir(exist_ok=True)

def usdrecord_path():
    return (shutil.which("usdrecord") or
            shutil.which("usdrecord.exe") or
            shutil.which("usdrecord.cmd"))

def have_usdrecord():
    return usdrecord_path() is not None

def run_cmd(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        print("COMMAND FAILED:", " ".join(cmd))
        print(p.stderr)
    return p.returncode == 0

def draft_render(stage_path: str, out_png: str, renderer: str | None = "Storm", width=640):
    exe = usdrecord_path()
    if exe:
        cmd = [exe]
        if renderer:
            cmd += ["--renderer", renderer]   # valid choices: "Storm", "GL"
        cmd += ["--imageWidth", str(width), "--defaultTime", stage_path, out_png]
        return run_cmd(cmd)
    # Fallback gradient if usdrecord missing
    w, h = width, int(width * 9 / 16)
    x = np.linspace(0, 1, w, dtype=np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)
    img = np.stack(np.meshgrid(x, y), axis=-1)
    pad = np.ones((h, w, 1), dtype=np.float32) * 0.5
    rgb = np.concatenate([img, pad], axis=-1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(out_png)
    return True


def load_img(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0

def ssim_diff(a_path, b_path):
    a = load_img(a_path); b = load_img(b_path)
    score, diff = ssim(a, b, channel_axis=2, full=True, data_range=1.0)
    diff_img = (1.0 - diff) * 255.0
    Image.fromarray(diff_img.astype(np.uint8)).save(str(Path(b_path).with_suffix(".diff.png")))
    return float(score)

def main():
    # args: python cli.py <review_stage> [final_stage]
    review_stage = sys.argv[1] if len(sys.argv) > 1 else "data/samples/teapot.usda"
    final_stage  = sys.argv[2] if len(sys.argv) > 2 else review_stage

    a_png = str(OUT / "review.png")
    b_png = str(OUT / "final.png")

    okA = draft_render(review_stage, a_png, renderer="Storm", width=640)
    okB = draft_render(final_stage,  b_png,  renderer="Storm", width=640)
    if not (okA and okB):
        print("Render failed.")
        sys.exit(2)

    score = ssim_diff(a_png, b_png)

    # --- scenegraph diff (requires pxr) ---
    from core.diff_scene import snapshot, diff_snap
    snapA = snapshot(review_stage)
    snapB = snapshot(final_stage)
    sg_diffs = diff_snap(snapA, snapB)

    report = {
        "review_stage": review_stage,
        "final_stage": final_stage,
        "ssim": score,
        "review_img": a_png,
        "final_img": b_png,
        "usdrecord": have_usdrecord(),
        "scene_diffs": sg_diffs
    }
    Path("out/report.json").write_text(json.dumps(report, indent=2))
    print(f"SSIM={score:.4f}  report=out/report.json  usdrecord={'yes' if have_usdrecord() else 'no'}  pxr=yes")

if __name__ == "__main__":
    main()
