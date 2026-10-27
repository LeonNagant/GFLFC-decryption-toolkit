# GFLFC 资源解密工具包

**中文** | [English](README.en.md)

[![CI](https://github.com/LeonNagant/GFLFC-decryption-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/LeonNagant/GFLFC-decryption-toolkit/actions/workflows/ci.yml)
[![License: EUPL-1.2](https://img.shields.io/badge/license-EUPL--1.2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

《少女前线：火力控制》（Girls' Frontline: Fire Control，包名 `com.sunborn.net`）
AssetBundle 解包/解密脚本与格式说明。

> **English summary**: A small, dependency-light toolkit to unpack the game's split APKs,
> decrypt its XOR-obfuscated UnityFS AssetBundles, parse the `SubpackageBundleInfo.fb`
> manifest, download post-launch subpackages from the CDN, and export meshes/textures/
> materials/animations with UnityPy. Scripts are Python 3.10+ and self-contained.
> Full English documentation: **[README.en.md](README.en.md)**.

**项目性质**：本仓库的代码与文档在 AI 编程助手（AI coding agent）的深度参与下完成，
所有结论均以实际解包结果为准。详见 [docs/ai-assisted.md](docs/ai-assisted.md)。

---

## 0. 免责声明

本项目仅用于**个人研究、存档与格式分析**。游戏资源版权归原开发/发行方所有，
请勿将解包产物用于商业用途或再分发。仓库内**不包含**任何游戏资源文件。

---

## 1. 这套工具解决什么问题

游戏客户端由 3 个 split APK 组成，核心资源在
`split_UnityDataAssetPack.apk!assets/Bundles/Android/`：

```
assets/Bundles/Android/
├── *.ab                    普通 AssetBundle（UnityFS，XOR 加密）
├── abxxxxxzip1 ... 7       无扩展名的 ZIP，里面还是 *.ab
├── assetMapName.fb         资源路径映射
├── assetbundlemetainfo.json  bundle 清单 + MD5
├── assetbundlestateinfo.json 版本/已解压列表
└── IndependentBundles.json 独立 bundle 列表
```

皮肤、活动等内容不在首包，而在停服前仍可访问的 CSnap 子包 CDN 上：

```
https://<server>/<channel>/subpackage/<segment>
```

子包文件 `.subpackage_segment` **不是 ZIP**，而是多个独立 XOR 的 UnityFS 首尾相接。
整套流程就是：

```
split APK ──► 提取 bundles ──► XOR 解密 ──► UnityPy 导出
                                   ▲
CDN 子包 ──► 下载 segment ──► 按魔数切分 ──┘
```

---

## 2. 环境

- Python **3.10+**（开发时使用 3.14）
- 依赖见 `requirements.txt`：

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

主要依赖：

| 包 | 用途 |
|---|---|
| `UnityPy` | 解析 UnityFS、导出 Mesh/Texture/TextAsset |
| `requests` | 下载 CDN 子包 |
| `Pillow` | 贴图转 PNG（UnityPy 的依赖） |
| `flatbuffers` | 读取 `.fb` 清单（可选，`parse_subpackage_fb.py` 为无 schema 解析） |

---

## 3. 目录约定

脚本默认从**当前工作目录**读取输入、写出结果。推荐布局：

```
<project>/
├── apk/                       # 放入 base.apk / split_*.apk
├── work/
│   ├── bundles_encrypted/     # unpack_apk.py 产出
│   ├── bundles_decrypted/     # 解密后的明文
│   ├── exported/              # 导出的资源
│   ├── subpackage/            # 下载的 .subpackage_segment
│   └── subpackage_bundles/    # 切分后的 bundle
└── scripts/                   # 本工具包
```

所有脚本都接受显式路径参数，不依赖固定目录名。

---

## 4. 快速开始

### 4.0 环境自检

```bash
python scripts/check_env.py
```

会打印 Python 版本、UnityPy / requests / Pillow 版本，并用一组构造的
明文/密文验证 XOR 核心（`UnityFS\0` ↔ `MAGIC`、循环密钥、MAGIC 守卫）。
退出码 0 才继续下一步。

> ⚠️ `decrypt.py` 里的 `decrypt(path)` 是**原地覆写**文件。
> 使用前请先复制一份原始 APK / bundle，或直接用 `unpack_apk.py`（它会写到新目录）。

### 4.1 解包 APK

```bash
python scripts/unpack_apk.py \
  --apk apk/split_UnityDataAssetPack.apk \
  --out work/
```

产出：

- `work/bundles_encrypted/`：APK 原始提取物（含内层 ZIP 拆出的 `.ab`）
- `work/bundles_decrypted/`：XOR 解密后的明文 UnityFS

### 4.2 建立索引（可选，但强烈建议）

```bash
python scripts/index_bundles.py \
  --bundles work/bundles_decrypted \
  --out work/_index.jsonl
```

每行一个 bundle 的对象清单，便于先检索 container 路径再决定导出什么。

### 4.3 导出资源

```bash
python scripts/export_bundles.py \
  --bundles work/bundles_decrypted \
  --out work/exported
```

| Unity 类型 | 输出 |
|---|---|
| `Texture2D` / `Sprite` / `Cubemap` | `.png` |
| `Mesh` | `.obj` |
| `TextAsset` | 原始字节（`.bytes` / `.txt` / `.json` …） |
| `Font` | `.ttf` |
| `Shader` / `ComputeShader` | `.shader` |
| `Material` / `AnimationClip` / `MonoBehaviour` / `SpriteAtlas` | `.json`（typetree） |

### 4.4 下载并解包子包（皮肤等）

前置：从 APK 取出

- `assets/Assets/CSnapAssetSetting/HotfixLocalConfig.json`
- `assets/Assets/CSnapAssetSetting/SubpackageBundleInfo.fb`

```bash
# 1) 解析子包清单
python scripts/parse_subpackage_fb.py \
  --fb SubpackageBundleInfo.fb \
  --out work/subpackage_info.json

# 2) 按关键词下载（例如所有 m1895 子包）
python scripts/dl_subpackage.py \
  --config HotfixLocalConfig.json \
  --info work/subpackage_info.json \
  --out work/subpackage/ \
  --match m1895

# 3) 切分 + 解密
python scripts/split_subpackage.py \
  --segments work/subpackage/ \
  --info work/subpackage_info.json \
  --out work/subpackage_bundles/

# 4) 导出（自动补齐跨 bundle 依赖）
python scripts/export_subpackage.py \
  --bundles work/subpackage_bundles/ \
  --info work/subpackage_info.json \
  --deps work/subpackage_info_deps.json \
  --out work/exported_subpackage/ \
  --match m1895
```

---

## 5. 脚本清单

| 脚本 | 作用 |
|---|---|
| `check_env.py` | 环境自检：依赖、版本、XOR 核心正确性 |
| `decrypt.py` | XOR 解密核心（来自 gffcdl，已修复返回值问题） |
| `unpack_apk.py` | 从 split APK 提取 bundles、拆内层 ZIP、批量解密 |
| `index_bundles.py` | 为 bundle 建立对象索引 JSONL |
| `export_bundles.py` | 通用资源导出（贴图/网格/文本/材质/动画） |
| `parse_subpackage_fb.py` | 无 schema 解析 `SubpackageBundleInfo.fb` |
| `dl_subpackage.py` | 从 CDN 按 tag 下载 `.subpackage_segment` |
| `split_subpackage.py` | 按魔数切分多 bundle 段并逐段解密 |
| `export_subpackage.py` | 子包资源导出，自动解析 CAB 跨 bundle 依赖 |

---

## 6. 验证方法

1. **解密是否正确**：明文前 8 字节应为 `UnityFS\0`。
2. **段切分是否正确**：每个 bundle 的 header 声明大小应等于实际字节数
   （`split_subpackage.py` 会打印异常）。
3. **对象是否完整**：`index_bundles.py` 的 `objects` 总数应与
   `assetbundlemetainfo.json` 的清单规模同量级；解析错误应为 0。
4. **导出是否可用**：OBJ 用 Blender 打开、PNG 用看图工具打开、JSON 能被 `jq` 解析。

---

## 7. 已知限制

- **RGBAHalf 贴图**：UnityPy/Pillow 无法把 `TextureFormat=17 (RGBAHalf)` 直接转 PNG，
  会报 `ValueError: bytes must be in range(0, 256)`。原始数据仍在 bundle 内，
  可用 `struct.unpack('<e')` 自行转 16-bit/float TIFF。
- **依赖闭包**：某些皮肤 bundle 的 Mesh PPtr 指向另一个 bundle 的 CAB，
  必须按 `SerializedFile.externals` 的 CAB 名补齐，否则 Mesh 会缺失。
- **版本差异**：不同客户端版本的 bundle 文件名/内容会变化，比对时以
  container 路径 + 对象哈希为准，不要只看文件名。
- **停服**：CDN 可能随时下线，重要资源请及时本地备份。

---

## 8. 致谢与许可

### 8.1 致谢

- **黑卡蒂工作室（Hecate Studio）**——《少女前线：火力控制》的开发团队。
  本工具包只是解析他们做出来的东西；所有游戏资源版权归工作室与原发行方所有。
- **在 Internet Archive 上传 `GFLFC_resourcepack_202606` 备份的玩家**——
  这份关服前导出的完整运行数据（1506 个 bundle），是本项目验证"CDN 备份是否完整"
  的基准，也补上了客户端首包缺失的全部热更内容。原地址：
  <https://archive.org/details/GFLFC_resourcepack_202606>
- **gffcdl 的作者 Neptuwunium**——XOR 密钥与初始解密实现的来源。
- **UnityPy 的作者们**——没有它就无法把 UnityFS 变成可用的模型和贴图。

### 8.2 相关链接

| 内容 | 地址 |
|---|---|
| 未解密的原始资源（玩家备份，1506 bundle） | <https://archive.org/details/GFLFC_resourcepack_202606> |
| 已解密后的资源（22,221 文件 / 6.51 GiB） | <https://archive.org/details/gflfc-unpacked-resources> |

### 8.3 许可

- XOR 密钥与初始解密实现来自 **gffcdl**（作者 Neptuwunium，EUPL-1.2）：
  <https://codeberg.org/neptuwunium/gffcdl>
  `scripts/decrypt.py` 保留其许可，全文见根目录 `LICENSE`。
- Unity 资源解析依赖 **UnityPy**（MIT）。
- 其余脚本为本项目原创，与 `decrypt.py` 一同按 EUPL-1.2 发布，不附带任何担保。

详见 `NOTICE.md`。

---

## 9. 关于 AI 辅助开发

本仓库是在 **AI 编程助手**（agent 形态的 AI coding，运行在本机，可读写文件、
执行命令、跑调试器）深度参与下完成的。为了对使用者诚实，这里把边界说清楚：

**AI 做了什么**

- 阅读 `assets/Bundles/Android/` 下的清单文件，定位加密方式与密钥来源；
- 反推 `.subpackage_segment` 的真实结构（多段 UnityFS 串联，而非 ZIP），
  并写出按魔数切分 + 逐段解密的实现；
- 在没有 FlatBuffers schema 的情况下，通过 vtable 偏移定向解析
  `SubpackageBundleInfo.fb`；
- 编写全部脚本、跑通 222 个 CDN 子包的下载/解密/导出，
  并根据导出失败的具体报错逐个修正（跨 bundle PPtr、RGBAHalf、重名覆盖等）；
- 整理本文档与 `docs/` 下的格式说明、操作流程、实测记录。

**人做了什么**

- 提供样本、账号环境与目标（"把仍能下载的角色资源完整备份下来"）；
- 判断哪些产出可用、哪些需要重做，决定取舍（例如最终放弃硬链接方案）；
- 复核 AI 的结论，并在真实设备上验证导出物能正常打开。

**这意味着什么**

- 脚本与文档中的每一个数字（bundle 数、对象数、字节数、MD5）都来自实际执行，
  不是推测；`docs/notes.md` 里连踩过的坑都保留了。
- AI 会犯错，本仓库的修错过程同样记录在案（`decrypt.py` 的返回值 bug、
  子包格式的误判、RGBAHalf 的失败路径），可以当作"AI 辅助逆向"的样本参考。
- 仓库不含任何游戏资源，也不含账号、设备、CDN token 等信息。

详细的协作方式、提示词组织与验证方法见 **[docs/ai-assisted.md](docs/ai-assisted.md)**。

---

## 10. 许可

本仓库整体按 **EUPL-1.2** 发布（`LICENSE`），以兼容上游 gffcdl 的许可。
第三方组件与例外说明见 `NOTICE.md`，逐项致谢见 [8.1](#81-致谢)。

