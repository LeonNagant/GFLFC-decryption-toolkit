# 完整操作流程

从零开始到导出可用模型/贴图，按顺序执行即可。

## 0. 准备

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

把 APK 放进 `apk/`，脚本放进 `scripts/`。

## 1. 确认版本

```bash
unzip -p apk/split_UnityDataAssetPack.apk \
  assets/Bundles/Android/assetbundlestateinfo.json | head -c 200
```

`appversion` 即客户端版本。不同版本 bundle 名与内容都可能变化，后续比对要记录版本。

## 2. 解包 APK

```bash
python scripts/unpack_apk.py \
  --apk apk/split_UnityDataAssetPack.apk \
  --out work/
```

检查：

```bash
python - <<'EOF'
from pathlib import Path
n = 0
bad = 0
for p in Path("work/bundles_decrypted").rglob("*.ab"):
    n += 1
    if p.read_bytes()[:8] != b"UnityFS\0":
        bad += 1
print(n, "bundles, bad headers:", bad)
EOF
```

预期 `bad headers: 0`。

## 3. 建索引

```bash
python scripts/index_bundles.py \
  --bundles work/bundles_decrypted \
  --out work/_index.jsonl
```

用索引先搜目标，不要盲目全量导出：

```bash
grep -i "m1895" work/_index.jsonl | head
```

每行是一个 bundle 的对象数组；`container` 即资源路径。

## 4. 导出

```bash
python scripts/export_bundles.py \
  --bundles work/bundles_decrypted \
  --out work/exported
```

常见问题：

| 现象 | 原因 | 处理 |
|---|---|---|
| `ValueError: bytes must be in range(0, 256)` | RGBAHalf 贴图 | 原始数据仍在 bundle，需自行转 16-bit |
| OBJ 为空/很小 | Mesh 在别的 bundle | 用 `export_subpackage.py` 的依赖闭包，或先加载 externals |
| 同名文件被覆盖 | 同一 bundle 内重名 | 用 `container` 路径 + `path_id` 命名 |
| 文本乱码 | TextAsset 是二进制 | 按 `m_Script.encode('utf-8','surrogateescape')` 原样写出 |

## 5. 子包（皮肤/活动）

### 5.1 取配置

从 APK 中取出：

```
assets/Assets/CSnapAssetSetting/HotfixLocalConfig.json
assets/Assets/CSnapAssetSetting/SubpackageBundleInfo.fb
```

### 5.2 解析清单

```bash
python scripts/parse_subpackage_fb.py \
  --fb SubpackageBundleInfo.fb \
  --out work/subpackage_info.json
```

输出包含每个 tag 的 segment 名、MD5、大小、内部文件表，以及 tag 依赖表。

### 5.3 下载

```bash
# 按关键词
python scripts/dl_subpackage.py \
  --config HotfixLocalConfig.json \
  --info work/subpackage_info.json \
  --out work/subpackage/ \
  --match hg_m1895

# 或指定 tag
python scripts/dl_subpackage.py ... \
  --tag avatar_hg_m1895_003 --tag weapon_m1895_cloud
```

下载后会校验 MD5。

### 5.4 切分 + 解密

```bash
python scripts/split_subpackage.py \
  --segments work/subpackage/ \
  --info work/subpackage_info.json \
  --out work/subpackage_bundles/
```

每个 tag 一个子目录，文件名形如 `00_<hash>.ab`。
脚本会校验每个 bundle 的 header 大小。

### 5.5 导出

```bash
python scripts/export_subpackage.py \
  --bundles work/subpackage_bundles/ \
  --info work/subpackage_info.json \
  --deps work/subpackage_info_deps.json \
  --out work/exported_subpackage/ \
  --match hg_m1895
```

脚本会：

1. 按依赖表递归加载相关 tag；
2. 扫描所有 bundle 建立 `CAB -> bundle` 索引；
3. 按 `externals` BFS 补齐跨 bundle 依赖；
4. 只导出 container 命中当前 tag 的对象，依赖 Mesh 落到 `shared_models/`。

## 6. 版本比对

推荐流程：

1. 两边都先解密；
2. 文件级：`md5(decrypted_a) == md5(decrypted_b)`；
3. 资源级：以 container 为 key，比较 `type + md5(obj.get_raw_data())`；
4. 输出新增/删除/修改三张表。

注意：不要直接比较加密文件的 MD5 来判断内容是否相同——只要任一边重新打包，
密文就会不同；但同一版本的原样拷贝可以比密文。

## 7. 发布前的自检

- [ ] 所有 bundle 解密后头 8 字节为 `UnityFS\0`
- [ ] 每个 bundle header 声明大小 == 实际大小
- [ ] 索引解析错误为 0
- [ ] 抽样 OBJ 能在 Blender 打开、PNG 能正常显示
- [ ] 不包含账号信息、设备信息、CDN token、个人路径
- [ ] 不包含游戏原始资源（如果只发布工具）
