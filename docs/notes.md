# 实测记录与案例

以下数字来自 2026-10 的实际解包，可作为复现时的对照。

## 1. 版本与规模

| 来源 | 版本 | bundle | Unity 对象 | 备注 |
|---|---|---:|---:|---|
| 旧首包（2025-09 打包） | 0.4.x | 795 | 475,106 | `game/` 三个 split APK |
| Google Play 首包 | 0.5.3 | 1,025 | 594,154 | `googleplay/` |
| 玩家完整运行数据 | 0.5.3 | 1,506 | 733,769 | 首包 + 204 个已下载子包 |
| CDN 子包（222 个） | 3213 清单 | 508 | 128,061 | 仅皮肤/挂件/特效 |

v0.5.3 的 `split_UnityDataAssetPack.apk` 为 1,476,982,857 字节，
与玩家存档中的同名 APK **SHA256 完全一致**。

## 2. M1895（纳甘左轮）案例

- 游戏内部代号只有 `m1895`，`nagant` / `nagan` / `纳甘` 均无命中。
- v0.4.1 首包中角色人体不在首包，只有武器与骨骼根；角色本体在旧备份
  `asset_bkup/Android/3cad38fa.ab`（battle）和 `11632a21.ab`（lobby）。
- v0.5.3 首包包含 `avatar/player/hg_m1895`，13 个网格、12 张贴图、18 个材质、
  78 个动画。
- CDN 上 M1895 有 5 套角色皮肤（003/004/006/007/009）和 11 套武器皮肤。
- 皮肤 bundle 的 Mesh PPtr 指向 `CAB-758404c4...`，该 CAB 在 003 的 bundle 里；
  fb 依赖表只写了 009→003，因此必须用 externals 做 BFS 才能补全 004/006/007/009。

## 3. 子包格式的坑

`.subpackage_segment` 最初被误判为 ZIP（文件头不是 PK），
后确认是多个 UnityFS 串联。关键证据：

- 全文件 XOR 后，第 1 段头为 `UnityFS\0`，第 2 段开始乱码；
- 按加密魔数切分后，39 个段全部 header 自洽；
- 每个段的 XOR 都从 `KEY[0]` 重新开始。

## 4. 玩家存档 vs 客户端

对比一个 2026-06 的玩家完整数据（1,506 bundle）与 0.5.3 首包（1,025 bundle）。
原始备份地址：<https://archive.org/details/GFLFC_resourcepack_202606>
本工具包导出的已解密资源存档：<https://archive.org/details/gflfc-unpacked-resources>

- 新增 481 个 bundle，全部是已下载子包内容；
- 0 个首包 bundle 缺失；
- 6 个同名 bundle 被热更替换，共 58 项资源变化：
  - `dsversion.txt` 165085 → 165636
  - 29 个 `assemblies/android/*.dll.bytes`
  - 21 个 `configs/bin/*.bytes`
  - 4 个语言包
  - 新手引导 Graph
  - `iconitem.spriteatlas`（WA2000 009 头像条目；PNG 本体未变）
- 新增的 4,066 项资源全部能在 CDN 子包备份中找到，说明 CDN 备份无遗漏。

## 5. 常见报错

| 报错 | 原因 | 处理 |
|---|---|---|
| `decrypt.py` 跑完文件没变 | 旧版丢弃返回值 | 改为 `data = decrypt_data(data)` |
| `ValueError: bytes must be in range(0, 256)` | RGBAHalf 贴图 | 跳过或用 `struct.unpack('<e')` 转 |
| `KeyError: 'm_Name'` | 对象读取失败 | 单对象 try/except，继续下一个 |
| Mesh 导出为空 | PPtr 指向其他 bundle | 建立 CAB 索引并 BFS 加载 |
| `pip` 安装时报 `trusted-host` 解析错误 | 本机 pip.ini 行内注释 | 用 `PIP_CONFIG_FILE` 指向干净的 ini |

## 6. 合规提示

- 仅用于个人存档/研究；
- 不发布账号数据、设备信息、CDN token、个人绝对路径；
- 发布工具时不要附带游戏原始资源；
- 停服后 CDN 可能随时下线，重要内容请先本地备份。
