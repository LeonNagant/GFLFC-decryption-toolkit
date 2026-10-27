#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""拆分 .subpackage_segment 为独立 bundle 并解密。

关键点：segment 不是 ZIP，而是多个「各自独立 XOR」的 UnityFS 首尾相接。
每个 bundle 的 XOR 都从 KEY[0] 重新开始，因此必须按加密魔数切分后逐段解密，
不能对整文件一次性 XOR。

用法：
  python split_subpackage.py --segments subpackage/ --info subpackage_info.json --out work/
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from decrypt import KEY, KEYLEN, MAGIC


def decrypt_chunk(buf: bytes) -> bytes:
    # 大整数异或：等价逐字节 buf[i] ^ KEY[i % KEYLEN]，但走 C 实现。
    n = len(buf)
    pad = (KEY * (n // KEYLEN + 1))[:n]
    return (int.from_bytes(buf, "little") ^
            int.from_bytes(pad, "little")).to_bytes(n, "little")


def split_segment(data: bytes):
    offs, i = [], 0
    while True:
        j = data.find(MAGIC, i)
        if j < 0:
            break
        offs.append(j)
        i = j + 1
    if not offs or offs[0] != 0:
        return []
    offs.append(len(data))
    return [data[offs[k]:offs[k + 1]] for k in range(len(offs) - 1)]


def bundle_size(buf: bytes):
    try:
        p = 12
        for _ in range(2):  # unityVersion, unityRevision（0 结尾）
            p = buf.index(0, p) + 1
        return struct.unpack_from(">q", buf, p)[0]
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True, help=".subpackage_segment 所在目录")
    ap.add_argument("--info", required=True, help="parse_subpackage_fb.py 产出的 JSON")
    ap.add_argument("--out", required=True, help="输出目录（每个 tag 一个子目录）")
    args = ap.parse_args()

    infos = {}
    for e in json.load(open(args.info, encoding="utf-8")):
        if e.get("tag") and e.get("segment"):
            infos.setdefault(e["tag"], e)

    segs = sorted(Path(args.segments).glob("*.subpackage_segment"))
    if not segs:
        print("未找到 .subpackage_segment")
        return 1

    out_root = Path(args.out)
    bad = 0
    for seg in segs:
        tag = seg.name[:-len(".subpackage_segment")]
        outdir = out_root / tag
        outdir.mkdir(parents=True, exist_ok=True)
        raw = seg.read_bytes()
        chunks = split_segment(raw)
        decl = [f["file"] for f in infos.get(tag, {}).get("files", [])]
        print(f"{tag}: {len(raw)} B -> {len(chunks)} 段", flush=True)
        for k, ch in enumerate(chunks):
            plain = decrypt_chunk(ch)
            declared = bundle_size(plain)
            name = decl[k] if k < len(decl) else f"part{k:02d}.ab"
            dest = outdir / f"{k:02d}_{name}"
            dest.write_bytes(plain)
            if declared != len(plain):
                bad += 1
                print(f"  [warn] {dest.name} header={declared} size={len(plain)}")
    print(f"完成，header 异常 {bad} 段")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
