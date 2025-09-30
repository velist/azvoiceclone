#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入激活码到数据库
"""

import os
import sys

# 要导入的激活码
CODES_TO_IMPORT = [
    {
        "code": "63R6LT28W9JIAXGN",
        "max_voices": 1,
        "max_characters": 1000,
        "expires_at": "2025-10-03",
        "note": "用户原有激活码 1"
    },
    {
        "code": "ZDPJ0A2NRWMDY0BO",
        "max_voices": 1,
        "max_characters": 1000,
        "expires_at": "2025-10-03",
        "note": "用户原有激活码 2"
    },
]

def import_to_database():
    """导入激活码到 PostgreSQL 数据库"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("错误：未找到 DATABASE_URL 环境变量")
        print("请设置 DATABASE_URL 环境变量指向 PostgreSQL 数据库")
        return False

    try:
        from db_activation_manager import DatabaseActivationManager

        manager = DatabaseActivationManager(database_url)
        print(f"✓ 成功连接到数据库")
        print()

        for code_data in CODES_TO_IMPORT:
            try:
                # 检查激活码是否已存在
                existing = manager.get_code_info(code_data["code"])
                if existing:
                    print(f"⚠ 激活码 {code_data['code']} 已存在，跳过")
                    continue

                # 直接插入数据库
                import psycopg2
                from datetime import datetime

                with manager._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO activation_codes
                            (code, max_voices, used_voices, max_characters, used_characters,
                             expires_at, disabled, note, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            code_data["code"],
                            code_data["max_voices"],
                            0,  # used_voices
                            code_data["max_characters"],
                            0,  # used_characters
                            code_data["expires_at"],
                            False,  # disabled
                            code_data["note"],
                            datetime.utcnow()
                        ))
                        conn.commit()

                print(f"✓ 成功导入激活码: {code_data['code']}")
                print(f"  - 音色额度: {code_data['max_voices']}")
                print(f"  - 字符额度: {code_data['max_characters']}")
                print(f"  - 有效期: {code_data['expires_at']}")
                print(f"  - 备注: {code_data['note']}")
                print()

            except Exception as e:
                print(f"✗ 导入激活码 {code_data['code']} 失败: {e}")

        # 显示所有激活码
        print("=" * 60)
        print("当前数据库中的所有激活码：")
        print("=" * 60)
        all_codes = manager.list_codes()
        for code_info in all_codes:
            print(f"\n激活码: {code_info['code']}")
            print(f"  音色: {code_info['used_voices']} / {code_info['max_voices']}")
            print(f"  字符: {code_info['used_characters']} / {code_info['max_characters']}")
            print(f"  有效期: {code_info['expires_at']}")
            print(f"  状态: {'正常' if not code_info['disabled'] and not code_info['expired'] else '已禁用/过期'}")
            if code_info['note']:
                print(f"  备注: {code_info['note']}")

        print("\n" + "=" * 60)
        print(f"✓ 导入完成！共 {len(all_codes)} 个激活码")

        return True

    except ImportError:
        print("错误：未安装 psycopg2-binary")
        print("请运行：pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"错误：{e}")
        import traceback
        traceback.print_exc()
        return False


def import_to_json():
    """导入激活码到 JSON 文件（本地开发）"""
    from pathlib import Path
    from activation_manager import ActivationManager
    from datetime import datetime

    manager = ActivationManager(Path("activation_codes.json"))
    print("✓ 使用 JSON 文件存储")
    print()

    for code_data in CODES_TO_IMPORT:
        try:
            # 检查激活码是否已存在
            existing = manager.get_code_info(code_data["code"])
            if existing:
                print(f"⚠ 激活码 {code_data['code']} 已存在，跳过")
                continue

            # 读取数据
            data = manager._load_data()

            # 创建激活码记录
            record = {
                "code": code_data["code"],
                "max_voices": code_data["max_voices"],
                "used_voices": 0,
                "max_characters": code_data["max_characters"],
                "used_characters": 0,
                "expires_at": code_data["expires_at"],
                "disabled": False,
                "note": code_data["note"],
                "created_at": datetime.utcnow().isoformat(),
                "last_used_at": None
            }

            # 保存
            data["codes"][code_data["code"]] = manager._normalise_record(code_data["code"], record)
            manager._save_data(data)

            print(f"✓ 成功导入激活码: {code_data['code']}")
            print(f"  - 音色额度: {code_data['max_voices']}")
            print(f"  - 字符额度: {code_data['max_characters']}")
            print(f"  - 有效期: {code_data['expires_at']}")
            print()

        except Exception as e:
            print(f"✗ 导入激活码 {code_data['code']} 失败: {e}")

    # 显示所有激活码
    print("=" * 60)
    print("当前 JSON 文件中的所有激活码：")
    print("=" * 60)
    all_codes = manager.list_codes()
    for code_info in all_codes:
        print(f"\n激活码: {code_info['code']}")
        print(f"  音色: {code_info['used_voices']} / {code_info['max_voices']}")
        print(f"  字符: {code_info['used_characters']} / {code_info['max_characters']}")
        print(f"  有效期: {code_info['expires_at']}")

    print("\n" + "=" * 60)
    print(f"✓ 导入完成！共 {len(all_codes)} 个激活码")


if __name__ == "__main__":
    print("=" * 60)
    print("激活码导入工具")
    print("=" * 60)
    print()

    # 检测环境
    if os.getenv("DATABASE_URL"):
        print("检测到 DATABASE_URL，导入到 PostgreSQL 数据库...")
        print()
        success = import_to_database()
    else:
        print("未检测到 DATABASE_URL，导入到本地 JSON 文件...")
        print()
        import_to_json()
        success = True

    if success:
        print("\n可以访问管理后台验证激活码：")
        print("https://vipvoice3.aipush.fun/azttsadmin/")
        print("\n或访问 API 检查：")
        print("https://vipvoice3.aipush.fun/api/check_codes")