# core/diff_scene.py
from pxr import Usd, UsdGeom, UsdShade

def _mat_binding(prim):
    api = UsdShade.MaterialBindingAPI(prim)
    rel = api.GetDirectBindingRel()
    t = rel.GetTargets()
    return str(t[0]) if t else None

def _visibility(prim):
    img = UsdGeom.Imageable(prim)
    attr = img.GetVisibilityAttr()
    return attr.Get() if attr else "inherited"

def _variant_selections(prim):
    vsets = prim.GetVariantSets()
    out = {}
    for name in vsets.GetNames():
        sel = vsets.GetVariantSelection(name)
        if sel:
            out[name] = sel
    return out

def snapshot(stage_path: str):
    stage = Usd.Stage.Open(stage_path)
    rows = {}
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Imageable):
            continue
        rows[str(prim.GetPath())] = {
            "material": _mat_binding(prim),
            "visibility": _visibility(prim),
            "variants": _variant_selections(prim),
        }
    return rows

def diff_snap(a: dict, b: dict):
    diffs = []
    for path, ar in a.items():
        br = b.get(path)
        if not br:
            continue
        delta = {}
        for k in ("material", "visibility"):
            if ar.get(k) != br.get(k):
                delta[k] = {"a": ar.get(k), "b": br.get(k)}
        if ar.get("variants", {}) != br.get("variants", {}):
            delta["variants"] = {"a": ar.get("variants", {}), "b": br.get("variants", {})}
        if delta:
            diffs.append({"path": path, "diff": delta})
    return diffs
