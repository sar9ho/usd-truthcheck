from pathlib import Path
import shutil, subprocess, sys, json
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

OUT = Path("out"); OUT.mkdir(exist_ok=True)

def have_usdrecord():
    return shutil.which("usdrecord") is not None

def run_cmd(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        print(p.stderr)
    return p.returncode == 0

def draft_render(stage_path: str, out_png: str, renderer: str = "HdStorm", res=(640, 360)):
    """Try usdrecord; if not found, create a placeholder image so the rest of the pipeline runs."""
    if have_usdrecord():
        w, h = res
        cmd = ["usdrecord", "--renderer", renderer, "--res", f"{w}x{h}", stage_path, out_png]
        return run_cmd(cmd)
    # Fallback: generate a simple placeholder gradient (so SSIM code can run end-to-end)
    w, h = res
    x = np.linspace(0, 1, w, dtype=np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)
    img = np.stack(np.meshgrid(x, y), axis=-1)  # (h,w,2)
    pad = np.ones((h, w, 1), dtype=np.float32) * 0.5
    rgb = np.concatenate([img, pad], axis=-1)  # (h,w,3)
    Image.fromarray((rgb*255).astype(np.uint8)).save(out_png)
    return True

def load_img(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0

def ssim_diff(a_path, b_path):
    a = load_img(a_path); b = load_img(b_path)  # floats in [0,1]
    score, diff = ssim(a, b, channel_axis=2, full=True, data_range=1.0)
    diff_img = (1.0 - diff) * 255.0
    Image.fromarray(diff_img.astype(np.uint8)).save(str(Path(b_path).with_suffix(".diff.png")))
    return float(score)

def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "data/samples/teapot.usda"
    a_png = str(OUT / "review.png")
    b_png = str(OUT / "final.png")

    okA = draft_render(stage, a_png, renderer="HdStorm", res=(640, 360))
    okB = draft_render(stage, b_png, renderer="HdStorm", res=(640, 360))
    if not (okA and okB):
        print("Render failed.")
        sys.exit(2)

    score = ssim_diff(a_png, b_png)
    report = {"stage": stage, "ssim": score, "review": a_png, "final": b_png, "usdrecord": have_usdrecord()}
    Path("out/report.json").write_text(json.dumps(report, indent=2))
    print(f"SSIM={score:.4f}  report=out/report.json  usdrecord={'yes' if have_usdrecord() else 'no'}")

if __name__ == "__main__":
    main()
