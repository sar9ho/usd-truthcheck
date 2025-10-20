# report/html_report.py
from pathlib import Path
from jinja2 import Template

_HTML = """<!doctype html>
<meta charset="utf-8">
<title>usd-truthcheck report</title>
<style>
  body{font:14px/1.45 system-ui,Segoe UI,Arial;margin:24px}
  header{display:flex;gap:24px;align-items:flex-start;margin-bottom:16px}
  img.thumb{height:180px;border:1px solid #ddd;border-radius:8px}
  table{border-collapse:collapse;width:100%;margin-top:16px}
  th,td{border:1px solid #e5e5e5;padding:8px;text-align:left}
  th{background:#fafafa}
  code{background:#f6f8fa;padding:2px 6px;border-radius:6px}
  .ok{color:#0a7d00}.bad{color:#b00020}
</style>
<header>
  <div>
    <h1 style="margin:0">USD Truth-Checker</h1>
    <div>Review: <code>{{ review_stage }}</code></div>
    <div>Final: <code>{{ final_stage }}</code></div>
    <div>SSIM: <b>{{ '%.4f'|format(ssim) }}</b> {% if ssim >= 0.95 %}<span class="ok">PASS</span>{% else %}<span class="bad">LOW</span>{% endif %}</div>
    {% if fixed_ssim is not none %}
      <div>Fixed SSIM: <b>{{ '%.4f'|format(fixed_ssim) }}</b></div>
      <div>Fix layer: <code>{{ fix_layer }}</code></div>
    {% endif %}
  </div>
  <div>
    <img class="thumb" src="{{ review_img }}" title="review">
    <img class="thumb" src="{{ final_img }}" title="final">
    <img class="thumb" src="{{ diff_img }}" title="diff">
    {% if fixed_img %}
      <img class="thumb" src="{{ fixed_img }}" title="final (fixed)">
    {% endif %}
  </div>
</header>

<h2>Scene Differences</h2>
{% if not scene_diffs %}
  <p>No scenegraph differences detected.</p>
{% else %}
<table>
  <tr><th>Prim</th><th>Property</th><th>Review</th><th>Final</th></tr>
  {% for d in scene_diffs %}
    {% for k,v in d.diff.items() %}
      <tr>
        <td><code>{{ d.path }}</code></td>
        <td>{{ k }}</td>
        <td><code>{{ v.a }}</code></td>
        <td><code>{{ v.b }}</code></td>
      </tr>
    {% endfor %}
  {% endfor %}
</table>
{% endif %}
"""

def _name(p: str) -> str:
    return Path(p).name  # make it relative to report folder

def write_html(out_path: str, payload: dict) -> str:
    out_dir = Path(out_path).parent

    # make image srcs relative to report location + force forward slashes
    review_img = _name(payload["review_img"])
    final_img  = _name(payload["final_img"])
    diff_img   = Path(payload["final_img"]).with_suffix(".diff.png").name
    fixed_img  = _name(payload.get("fixed_img")) if payload.get("fixed_img") else None

    html = Template(_HTML).render(
        review_stage = payload["review_stage"],
        final_stage  = payload["final_stage"],
        ssim         = payload["ssim"],
        fixed_ssim   = payload.get("fixed_ssim"),
        fix_layer    = _name(payload.get("fix_layer")) if payload.get("fix_layer") else None,
        review_img   = review_img,
        final_img    = final_img,
        diff_img     = diff_img,
        fixed_img    = fixed_img,
        scene_diffs  = payload["scene_diffs"],
    )
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    return str(out_dir / "report.html")
