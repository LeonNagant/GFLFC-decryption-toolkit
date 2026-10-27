#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""解析 SubpackageBundleInfo.fb（FlatBuffers，无 schema 定向解析）。

用法：
  python parse_subpackage_fb.py --fb SubpackageBundleInfo.fb --out subpackage_info.json

输出：
  <out>                 子包表：tag / segment / md5 / size / files[]
  <out 去 .json>_deps.json  tag 依赖表
"""
import argparse
import json
import struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fb", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = open(args.fb, "rb").read()
    N = len(data)

    def u16(p):
        return struct.unpack_from("<H", data, p)[0]

    def u32(p):
        return struct.unpack_from("<I", data, p)[0]

    def i32(p):
        return struct.unpack_from("<i", data, p)[0]

    def u64(p):
        return struct.unpack_from("<Q", data, p)[0]

    def as_string(p):
        if p < 4 or p + 4 > N:
            return None
        n = u32(p)
        if n == 0 or n > 400 or p + 4 + n > N:
            return None
        raw = data[p + 4:p + 4 + n]
        if all(32 <= b < 127 or b in (9, 10, 13) for b in raw):
            try:
                return raw.decode("ascii")
            except UnicodeDecodeError:
                return None
        return None

    def table_fields(p):
        if p < 8 or p + 4 > N:
            return None
        vt = p - i32(p)
        if vt < 0 or vt + 4 > N:
            return None
        vts, tbs = u16(vt), u16(vt + 2)
        if vts < 4 or vts % 2 or vt + vts > N or tbs > 4096:
            return None
        out = {}
        for i in range((vts - 4) // 2):
            off = u16(vt + 4 + 2 * i)
            if off and off < tbs:
                out[i] = p + off
        return out

    def vec_len(fp):
        t = fp + u32(fp)
        if not (0 < t < N - 4):
            return None, None
        cnt = u32(t)
        if cnt > 5000 or t + 4 + cnt * 4 > N:
            return None, None
        return t, cnt

    def field_str(fs, idx):
        fp = fs.get(idx)
        return as_string(fp + u32(fp)) if fp is not None else None

    def field_int(fs, idx):
        fp = fs.get(idx)
        return u32(fp) if fp is not None else None

    def field_i64(fs, idx):
        fp = fs.get(idx)
        return u64(fp) if fp is not None else None

    root = u32(0)
    rfs = table_fields(root)
    result = []
    for idx, fp in sorted(rfs.items()):
        t, cnt = vec_len(fp)
        if t is None or cnt > 300:
            continue
        for k in range(cnt):
            ep = t + 4 + 4 * k
            tp = ep + u32(ep)
            sfs = table_fields(tp)
            if not sfs:
                continue
            files = []
            ft, fcnt = vec_len(sfs[6]) if 6 in sfs else (None, None)
            if ft is not None:
                for j in range(fcnt):
                    fep = ft + 4 + 4 * j
                    ffp = fep + u32(fep)
                    ffs = table_fields(ffp)
                    if not ffs:
                        continue
                    files.append({
                        "file": field_str(ffs, 0),
                        "offset": field_i64(ffs, 3),
                        "md5": field_str(ffs, 5),
                        "size": field_i64(ffs, 6),
                    })
            result.append({
                "tag": field_str(sfs, 0), "segment": field_str(sfs, 1),
                "md5": field_str(sfs, 3), "size": field_int(sfs, 4),
                "file_count": len(files), "files": files,
            })

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    deps = {}
    if 1 in rfs:
        t, cnt = vec_len(rfs[1])
        if t is not None:
            for k in range(cnt):
                ep = t + 4 + 4 * k
                tp = ep + u32(ep)
                dfs = table_fields(tp)
                if not dfs:
                    continue
                name = field_str(dfs, 0)
                lst = []
                if 1 in dfs:
                    vt, vcnt = vec_len(dfs[1])
                    if vt is not None:
                        for j in range(vcnt):
                            vp = vt + 4 + 4 * j
                            s = as_string(vp + u32(vp))
                            if s:
                                lst.append(s)
                if name:
                    deps[name] = sorted(set(lst))

    deps_path = args.out[:-5] + "_deps.json" if args.out.endswith(".json") else args.out + "_deps.json"
    with open(deps_path, "w", encoding="utf-8") as f:
        json.dump(deps, f, ensure_ascii=False, indent=1)

    print(f"子包 {len(result)} 条 -> {args.out}")
    print(f"依赖 {len(deps)} 条 -> {deps_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
