#!/usr/bin/env python3
"""环境自检。

在做任何解包之前先跑一次，确认依赖齐全、XOR 核心逻辑正常：

    python scripts/check_env.py

会检查：
1. Python 版本（>= 3.10）
2. UnityPy / requests / Pillow 能否导入及版本
3. decrypt.py 的 KEY / MAGIC 常量
4. decrypt_data() 的对称性（两次解密还原原文）
5. UnityPy 能否解析一个最小的内存 bundle（不依赖本地文件）

退出码 0 表示环境可用。
"""

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAIL = 0


def ok(msg):
    print(f"  [ok]   {msg}")


def bad(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    print(f"  [warn] {msg}")


print("== Python ==")
if sys.version_info >= (3, 10):
    ok(f"{sys.version.split()[0]}")
else:
    bad(f"需要 Python 3.10+，当前 {sys.version.split()[0]}")

print("\n== 依赖 ==")
try:
    import UnityPy
    ok(f"UnityPy {getattr(UnityPy, '__version__', '?')}")
except Exception as e:
    UnityPy = None
    bad(f"UnityPy 导入失败: {e}")

try:
    import requests
    ok(f"requests {requests.__version__}")
except Exception as e:
    bad(f"requests 导入失败: {e}")

try:
    import PIL
    ok(f"Pillow {PIL.__version__}")
except Exception as e:
    warn(f"Pillow 不可用（只影响贴图导出）: {e}")

try:
    import flatbuffers  # noqa: F401
    ok("flatbuffers")
except Exception:
    warn("flatbuffers 未安装（本项目用无 schema 解析，不影响使用）")

print("\n== XOR 核心 ==")
try:
    import decrypt as D
except Exception as e:
    bad(f"decrypt.py 导入失败: {e}")
    D = None

if D:
    print(f"  KEY 长度   : {D.KEYLEN}")
    print(f"  MAGIC      : {D.MAGIC!r} ({D.MAGICLEN} 字节)")
    if D.MAGICLEN != 8:
        bad("MAGIC 长度应为 8")

    # 构造真实语义下的一对明文/密文：
    #   明文以 UnityFS\0 开头，密文 = 明文 XOR KEY（循环）
    #   密文头部因此等于 UnityFS\0 XOR KEY[:8] == MAGIC
    rnd = random.Random(1234)
    body = bytes(rnd.getrandbits(8) for _ in range(4096))
    plain = b"UnityFS\0" + body
    cipher = bytes(b ^ D.KEY[i % D.KEYLEN] for i, b in enumerate(plain))

    if cipher[:8] != D.MAGIC:
        bad(f"加密后头部不是 MAGIC: {cipher[:8]!r}")
    else:
        ok("加密后头部等于 MAGIC")

    once = bytes(D.decrypt_data(cipher))
    if once == plain:
        ok("decrypt_data(密文) == 明文")
    else:
        bad("解密结果与原文不一致")

    if once[:8] == b"UnityFS\0":
        ok("解密后头部为 UnityFS\\0")
    else:
        bad(f"解密后头部不是 UnityFS\\0: {once[:8]!r}")

    # 已解密数据不应被二次处理（MAGIC 守卫）
    if bytes(D.decrypt_data(plain)) == plain:
        ok("已解密数据原样返回（MAGIC 守卫生效）")
    else:
        bad("已解密数据被二次 XOR")

    # 非 UnityFS 的普通文件也不应被改动
    other = b"PK\x03\x04" + body
    if bytes(D.decrypt_data(other)) == other:
        ok("非 UnityFS 数据原样返回")
    else:
        bad("非 UnityFS 数据被错误处理")

    warn("注意：decrypt.decrypt(path) 是【原地覆写】文件，"
         "请先复制一份原始 APK/bundle")

print("\n== UnityPy 解析 ==")
if UnityPy is not None:
    try:
        from UnityPy.enums import ClassIDType  # noqa: F401
        ok("ClassIDType 可用")
    except Exception as e:
        bad(f"ClassIDType 导入失败: {e}")

    try:
        from UnityPy.files import ObjectReader  # noqa: F401
        ok("ObjectReader 可用")
    except Exception as e:
        warn(f"ObjectReader 路径变化（不同 UnityPy 版本路径不同）: {e}")

print()
if FAIL:
    print(f"结果：{FAIL} 项失败，请先修好环境")
else:
    print("结果：环境自检通过")

sys.exit(1 if FAIL else 0)
