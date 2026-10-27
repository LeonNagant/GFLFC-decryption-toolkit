# GFLFC Decryption Toolkit

[中文](README.md) | **English**

[![CI](https://github.com/LeonNagant/GFLFC-decryption-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/LeonNagant/GFLFC-decryption-toolkit/actions/workflows/ci.yml)
[![License: EUPL-1.2](https://img.shields.io/badge/license-EUPL--1.2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

Unpacking and decryption scripts plus format notes for
**Girls' Frontline: Fire Control** (`com.sunborn.net`), a Unity 2022.3 + IL2CPP
Android title whose client shipped as an App Bundle and whose post-launch content
was served from a CDN as XOR-obfuscated UnityFS segments.

A small, dependency-light toolkit that can:

- split the three-part APK set and pull `assets/Bundles/Android/` out of it;
- decrypt the XOR-obfuscated `UnityFS` AssetBundles;
- parse the `SubpackageBundleInfo.fb` manifest **without a FlatBuffers schema**;
- download post-launch subpackages (skins, accessories, VFX) from the CDN;
- export meshes / textures / materials / animations through UnityPy.

**Project nature**: this repository was built with heavy involvement of an
**AI coding agent** running locally (file access, shell, debugger). Every claim
here is backed by actual unpacking runs. See [docs/ai-assisted.md](docs/ai-assisted.md).

> **Disclaimer**: for personal research, archiving and format analysis only.
> All game assets remain the property of their respective rights holders.
> This repository contains **no** game assets.

---

## 1. What problem this solves

The client consists of three split APKs; the bulk of the content lives in
`split_UnityDataAssetPack.apk!assets/Bundles/Android/`:

```
assets/Bundles/Android/
├── *.ab                     regular AssetBundles (UnityFS, XOR-encrypted)
├── abxxxxxzip1 ... 7        extension-less ZIPs containing more *.ab
├── assetMapName.fb          asset path map
├── assetbundlemetainfo.json bundle list + MD5
├── assetbundlestateinfo.json version / extracted list
└── IndependentBundles.json  standalone bundle list
```

Skins and event content were **not** in the initial install. They were fetched at
runtime from a CSnap subpackage CDN that stayed online after the shutdown:

```
https://<server>/<channel>/subpackage/<segment>
```

Those `.subpackage_segment` files are **not ZIPs** — they are several
independently XOR-encrypted UnityFS files concatenated back to back.

```
split APK ──► extract bundles ──► XOR decrypt ──► UnityPy export
                                        ▲
CDN segment ──► download ──► split by magic ─┘
```

---

## 2. Requirements

- Python **3.10+** (developed on 3.14)
- Dependencies in `requirements.txt`:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

| Package | Purpose |
|---|---|
| `UnityPy` | parse UnityFS, export Mesh/Texture/TextAsset |
| `requests` | download CDN subpackages |
| `Pillow` | texture → PNG (UnityPy dependency) |
| `flatbuffers` | read `.fb` manifests (optional; the parser here is schema-less) |

---

## 3. Layout

Scripts read inputs and write outputs relative to the **current working directory**.
Recommended layout:

```
<project>/
├── apk/                       # base.apk / split_*.apk
├── work/
│   ├── bundles_encrypted/     # produced by unpack_apk.py
│   ├── bundles_decrypted/     # decrypted plaintext
│   ├── exported/              # exported assets
│   ├── subpackage/            # downloaded .subpackage_segment
│   └── subpackage_bundles/    # split bundles
└── scripts/                   # this toolkit
```

Every script takes explicit path arguments; nothing depends on a fixed directory name.

---

## 4. Quick start

### 4.0 Environment self-check

```bash
python scripts/check_env.py
```

Prints the Python version, UnityPy / requests / Pillow versions, and validates the
XOR core against a constructed plaintext/ciphertext pair
(`UnityFS\0` ↔ `MAGIC`, cyclic key, magic guard). Exit code 0 means you may proceed.

> ⚠️ `decrypt(path)` in `decrypt.py` **overwrites the file in place**.
> Copy your original APK/bundle first, or use `unpack_apk.py`, which writes to a new directory.

### 4.1 Unpack the APK

```bash
python scripts/unpack_apk.py \
  --apk apk/split_UnityDataAssetPack.apk \
  --out work/
```

Produces:

- `work/bundles_encrypted/` — raw APK extraction (including `*.ab` from inner ZIPs)
- `work/bundles_decrypted/` — decrypted plaintext UnityFS

### 4.2 Build an index (optional but recommended)

```bash
python scripts/index_bundles.py \
  --bundles work/bundles_decrypted \
  --out work/_index.jsonl
```

One line per bundle listing its objects, so you can search `container` paths before
exporting anything.

### 4.3 Export assets

```bash
python scripts/export_bundles.py \
  --bundles work/bundles_decrypted \
  --out work/exported
```

| Unity type | Output |
|---|---|
| `Texture2D` / `Sprite` / `Cubemap` | `.png` |
| `Mesh` | `.obj` |
| `TextAsset` | raw bytes (`.bytes` / `.txt` / `.json` …) |
| `Font` | `.ttf` |
| `Shader` / `ComputeShader` | `.shader` |
| `Material` / `AnimationClip` / `MonoBehaviour` / `SpriteAtlas` | `.json` (typetree) |

### 4.4 Download and unpack subpackages (skins etc.)

Prerequisite — extract from the APK:

- `assets/Assets/CSnapAssetSetting/HotfixLocalConfig.json`
- `assets/Assets/CSnapAssetSetting/SubpackageBundleInfo.fb`

```bash
# 1) parse the subpackage manifest
python scripts/parse_subpackage_fb.py \
  --fb SubpackageBundleInfo.fb \
  --out work/subpackage_info.json

# 2) download by keyword (e.g. all m1895 subpackages)
python scripts/dl_subpackage.py \
  --config HotfixLocalConfig.json \
  --info work/subpackage_info.json \
  --out work/subpackage/ \
  --match m1895

# 3) split + decrypt
python scripts/split_subpackage.py \
  --segments work/subpackage/ \
  --info work/subpackage_info.json \
  --out work/subpackage_bundles/

# 4) export (resolves cross-bundle dependencies automatically)
python scripts/export_subpackage.py \
  --bundles work/subpackage_bundles/ \
  --info work/subpackage_info.json \
  --deps work/subpackage_info_deps.json \
  --out work/exported_subpackage/ \
  --match m1895
```

---

## 5. Scripts

| Script | Purpose |
|---|---|
| `check_env.py` | environment self-check: deps, versions, XOR core correctness |
| `decrypt.py` | XOR core (from gffcdl, with a return-value fix) |
| `unpack_apk.py` | extract bundles from split APKs, expand inner ZIPs, batch decrypt |
| `index_bundles.py` | build a per-bundle object index (JSONL) |
| `export_bundles.py` | generic export (textures/meshes/text/materials/animations) |
| `parse_subpackage_fb.py` | schema-less parser for `SubpackageBundleInfo.fb` |
| `dl_subpackage.py` | download `.subpackage_segment` from the CDN by tag |
| `split_subpackage.py` | split concatenated segments by magic and decrypt each |
| `export_subpackage.py` | subpackage export with CAB cross-bundle dependency resolution |

---

## 6. How to verify your results

1. **Decryption** — the first 8 bytes of plaintext must be `UnityFS\0`.
2. **Segment splitting** — each bundle's declared header size must equal its actual
   byte length (`split_subpackage.py` prints anomalies).
3. **Object completeness** — total objects from `index_bundles.py` should be in the
   same order of magnitude as `assetbundlemetainfo.json`, with zero parse errors.
4. **Usability** — open OBJ in Blender, PNG in any viewer, and pipe JSON through `jq`.

Real measured numbers (bundle counts, object counts, byte sizes) are in
[docs/notes.md](docs/notes.md) so you can compare against your own run.

---

## 7. Known limitations

- **RGBAHalf textures** — UnityPy/Pillow cannot convert `TextureFormat=17 (RGBAHalf)`
  to PNG and raises `ValueError: bytes must be in range(0, 256)`. The raw data is
  still in the bundle; convert it yourself with `struct.unpack('<e')` to 16-bit/float TIFF.
- **Dependency closure** — some skin bundles have Mesh PPtrs pointing at a CAB in
  another bundle. You must resolve them through `SerializedFile.externals`, otherwise
  meshes come out empty.
- **Version drift** — bundle names and contents change between client versions.
  When comparing, key on container path + object hash, not on file names.
- **CDN shutdown** — the CDN may go offline at any time. Back up anything important.

---

## 8. Format notes

Deep dives live in `docs/`:

- [docs/formats.md](docs/formats.md) — APK layout, XOR algorithm, inner ZIPs,
  UnityFS, `SubpackageBundleInfo.fb` field table, `.subpackage_segment` structure,
  CDN protocol, cross-bundle dependencies.
- [docs/workflow.md](docs/workflow.md) — step-by-step walkthrough and a common-error table.
- [docs/notes.md](docs/notes.md) — measured numbers, the M1895 case study,
  subpackage format pitfalls, client-vs-savefile comparison.

---

## 9. About AI-assisted development

This repository was built with an **AI coding agent** running locally — able to read
and write files, run shell commands and drive debuggers. To be honest with users,
here is where the line sits.

**What the AI did**

- Read the manifests under `assets/Bundles/Android/` and traced how the key is derived;
- Reverse-engineered the real structure of `.subpackage_segment` (concatenated
  UnityFS files, not a ZIP) and wrote the magic-based splitter + per-segment decryption;
- Parsed `SubpackageBundleInfo.fb` **without a schema**, by walking vtable offsets;
- Wrote every script, ran the full 222-subpackage download/decrypt/export pipeline,
  and fixed failures one by one based on concrete errors (cross-bundle PPtrs,
  RGBAHalf, filename collisions);
- Wrote this documentation and everything under `docs/`.

**What the human did**

- Supplied samples, the runtime environment, and the goal ("back up every character
  asset still downloadable, skins included");
- Judged which outputs were usable and which needed redoing, and made the trade-offs
  (e.g. ultimately dropping the hardlink dedup plan);
- Reviewed the AI's conclusions and verified on real hardware that exported files open.

**What that means**

- Every number in these docs (bundle counts, object counts, byte sizes, MD5s) comes
  from real execution, not estimation. Even the dead ends are recorded.
- The AI made mistakes, and the fixes are in the repo too — the `decrypt.py` return-value
  bug, the subpackage format misjudgement, the RGBAHalf failure path. They make a useful
  case study for "AI-assisted reverse engineering".
- The repository contains no game assets, no account data, no device identifiers and
  no CDN tokens.

Details on the collaboration, prompt organisation and verification method:
**[docs/ai-assisted.md](docs/ai-assisted.md)**.

---

## 10. License

Released under **EUPL-1.2** (`LICENSE`) to stay compatible with upstream gffcdl.
Third-party components and exceptions are described in `NOTICE.md`.

- `scripts/decrypt.py` — from **gffcdl** by Neptuwunium, EUPL-1.2
  (<https://codeberg.org/neptuwunium/gffcdl>)
- **UnityPy** — MIT
- Remaining scripts — original work for this project
