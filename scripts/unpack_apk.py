#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 split APK 提取并解密 Unity AssetBundle。

用法：
  python unpack_apk.py --apk split_UnityDataAssetPack.apk --out work/

流程：
  1. 解出 APK 内 assets/Bundles/Android/ 下的全部文件
  2. 对 abxxxxxzip*（无扩展名的 ZIP 容器）再拆一层
  3. 对所有 *.ab 检查加密魔数，命中则 XOR 解密

输出：
  <out>/bundles_encrypted/   原始提取物（仍加密）
  <out>/bundles_decrypted/   解密后的明文 UnityFS
"""
import argparse
import sys
import time
import zipfile
from pathlib import Path

from decrypt import MAGIC, decrypt_data


def extract_apk(apk: Path, prefix: str, enc: Path) -> int:
    n = 0
    with zipfile.ZipFile(apk) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            rel = info.filename[len(prefix):]
            dest = enc / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size == info.file_size:
                continue
            with z.open(info) as src, open(dest, "wb") as dst:
                while True:
                    buf = src.read(1 << 20)
                    if not buf:
                        break
                    dst.write(buf)
            n += 1
    return n


def split_inner_zips(enc: Path) -> int:
    n = 0
    for zp in sorted(enc.glob("abxxxxxzip*")):
        if not zipfile.is_zipfile(zp):
            continue
        outdir = enc / "zips" / zp.name
        outdir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zp) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                dest = outdir / info.filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.stat().st_size == info.file_size:
                    continue
                with z.open(info) as src, open(dest, "wb") as dst:
                    while True:
                        buf = src.read(1 << 20)
                        if not buf:
                            break
                        dst.write(buf)
                n += 1
    return n


def decrypt_all(enc: Path, dec: Path) -> tuple[int, int]:
    files = sorted(p for p in enc.rglob("*.ab") if p.is_file())
    hit = miss = 0
    for i, src in enumerate(files, 1):
        rel = src.relative_to(enc)
        dst = dec / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        if data[:len(MAGIC)] == MAGIC:
            hit += 1
            out = bytes(decrypt_data(data))
        else:
            miss += 1
            out = data
        dst.write_bytes(out)
        if i % 100 == 0 or i == len(files):
            print(f"[decrypt] {i}/{len(files)} magic={hit} plain={miss}", flush=True)
    return hit, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True, help="split_UnityDataAssetPack.apk")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--prefix", default="assets/Bundles/Android/",
                    help="APK 内资源前缀")
    args = ap.parse_args()

    out = Path(args.out)
    enc = out / "bundles_encrypted"
    dec = out / "bundles_decrypted"
    enc.mkdir(parents=True, exist_ok=True)
    dec.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    n = extract_apk(Path(args.apk), args.prefix, enc)
    print(f"APK 提取 {n} 个条目")
    n2 = split_inner_zips(enc)
    print(f"内层 ZIP 拆出 {n2} 个文件")
    hit, miss = decrypt_all(enc, dec)
    print(f"完成：加密命中 {hit}，未加密 {miss}，用时 {time.time()-t0:.1f}s")
    print(f"明文 bundle：{dec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
