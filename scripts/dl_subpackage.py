#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 SubpackageBundleInfo 清单从 CDN 下载 .subpackage_segment。

URL 模板：{serverUrl}/{channelId}/subpackage/{segment}
  serverUrl / channelId 来自 HotfixLocalConfig.json

用法：
  python dl_subpackage.py --config HotfixLocalConfig.json --info subpackage_info.json \
      --out subpackage/ --match m1895
  python dl_subpackage.py ... --tag avatar_hg_m1895_003 --tag weapon_m1895_cloud
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests


def md5_of(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="HotfixLocalConfig.json")
    ap.add_argument("--info", required=True, help="parse_subpackage_fb.py 产出的 JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--match", default="", help="tag 子串匹配（大小写不敏感）")
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8-sig"))
    server = cfg["serverUrls"][0].rstrip("/")
    channel = cfg["channelId"]

    seen, entries = set(), []
    for e in json.load(open(args.info, encoding="utf-8")):
        t = e.get("tag")
        if not t or not e.get("segment") or t in seen:
            continue
        seen.add(t)
        entries.append(e)

    if args.tag:
        sel = [e for e in entries if e["tag"] in set(args.tag)]
    elif args.match:
        sel = [e for e in entries if args.match.lower() in e["tag"].lower()]
    else:
        sel = entries
    if not sel:
        print("没有匹配的子包")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"server={server} channel={channel}")
    print(f"选中 {len(sel)} 个，合计 {sum(e['size'] or 0 for e in sel)/1048576:.1f} MiB")

    ok = fail = 0
    for e in sel:
        url = f"{server}/{channel}/subpackage/{e['segment']}"
        dest = out / e["segment"]
        if dest.exists() and not args.force and md5_of(dest) == e["md5"]:
            print(f"[skip] {e['tag']} 已存在且 MD5 匹配")
            ok += 1
            continue
        for attempt in range(1, args.retries + 1):
            try:
                t0 = time.time()
                with requests.get(url, stream=True, timeout=90) as r:
                    r.raise_for_status()
                    tmp = dest.with_suffix(dest.suffix + ".part")
                    h = hashlib.md5()
                    n = 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            if chunk:
                                f.write(chunk)
                                h.update(chunk)
                                n += len(chunk)
                tmp.replace(dest)
                digest = h.hexdigest()
                good = digest == e["md5"]
                print(f"[{'ok' if good else 'bad'}] {e['tag']} {n/1048576:.1f} MiB "
                      f"{time.time()-t0:.1f}s md5={digest}")
                ok += 1 if good else 0
                fail += 0 if good else 1
                break
            except Exception as exc:  # noqa: BLE001
                print(f"[retry {attempt}] {e['tag']}: {type(exc).__name__}: {exc}")
                time.sleep(min(2 ** attempt, 15))
        else:
            fail += 1
    print(f"完成：成功 {ok}，失败 {fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
