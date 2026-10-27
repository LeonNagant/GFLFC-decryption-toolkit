# 格式与算法说明

本文记录实测得到的格式细节，足以从零复现整个解密流程。

## 1. APK 结构

游戏使用 Android App Bundle 拆分的三个 APK：

| APK | 内容 |
|---|---|
| `base.apk` | 代码、Unity 启动数据、少量首包资源 |
| `split_UnityDataAssetPack.apk` | **核心资源**：`assets/Bundles/Android/` |
| `split_config.arm64_v8a.apk` | native so（`libil2cpp.so`、`libunity.so` 等） |

资源目录：

```
assets/Bundles/Android/
├── *.ab                       AssetBundle（UnityFS，XOR 加密）
├── abxxxxxzip1 ... 7          无扩展名 ZIP（内含更多 *.ab）
├── assetMapName.fb            路径映射（FlatBuffers）
├── assetbundlemetainfo.json   bundle 清单：assetPath + md5
├── assetbundlestateinfo.json  appversion / 已解压文件列表
└── IndependentBundles.json    独立 bundle 列表
```

`assetbundlestateinfo.json` 可直接读出客户端版本，例如：

```json
{"appversion":"0.5.3","untracted_size":1332258817,
 "zipnames":["assetbundlezipdefaultname"],"untracted_assetbundle":["1044748e.ab", ...]}
```

## 2. XOR 加密

所有 `.ab`（包括内层 ZIP 里的）都是**同一套循环 XOR**：

```python
KEY = b'sdfsdfsdfweerterewwr9ikieioerf...'   # 长度 132
MAGIC = b'&\x0A\x0F\x07\x1D  d'              # 加密后的文件头

def decrypt(data):
    if data[:8] != MAGIC:
        return data
    return bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(data))
```

要点：

1. **先判魔数**：只有以 `26 0A 0F 07 1D 20 20 64` 开头的文件才需要解密；
   解密后头 8 字节为 `UnityFS\0`。
2. **从头开始**：每个文件独立，XOR 位置从 `KEY[0]` 重新计算。
3. **原地修改陷阱**：gffcdl 早期版本的 `decrypt(path)` 丢弃了
   `decrypt_data()` 的返回值，导致“命令行跑完但文件没变”。本工具包的
   `decrypt.py` 已修复为 `data = decrypt_data(data)`。
4. **性能**：逐字节 Python 循环很慢。可用
   `bytes.translate` 按 `i % 132` 分组，或大整数异或：

```python
n = len(data)
pad = (KEY * (n // len(KEY) + 1))[:n]
plain = (int.from_bytes(data, "little") ^
         int.from_bytes(pad, "little")).to_bytes(n, "little")
```

40 MB 文件约 0.16 秒。

## 3. 内层 ZIP

`abxxxxxzip1..7` 没有扩展名，但 `zipfile.is_zipfile()` 为真。内部通常是
`<hash>.ab`。先解 ZIP，再对解出的 `.ab` 做同样的 XOR 解密。

## 4. UnityFS 与导出

解密后的文件是标准 UnityFS（Unity 2022.3.x，IL2CPP）。用 UnityPy：

```python
import UnityPy
env = UnityPy.load("plain.ab")
for obj in env.objects:
    if obj.type.name == "Mesh":
        obj.read().export("obj")
    elif obj.type.name == "Texture2D":
        obj.read().image.save("tex.png")
```

`obj.container` 是该对象在 AssetBundle 里的资源路径（如
`assets/gameres/gameresmobile/battle/avatar/player/hg_m1895/...`），
导出时优先用它作为目录结构，避免同名覆盖。

## 5. SubpackageBundleInfo.fb

FlatBuffers 文件，没有公开 schema。实测结构（root table 两个 vector）：

```
root[0] 子包表，每项：
  [0] tag        string   例：avatar_hg_m1895_003
  [1] segment    string   例：avatar_hg_m1895_003_<md5>_<hash>.subpackage_segment
  [3] md5        string   整个 segment 的 MD5
  [4] size       uint32
  [6] files      vector<File>
        [0] file   string  <hash>.ab
        [3] offset uint64
        [5] md5    string
        [6] size   uint64

root[1] 依赖表，每项：
  [0] tag        string
  [1] deps       vector<string>
```

解析方法见 `scripts/parse_subpackage_fb.py`：利用 FlatBuffers 的
vtable（`soffset` 指向 vtable，vtable 头部为 vtable_size/table_size，
后续为各字段偏移）做无 schema 读取。

## 6. `.subpackage_segment` 格式

**它不是 ZIP，也不是单个 bundle**，而是多个 UnityFS 文件首尾相接：

```
[加密 bundle 0][加密 bundle 1][加密 bundle 2]...
```

每个 bundle 都独立 XOR，且**都从 KEY[0] 重新开始**。因此：

- 对整个文件做一次 XOR → 只有第 1 个 bundle 正确，后续全坏；
- 正确做法：搜索加密魔数 `26 0A 0F 07 1D 20 20 64` 得到切分点，
  逐段 XOR，再校验每段 UnityFS header 声明的大小。

```python
offs = []
i = 0
while True:
    j = data.find(MAGIC, i)
    if j < 0: break
    offs.append(j); i = j + 1
offs.append(len(data))
chunks = [data[offs[k]:offs[k+1]] for k in range(len(offs)-1)]
```

切分后每个 chunk 的文件名可对应 fb 里的 `files[].file`。

## 7. CDN 子包协议

从 `HotfixLocalConfig.json` 读取：

```json
{"serverUrls":["https://net-cdn.hecategames.com/prod"],"channelId":"android"}
```

URL 模板：

```
{serverUrls[0]}/{channelId}/subpackage/{segment}
```

实测可用端点：

| 路径 | 内容 |
|---|---|
| `/prod/android/version.json` | 版本清单 |
| `/prod/android/patch.json` | 热更清单 |
| `/prod/android/<version>/<md5>.zpf` | ZIP 包（内含若干 `.ab`） |
| `/prod/android/subpackage/<segment>` | 子包段（皮肤/活动） |

客户端在 `OuterPackage/` 下为每个子包维护
`<tag>_subpackage_chunk_state`，内容形如：

```
0bcf6306b47cadf96ccf16caaff012be,1
```

可以据此判断某个账号实际下载了哪些子包。

## 8. 跨 bundle 依赖

皮肤 bundle 的 `SkinnedMeshRenderer.m_Mesh` 是指向其他 bundle 的 PPtr。
`SerializedFile.externals` 里记录了目标 CAB 名（`CAB-xxxxxxxx...`）。
只加载本 tag 的 bundle 时，Mesh 会解析不到。

解决办法：

1. 建立 `CAB 名 -> bundle 文件` 索引（扫描所有 bundle 的二进制找 `CAB-`）；
2. 从当前 bundle 出发 BFS，遇到 externals 就加载对应 bundle；
3. 在完整的 `UnityPy.Environment` 上导出。

`export_subpackage.py` 已实现该逻辑。

## 9. 版本差异与比对

同一个 container 路径在不同版本可能对应不同内容。可靠比对方法：

- **文件级**：先解密再比 MD5（不要比加密文件，除非两边都加密）；
- **资源级**：以 `container` 路径为 key，比较对象类型 + `obj.get_raw_data()` 的 MD5；
- **完整性**：UnityFS header 声明大小 == 文件实际大小。

实测：

- v0.4.1 首包 795 个 bundle，约 47.5 万对象；
- v0.5.3 首包 1025 个 bundle，约 59.4 万对象；
- 玩家完整运行数据 1506 个 bundle，约 73.4 万对象（含已下载子包）。
