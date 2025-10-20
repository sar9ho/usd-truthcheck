# cli.py
import sys, json, shutil, subprocess, webbrowser
from pathlib import Path
from typing import Optional
import typer
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

OUT = Path("out"); OUT.mkdir(exist_ok=True)

def usdrecord_path():
    return (shutil.which("usdrecord")
            or shutil.which("usdrecord.exe")
            or shutil.which("usdrecord.cmd"))

def have_usdrecord() -> bool:
    return usdrecord_path() is not None

def run_cmd(cmd):
    cmd = [str(x) for x in cmd]  # robust on Windows/paths-with-spaces
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        print("COMMAND FAILED:", " ".join(cmd))
        print(p.stderr)
    return p.returncode == 0

# --- NEW: stack base session layer + fix layer so we keep the same view ---
def make_stacked_session_layer(base_layer: Optional[str], extra_layer: str, out_path: Path) -> str:
    subs = []
    if base_layer:
        subs.append(f'@{base_layer}@')
    subs.append(f'@{extra_layer}@')
    text = '#usda 1.0\n(\n    subLayers = [\n        ' + ',\n        '.join(subs) + '\n    ]\n)\n'
    out_path.write_text(text)
    return str(out_path)

# ---------------- rendering ----------------
def draft_render(
    stage_path: str,
    out_png: str,
    renderer: Optional[str] = "Storm",   # valid: "Storm" or "GL" in your build
    width: int = 640,
    camera: Optional[str] = None,
    session_layer: Optional[str] = None,
    color_correction: Optional[str] = "sRGB",  # "sRGB" | "disabled" | "openColorIO"
    complexity: Optional[str] = "medium",      # "low" | "medium" | "high" | "veryhigh"
):
    exe = usdrecord_path()
    if exe:
        cmd = [exe]
        if renderer:        cmd += ["--renderer", renderer]
        if session_layer:   cmd += ["--sessionLayer", session_layer]
        if color_correction:cmd += ["--colorCorrectionMode", color_correction]
        if complexity:      cmd += ["--complexity", complexity]
        if camera:          cmd += ["--camera", camera]
        cmd += ["--imageWidth", str(width), "--defaultTime", stage_path, out_png]
        return run_cmd(cmd)

    # Fallback gradient if usdrecord missing
    h = int(width * 9 / 16)
    x = np.linspace(0, 1, width, dtype=np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)
    img = np.stack(np.meshgrid(x, y), axis=-1)
    pad = np.ones((h, width, 1), dtype=np.float32) * 0.5
    rgb = np.concatenate([img, pad], axis=-1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(out_png)
    return True

# ---------------- image metrics ----------------
def _load_img(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0

def ssim_diff(a_path, b_path):
    a = _load_img(a_path); b = _load_img(b_path)
    score, diff = ssim(a, b, channel_axis=2, full=True, data_range=1.0)
    Image.fromarray(((1.0 - diff) * 255.0).astype(np.uint8)).save(str(Path(b_path).with_suffix(".diff.png")))
    return float(score)

# ---------------- main app ----------------
app = typer.Typer(add_completion=False, help="Compare two USD stages: renders + scenegraph diffs + optional auto-fix.")

@app.command()
def check(
    review_stage: str = typer.Argument(...),
    final_stage:  str = typer.Argument(...),
    apply_fix:    bool = typer.Option(True, help="Author a fix session layer for FINAL to match REVIEW and re-check"),
    renderer:     str  = typer.Option("Storm"),
    width:        int  = typer.Option(640),
    camera:       Optional[str] = typer.Option("/World/Cam", help="Camera primPath"),
    ssim_threshold: float = typer.Option(0.95),
    open_html:    bool = typer.Option(True),
    session_layer: Optional[str] = typer.Option(None, help="Optional USD session layer to apply (e.g., camera override)"),
    color_correction: str = typer.Option("sRGB", help="usdrecord --colorCorrectionMode (sRGB|disabled|openColorIO)"),
    complexity: str = typer.Option("medium", help="usdrecord --complexity (low|medium|high|veryhigh)"),
    pass_if_fixed: bool = typer.Option(True, help="If fixed_ssim >= threshold, treat as PASS even if scene diffs exist"),
):
    a_png = str(OUT / "review.png")
    b_png = str(OUT / "final.png")

    okA = draft_render(review_stage, a_png, renderer=renderer, width=width,
                       camera=camera, session_layer=session_layer,
                       color_correction=color_correction, complexity=complexity)
    okB = draft_render(final_stage,  b_png,  renderer=renderer, width=width,
                       camera=camera, session_layer=session_layer,
                       color_correction=color_correction, complexity=complexity)
    if not (okA and okB):
        typer.secho("Render failed.", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    # Image diff
    score = ssim_diff(a_png, b_png)

    # Scenegraph diff
    from core.diff_scene import snapshot, diff_snap
    snapA = snapshot(review_stage)
    snapB = snapshot(final_stage)
    sg_diffs = diff_snap(snapA, snapB)

    report = {
        "review_stage": review_stage,
        "final_stage": final_stage,
        "review_img": a_png,
        "final_img": b_png,
        "ssim": score,
        "usdrecord": have_usdrecord(),
        "scene_diffs": sg_diffs,
        "renderer": renderer,
        "camera": camera or "",
        "width": width,
        "threshold": ssim_threshold,
        "color_correction": color_correction,
        "complexity": complexity,
    }

    # --- inside the apply_fix block ---
    if apply_fix and sg_diffs:
        from core.fix_author import author_fix_layer
        fix_path = str(OUT / "truth_fix.usda")
        fix_layer = author_fix_layer(fix_path, sg_diffs)

        combo_path = OUT / "session_combo.usda"
        stacked = make_stacked_session_layer(session_layer, fix_layer, combo_path)

        fixed_png = str(OUT / "final_fixed.png")
        draft_render(final_stage, fixed_png, renderer=renderer, width=width,
                    camera=camera, session_layer=stacked,
                    color_correction=color_correction, complexity=complexity)
        fixed_score = ssim_diff(a_png, fixed_png)

        # store fixed fields (needed for console + HTML + CI)
        report.update({
            "fixed_img": fixed_png,
            "fixed_ssim": fixed_score,
            "fix_layer": fix_layer,
        })


    # Write JSON + HTML
    Path("out/report.json").write_text(json.dumps(report, indent=2))
    from report.html_report import write_html
    html_path = write_html("out/report.html", report)

    # Console summary
    # --- after writing HTML, before deciding exit code ---
    fixed_txt = f"  fixed={report['fixed_ssim']:.4f}" if report.get('fixed_ssim') is not None else ""
    typer.echo(f"SSIM={score:.4f}{fixed_txt}  report={html_path}  usdrecord={'yes' if have_usdrecord() else 'no'}")

    failed = (score < ssim_threshold) or (len(sg_diffs) > 0)
    fixed_ok = report.get("fixed_ssim") is not None and report["fixed_ssim"] >= ssim_threshold

    # record decision metadata for dashboards
    report.update({"pass_if_fixed": pass_if_fixed, "fixed_ok": bool(fixed_ok)})
    Path("out/report.json").write_text(json.dumps(report, indent=2))  # refresh with decision flags

    if pass_if_fixed and fixed_ok:
        failed = False

    if failed:
        typer.secho("Result: FAIL (threshold or scene diffs)", fg=typer.colors.RED)
    else:
        msg = "PASS" if not (pass_if_fixed and fixed_ok) else "PASS (fixed)"
        typer.secho(f"Result: {msg}", fg=typer.colors.GREEN)


    if open_html:
        try:
            webbrowser.open(Path(html_path).absolute().as_uri())
        except Exception:
            pass

    raise typer.Exit(code=1 if failed else 0)


if __name__ == "__main__":
    app()
