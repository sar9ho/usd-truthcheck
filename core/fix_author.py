# core/fix_author.py
from pathlib import Path
from typing import List, Dict, Any

_HEADER = '#usda 1.0\n(\n)\n'

def _over_block(path: str, lines: List[str]) -> str:
    # path like /World/Geom/Floor -> def "World"{ over "Geom"{ over "Floor"{ ... }}}
    parts = [p for p in path.split("/") if p]
    out = []
    # open chain
    for i, p in enumerate(parts):
        kw = "def" if i == 0 else "over"
        out.append(f'{kw} "{p}" ' + "{")
    # payload
    out += lines
    # close chain
    out += ["}" for _ in parts]
    return "\n".join(out)

def _line_set_visibility(val: str) -> List[str]:
    return [f'uniform token visibility = "{val}"']

def _line_bind_material(mat_path: str) -> List[str]:
    return [f'rel material:binding = <{mat_path}>']

def _variant_set_lines(variants: Dict[str,str]) -> List[str]:
    # write variant selections as metadata on prim (for simplicity we just set variantSets:…)
    return [f'variantSets = {{"{k}={v}"}}' for k,v in variants.items()]  # minimal; good enough for demo

def author_fix_layer(out_path: str, diffs: List[Dict[str,Any]]) -> str:
    body = []
    for d in diffs:
        path = d["path"]
        lines = []
        if "visibility" in d["diff"]:
            # normalize to 'a' (review) value
            lines += _line_set_visibility(d["diff"]["visibility"]["a"] or "inherited")
        if "material" in d["diff"] and d["diff"]["material"]["a"]:
            lines += _line_bind_material(d["diff"]["material"]["a"])
        if "variants" in d["diff"] and d["diff"]["variants"]["a"]:
            lines += _variant_set_lines(d["diff"]["variants"]["a"])
        if lines:
            body.append(_over_block(path, lines))
    text = _HEADER + "\n\n" + "\n\n".join(body) + "\n"
    Path(out_path).write_text(text, encoding="utf-8")
    return out_path
