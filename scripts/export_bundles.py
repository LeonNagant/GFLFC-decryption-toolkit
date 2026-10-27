#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 bundle 中的资源导出为可用文件。

用法：
  python export_bundles.py --bundles work/bundles_decrypted --out work/exported

导出规则：
  Texture2D / Sprite / Cubemap -> .png
  Mesh                         -> .obj
  TextAsset                    -> 原始字节（保留原扩展名，默认 .txt）
  Font                         -> .ttf
  Shader / ComputeShader       -> .shader
  Material / AnimationClip /
  MonoBehaviour / SpriteAtlas  -> .json（typetree）
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import UnityPy
from UnityPy.enums import ClassIDType as C

BAD = re.compile(r'[<>:"|?*\x00-\x1f]')


def safe(rel: str) -> Path:
    parts = []
    for p in rel.replace("\\", "/").split("/"):
        p = BAD.sub("_", p).strip()
        if p in ("", ".", ".."):
            continue
        parts.append(p[:120])
    return Path(*parts) if parts else Path("unnamed")


def target(outdir: Path, obj, data, default_ext: str) -> Path:
    try:
        cont = obj.container or ""
    except Exception:  # noqa: BLE001
        cont = ""
    if cont:
        rel = cont[7:] if cont.lower().startswith("assets/") else cont
        p = safe(rel)
        return outdir / (p if p.suffix else Path(str(p) + default_ext))
    name = getattr(data, "m_Name", "") or f"pathid_{obj.path_id}"
    return outdir / safe(f"{name}{default_ext}")


def dump_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--errors", default="export_errors.log")
    args = ap.parse_args()

    root = Path(args.bundles)
    out_root = Path(args.out)
    files = sorted(p for p in root.rglob("*.ab") if p.is_file())
    print(f"bundle 总数 {len(files)}", flush=True)

    stats = Counter()
    errs = open(args.errors, "w", encoding="utf-8")
    t0 = time.time()
    for i, path in enumerate(files, 1):
        rel = path.relative_to(root)
        outdir = out_root / rel.with_suffix("")
        try:
            env = UnityPy.load(str(path))
        except Exception as exc:  # noqa: BLE001
            errs.write(f"[bundle] {rel}: {type(exc).__name__}: {exc}\n")
            stats["bundle_error"] += 1
            continue
        for obj in env.objects:
            t = obj.type
            try:
                if t in (C.Texture2D, C.Sprite, C.Cubemap):
                    d = obj.read()
                    dest = target(outdir, obj, d, ".png").with_suffix(".png")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    d.image.save(dest, format="PNG")
                    stats["image"] += 1
                elif t == C.Mesh:
                    d = obj.read()
                    dest = target(outdir, obj, d, ".obj").with_suffix(".obj")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    text = d.export("obj")
                    if not isinstance(text, str):
                        raise TypeError("export() 返回非字符串")
                    dest.write_text(text, encoding="utf-8", errors="replace")
                    stats["mesh"] += 1
                elif t == C.TextAsset:
                    d = obj.read()
                    dest = target(outdir, obj, d, ".txt")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    raw = d.m_Script
                    if isinstance(raw, str):
                        raw = raw.encode("utf-8", "surrogateescape")
                    dest.write_bytes(bytes(raw))
                    stats["textasset"] += 1
                elif t == C.Font:
                    d = obj.read()
                    dest = target(outdir, obj, d, ".ttf")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(bytes(d.m_FontData))
                    stats["font"] += 1
                elif t in (C.Shader, C.ComputeShader):
                    d = obj.read()
                    script = getattr(d, "m_Script", None)
                    if not isinstance(script, str):
                        stats["shader_skipped"] += 1
                        continue
                    dest = target(outdir, obj, d, ".shader")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(script, encoding="utf-8", errors="replace")
                    stats["shader"] += 1
                elif t in (C.MonoBehaviour, C.Material, C.AnimationClip,
                           C.AnimatorController, C.SpriteAtlas):
                    d = obj.read()
                    dest = target(outdir, obj, d, ".json").with_suffix(".json")
                    try:
                        payload = obj.parse_as_dict()
                    except Exception:  # noqa: BLE001
                        payload = {"_unparsed": True, "_type": t.name,
                                   "_name": getattr(d, "m_Name", "")}
                    dump_json(dest, payload)
                    stats["json"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["obj_error"] += 1
                errs.write(f"[obj] {rel} path_id={obj.path_id} {t.name}: "
                           f"{type(exc).__name__}: {exc}\n")
        if i % 50 == 0 or i == len(files):
            print(f"[export] {i}/{len(files)} {dict(stats)} "
                  f"({time.time()-t0:.0f}s)", flush=True)

    errs.close()
    print("导出完成", json.dumps(dict(stats), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
