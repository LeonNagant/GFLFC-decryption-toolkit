# AI 辅助开发说明 / AI-Assisted Development Note

[中文](#中文) · [English](#english)

---

## 中文

### 1. 结论先行

本仓库的脚本、格式分析和文档，是在一个**本地运行的 AI 编程助手**（agent 形态，
具备文件读写、命令执行、调试器操作能力）深度参与下完成的。人负责目标、判断与验收；
AI 负责侦察、试错、编码和写作。

这不是"AI 生成了代码我贴上来"，而是**人在回路（human-in-the-loop）的协作**：
每一步结论都要由真实执行结果支撑，跑不通就改，改完再跑。

### 2. 分工

| 环节 | AI | 人 |
|---|---|---|
| 目标设定 | — | ✅ 要备份哪些内容、优先级 |
| 环境准备 | 建议依赖与虚拟环境 | ✅ 实际搭建、提供样本 |
| 静态侦察 | ✅ 读清单、找密钥来源、定位资源目录 | 抽查 |
| 格式逆向 | ✅ 提出假设、设计验证实验、推翻错误假设 | 判断结论是否可信 |
| 编码 | ✅ 全部脚本 | 复核关键逻辑 |
| 执行 | ✅ 批量下载/解密/导出、读报错、修 bug | 决定是否重跑 |
| 验收 | 输出统计与自检 | ✅ 在真机上打开 OBJ/PNG 确认可用 |
| 文档 | ✅ 全部 Markdown | 校对、删改 |

### 3. AI 实际解决的问题（附证据）

**3.1 定位加密方式**

`assets/Bundles/Android/*.ab` 的头部不是 `UnityFS`。AI 的做法是：
把已知的 UnityFS 头 `UnityFS\0` 与文件头做 XOR，得到一个 8 字节序列
`&\x0A\x0F\x07\x1D  d`；用这个序列反推，确认是**全文件循环 XOR**，
密钥来自 gffcdl 项目，长度 132 字节。

判据：解密后前 8 字节必须等于 `UnityFS\0`，且 UnityFS header 里声明的大小
等于文件实际大小。两个判据同时成立才算通过。

**3.2 推翻"子包是 ZIP"的错误假设**

`.subpackage_segment` 最初被当成 ZIP（因为它是 CDN 下发的"包"），
但文件头不是 `PK\x03\x04`。AI 设计了对照实验：

- 对整个文件做一次 XOR → 第 1 段头部变成 `UnityFS\0`，第 2 段开始仍是乱码；
- 说明是**多段串联**，且每段的 XOR 都从 `KEY[0]` 重新开始；
- 按加密魔数 `&\x0A\x0F\x07\x1D  d` 切分后，39 个段全部 header 自洽。

这个结论改变了整个子包处理流程（先切分，再逐段解密）。

**3.3 无 schema 解析 FlatBuffers**

`SubpackageBundleInfo.fb` 没有公开的 `.fbs`。AI 的做法是手工读 vtable：

- 从文件头解析 root table 偏移；
- 读 vtable 的字段偏移表，按 `offset` 是否为 0 判断字段是否存在；
- 用类型试探（string / vector / table）逐个字段确认语义，得到
  子包表（tag、segment 名、MD5、大小、内部文件表）与依赖表两张结构。

解析结果与实际下载的 222 个子包全部对上，MD5 校验通过，反证了字段推断正确。

**3.4 跨 bundle 依赖（导出为空 OBJ）**

部分皮肤 bundle 的 Mesh PPtr 指向另一个 bundle 的 CAB。AI 的处理：

1. 扫描所有 bundle，建立 `CAB-xxxx -> bundle` 索引；
2. 从目标 bundle 的 `SerializedFile.externals` 出发做 BFS；
3. 只导出 container 命中当前 tag 的对象，依赖 Mesh 落到 `shared_models/`。

案例：M1895 的 5 套角色皮肤里，`fb` 依赖表只写了 `009 -> 003`，
但 004/006/007 的 Mesh 同样指向 003 的 CAB，靠 BFS 才补全。

**3.5 已知失败**

603 个 `RampMap_Linear_RGBAHalf` 贴图无法转 PNG（`TextureFormat=17`，
UnityPy/Pillow 报 `ValueError: bytes must be in range(0, 256)`）。
AI 尝试过先转 `float32` 再走 PIL，仍然失败；最终选择跳过并记录，
原始数据保留在 bundle 内。**这条没有解决**，写在这里而不是藏起来。

### 4. AI 犯过的错（同样保留）

| 错误 | 表现 | 修正 |
|---|---|---|
| `decrypt.py` 丢弃返回值 | 跑完文件没变，静默失败 | 改为 `data = decrypt_data(data)` 再写回 |
| 把子包当 ZIP | 解压报错、格式对不上 | 改判为多段 UnityFS 串联 |
| 用密文 MD5 比对版本 | 1025 个 bundle 全部"被改动" | 先解密再比 MD5，真实改动只有 6 个 |
| 容器继承条件写反 | 漏掉只存在于新版本的容器 | 改为集合包含关系取反 |
| 分类函数把无路径对象全归到 `misc/` | 68,092 项错分 | 改为按扩展名分流 |

### 5. 为什么保留这些记录

1. **可复现**：别人按文档跑，得到的数字应该和 `docs/notes.md` 一致；
   不一致就说明版本或环境不同，而不是"文档在吹"。
2. **可评估**：想知道 AI 辅助逆向到底能做到什么程度，看错误清单比看成功清单更有用。
3. **可追责**：每条结论都能回溯到具体的执行结果，没有"大概是吧"。

### 6. 合规边界

- 仓库**不含**任何游戏资源、账号数据、设备标识、CDN token、个人绝对路径；
- 工具仅用于个人研究、存档与格式分析；
- 解包产物请勿商用或再分发，版权归原开发/发行方所有。

---

## English

### 1. Bottom line

The scripts, format analysis and documentation in this repository were produced with
deep involvement of a **locally running AI coding agent** — one with file access,
shell execution and debugger control. The human set the goals, made the judgement
calls, and accepted the results; the AI did the reconnaissance, trial and error,
coding and writing.

This is not "the AI wrote code and I pasted it". It is a
**human-in-the-loop collaboration**: every conclusion is backed by a real execution,
and anything that did not run was fixed and re-run.

### 2. Division of labour

| Stage | AI | Human |
|---|---|---|
| Goal setting | — | ✅ what to back up, priorities |
| Environment | suggested deps and venv | ✅ actually set it up, supplied samples |
| Static recon | ✅ read manifests, find key source, locate asset dirs | spot checks |
| Format reverse engineering | ✅ form hypotheses, design experiments, discard wrong ones | judged credibility |
| Coding | ✅ all scripts | reviewed critical logic |
| Execution | ✅ batch download/decrypt/export, read errors, fix bugs | decided when to re-run |
| Acceptance | produced stats and self-checks | ✅ opened OBJ/PNG on real hardware |
| Documentation | ✅ all Markdown | proofread, edited |

### 3. Problems the AI actually solved (with evidence)

**3.1 Locating the encryption**

`assets/Bundles/Android/*.ab` do not start with `UnityFS`. The AI XORed the known
UnityFS header `UnityFS\0` against the file header, obtaining the 8-byte sequence
`&\x0A\x0F\x07\x1D  d`, and worked backwards to confirm a **whole-file cyclic XOR**
with a 132-byte key (originating from the gffcdl project).

Acceptance criteria: the first 8 bytes must equal `UnityFS\0` **and** the size declared
in the UnityFS header must equal the actual byte length. Both must hold.

**3.2 Discarding the "subpackages are ZIPs" hypothesis**

`.subpackage_segment` was initially treated as a ZIP (it is, after all, a "package"
delivered over CDN), but its header is not `PK\x03\x04`. The AI designed a control
experiment:

- XOR the whole file once → segment 1 starts with `UnityFS\0`, segment 2 onward is garbage;
- therefore it is **multiple concatenated segments**, each restarting the XOR at `KEY[0]`;
- after splitting on the encrypted magic `&\x0A\x0F\x07\x1D  d`, all 39 segments had
  self-consistent headers.

This changed the entire subpackage pipeline (split first, decrypt per segment).

**3.3 Schema-less FlatBuffers parsing**

`SubpackageBundleInfo.fb` has no published `.fbs`. The AI read the vtable by hand:

- parse the root table offset from the file header;
- read the vtable's field-offset table, treating `offset == 0` as "field absent";
- probe types (string / vector / table) to determine each field's meaning, arriving at
  a subpackage table (tag, segment name, MD5, size, inner file table) and a dependency table.

The parse matched all 222 downloaded subpackages with MD5 verification passing, which
confirms the field inference.

**3.4 Cross-bundle dependencies (empty OBJ exports)**

Some skin bundles have Mesh PPtrs pointing at a CAB in another bundle. The approach:

1. scan all bundles, build a `CAB-xxxx -> bundle` index;
2. BFS outward from the target bundle's `SerializedFile.externals`;
3. export only objects whose container matches the current tag; dependency meshes go to `shared_models/`.

Case study: of the five M1895 character skins, the `fb` dependency table only records
`009 -> 003`, yet the meshes of 004/006/007 also point at 003's CAB — only BFS recovered them.

**3.5 A known failure**

603 `RampMap_Linear_RGBAHalf` textures cannot be converted to PNG (`TextureFormat=17`;
UnityPy/Pillow raises `ValueError: bytes must be in range(0, 256)`). Converting to
`float32` first and then going through PIL also failed. The final decision was to skip
them and document it; the raw data remains inside the bundles. **This one is unsolved**,
and it is written down rather than hidden.

### 4. Mistakes the AI made (kept on purpose)

| Mistake | Symptom | Fix |
|---|---|---|
| `decrypt.py` discarded the return value | file unchanged, silent failure | `data = decrypt_data(data)` then write back |
| Treated subpackages as ZIP | extraction errors, format mismatch | reclassified as concatenated UnityFS |
| Compared ciphertext MD5 across versions | all 1025 bundles appeared "changed" | decrypt first, then compare — only 6 real changes |
| Inverted the container-inheritance predicate | containers present only in the new version were dropped | negated the set-containment test |
| Classifier dumped path-less objects into `misc/` | 68,092 misclassified files | split by file extension instead |

### 5. Why keep these records

1. **Reproducibility** — following the docs should yield numbers matching
   `docs/notes.md`. A mismatch means a different version or environment, not that
   the docs are inflated.
2. **Evaluability** — to judge what AI-assisted reverse engineering can actually do,
   the error list is more informative than the success list.
3. **Accountability** — every claim traces back to a concrete execution result.
   Nothing is "probably".

### 6. Compliance boundaries

- This repository contains **no** game assets, account data, device identifiers,
  CDN tokens, or personal absolute paths;
- The tooling is for personal research, archiving and format analysis only;
- Do not use extracted assets commercially or redistribute them; all rights remain
  with the original developer/publisher.
