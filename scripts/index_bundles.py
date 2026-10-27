#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为解密后的 bundle 建立对象索引（JSONL）。

用法：
  python index_bundles.py --bundles work/bundles_decrypted --out work/_index.jsonl

输出每行：
  {"bundle": "...", "objects": [{"path_id":..., "type":..., "name":..., "container":...}]}
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import UnityPy


def name_of(data):
    for attr in ("m_Name", "name"):
        v = getattr(data, attr, None)
        if isinstance(v, str) and v:
            return v
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = Path(args.bundles)
    files = sorted(p for p in root.rglob("*.ab") if p.is_file())
    print(f"bundle 总数 {len(files)}", flush=True)

    types = Counter()
    errors = []
    total = 0
    t0 = time.time()
    with open(args.out, "w", encoding="utf-8") as fh:
        for i, path in enumerate(files, 1):
            rel = path.relative_to(root).as_posix()
            rec = {"bundle": rel, "objects": []}
            try:
                env = UnityPy.load(str(path))
                containers = {o.path_id: c for c, o in env.container.items()}
                for obj in env.objects:
                    e = {"path_id": obj.path_id, "type": obj.type.name}
                    try:
                        d = obj.read()
                        nm = name_of(d)
                        if nm:
                            e["name"] = nm
                    except Exception as exc:  # noqa: BLE001
                        e["read_error"] = f"{type(exc).__name__}: {exc}"
                    c = containers.get(obj.path_id)
                    if c:
                        e["container"] = c
                    rec["objects"].append(e)
                    types[obj.type.name] += 1
                total += len(rec["objects"])
            except Exception as exc:  # noqa: BLE001
                rec["error"] = f"{type(exc).__name__}: {exc}"
                errors.append(rec)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if i % 100 == 0 or i == len(files):
                print(f"[index] {i}/{len(files)} objects={total} "
                      f"errors={len(errors)} ({time.time()-t0:.0f}s)", flush=True)

    print(f"完成：{len(files)} bundle / {total} 对象 / {len(errors)} 错误")
    print("类型分布（前 15）：", types.most_common(15))
    return 0


if __name__ == "__main__":
    sys.exit(main())
