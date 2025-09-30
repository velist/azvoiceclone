#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 DEFAULT_ACTIVATION_CODES 环境变量值
用于在 Render 等临时文件系统平台上保存激活码
"""

import json
from pathlib import Path

activation_file = Path("activation_codes.json")

if not activation_file.exists():
    print("错误：activation_codes.json 文件不存在")
    print("请先在本地或管理后台创建激活码")
    exit(1)

try:
    with open(activation_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 压缩 JSON（移除空格和换行）
    compact_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

    print("=" * 80)
    print("DEFAULT_ACTIVATION_CODES 环境变量值")
    print("=" * 80)
    print()
    print("将以下内容复制到 Render 的环境变量中：")
    print()
    print("变量名: DEFAULT_ACTIVATION_CODES")
    print("变量值:")
    print()
    print(compact_json)
    print()
    print("=" * 80)
    print(f"✓ 包含 {len(data.get('codes', {}))} 个激活码")
    print()
    print("激活码列表:")
    for code, info in data.get('codes', {}).items():
        print(f"  - {code}: {info.get('note', '无备注')}")
    print()
    print("=" * 80)
    print()
    print("设置步骤：")
    print("1. 登录 Render Dashboard")
    print("2. 选择 azvoiceclone 服务")
    print("3. 进入 Environment 标签")
    print("4. 添加新环境变量：")
    print("   Key: DEFAULT_ACTIVATION_CODES")
    print("   Value: 上面显示的 JSON 字符串")
    print("5. 保存后 Render 会自动重新部署")
    print()

except Exception as e:
    print(f"错误：{e}")
    exit(1)