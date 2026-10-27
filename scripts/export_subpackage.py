#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出子包 bundle 中的资源（自动处理跨 bundle 的 CAB 依赖）。

用法：
  python export_subpackage.py --bundles work/bundles --info subpackage_info.json \
      --deps subpackage_info_deps.json --out exported/ --match m1895

输出：<out>/<tag>/{models,textures,materials,prefabs,animations,shared_models}/
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import UnityPy


def closure(tag, deps):
    out, stack = [], [tag]
    while stack:
        t = stack.pop()
        if t in out:
            continue
        out.append(t)
        stack.extend(deps.get(t, []))
    return out


def uniq(dest: Path, path_id: int) -> Path:
    return dest.parent / f"{dest.stem}__{path_id}{dest.suffix}" if dest.exists() else dest


def rel(cont: str, name: str, ext: str) -> Path:
    c = (cont or "").strip()
    if c.lower().startswith("assets/"):
        c = c[7:]
    p = Path(c) if c else Path(name + ext)
    return p.with_suffix(ext) if ext else p


def dump(obj, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(obj.read_typetree(), ensure_ascii=False,
                               indent=2, default=str), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", required=True, help="split_subpackage.py 的输出目录")
    ap.add_argument("--info", required=True)
    ap.add_argument("--deps", default="", help="parse_subpackage_fb.py 的 *_deps.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--match", default="", help="tag 子串匹配")
    ap.add_argument("--tag", action="append", default=[])
    args = ap.parse_args()

    root = Path(args.bundles)
    tags = sorted(d.name for d in root.iterdir() if d.is_dir())
    if args.tag:
        tags = [t for t in tags if t in set(args.tag)]
    elif args.match:
        tags = [t for t in tags if args.match.lower() in t.lower()]
    if not tags:
        print("没有匹配的 tag")
        return 1
    deps = json.load(open(args.deps, encoding="utf-8")) if args.deps and Path(args.deps).exists() else {}

    # CAB 名 -> bundle 路径，用于补齐跨 tag 依赖
    cab_index = {}
    for p in root.glob("*/*.ab"):
        for cab in re.findall(rb"CAB-[0-9a-f]{32}", p.read_bytes()):
            cab_index.setdefault(cab.decode(), p)
    print(f"CAB 索引 {len(cab_index)} 条")

    out_root = Path(args.out)
    for tag in tags:
        paths = []
        for t in closure(tag, deps):
            paths += sorted((root / t).glob("*.ab"))
        env = UnityPy.Environment()
        loaded, queue = set(), list(paths)
        while queue:
            p = queue.pop()
            if str(p) in loaded:
                continue
            loaded.add(str(p))
            try:
                env.load_file(str(p))
            except Exception:  # noqa: BLE001
                continue
            for bf in env.files.values():
                for sf in getattr(bf, "files", {}).values():
                    for ext in getattr(sf, "externals", []) or []:
                        owner = cab_index.get(Path(str(ext.path)).name)
                        if owner and str(owner) not in loaded:
                            queue.append(owner)

        key = re.sub(r"^(avatar|weapon|battle_vfx|vfx)_", "", tag, flags=re.I)
        own = re.compile(re.escape(key) + r"(?![0-9a-z])", re.I)
        outdir = out_root / tag
        n = Counter()
        for obj in env.objects:
            t = obj.type.name
            if t not in ("Mesh", "Texture2D", "Sprite", "Material", "GameObject",
                         "AnimationClip", "AnimatorOverrideController", "AvatarMask"):
                continue
            try:
                cont = obj.container or ""
            except Exception:  # noqa: BLE001
                cont = ""
            try:
                d = obj.read()
                name = getattr(d, "m_Name", "") or f"pathid_{obj.path_id}"
            except Exception:  # noqa: BLE001
                continue
            if t == "GameObject" and not own.search(cont):
                continue
            if not own.search(cont) and t != "Mesh":
                continue
            try:
                if t == "Mesh":
                    p = rel(cont, name, ".obj")
                    sub = "models" if own.search(cont) else "shared_models"
                    dest = outdir / sub / p.parent / f"{p.stem}__{name}.obj"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    text = d.export("obj")
                    if not isinstance(text, str):
                        raise TypeError("export() 返回非字符串")
                    dest.write_text(text, encoding="utf-8", errors="replace")
                elif t in ("Texture2D", "Sprite"):
                    dest = uniq(outdir / "textures" / rel(cont, name, ".png"), obj.path_id)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    d.image.save(dest, format="PNG")
                elif t == "Material":
                    dump(obj, uniq(outdir / "materials" / rel(cont, name, ".json"), obj.path_id))
                elif t == "GameObject":
                    dump(obj, uniq(outdir / "prefabs" / rel(cont, name, ".json"), obj.path_id))
                else:
                    dump(obj, uniq(outdir / "animations" / rel(cont, name, ".json"), obj.path_id))
                n[t] += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  [err] {tag} {t} {name}: {type(exc).__name__}: {exc}")
        print(f"{tag}: {dict(n)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
