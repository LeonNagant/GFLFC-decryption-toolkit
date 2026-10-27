# NOTICE / 第三方组件与许可

## gffcdl

- 项目：gffcdl — Girls' Frontline: Fire Control Downloader/Decryptor
- 作者：Neptuwunium
- 来源：https://codeberg.org/neptuwunium/gffcdl
- 许可：EUPL-1.2（全文见仓库根目录 `LICENSE`）

本工具包中的 `scripts/decrypt.py` 源自 gffcdl，并做了一处修复：
原 `decrypt(path)` 调用 `decrypt_data(data)` 后丢弃返回值，导致文件实际未被解密；
本版本改为 `data = decrypt_data(data)` 后再写回。

## UnityPy

- 项目：UnityPy
- 许可：MIT
- 用途：解析 UnityFS、导出 Mesh/Texture/TextAsset

## 本项目脚本

除 `decrypt.py` 外，`scripts/` 下的脚本为本项目原创，与 `decrypt.py` 一同按
EUPL-1.2 发布（见根目录 `LICENSE`），不附带任何明示或暗示担保。

## 游戏资源

本工具包**不包含**任何《少女前线：火力控制》的游戏资源。
游戏资源版权归原开发/发行方所有；解包产物仅限个人研究、存档与格式分析，
请勿商用或再分发。
