#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键恢复激活码到 Render PostgreSQL 数据库
"""

import os
import sys

# 固定的激活码数据
RESTORE_CODES = [
    ("63R6LT28W9JIAXGN", 1, 1000, "2025-10-03", "用户原有激活码 1"),
    ("ZDPJ0A2NRWMDY0BO", 1, 1000, "2025-10-03", "用户原有激活码 2"),
]

def main():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL not found")
        sys.exit(1)

    try:
        import psycopg2
        from datetime import datetime

        conn = psycopg2.connect(database_url)
        print(f"Connected to database")

        with conn.cursor() as cur:
            # 确保表存在
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activation_codes (
                    code VARCHAR(50) PRIMARY KEY,
                    max_voices INTEGER NOT NULL DEFAULT 0,
                    used_voices INTEGER NOT NULL DEFAULT 0,
                    max_characters INTEGER NOT NULL DEFAULT 0,
                    used_characters INTEGER NOT NULL DEFAULT 0,
                    expires_at DATE,
                    disabled BOOLEAN NOT NULL DEFAULT FALSE,
                    note TEXT DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMP
                )
            """)
            conn.commit()
            print("Table ready")

            # 插入激活码
            for code, max_voices, max_chars, expires, note in RESTORE_CODES:
                try:
                    cur.execute("""
                        INSERT INTO activation_codes
                        (code, max_voices, used_voices, max_characters, used_characters,
                         expires_at, disabled, note, created_at)
                        VALUES (%s, %s, 0, %s, 0, %s, FALSE, %s, NOW())
                        ON CONFLICT (code) DO NOTHING
                    """, (code, max_voices, max_chars, expires, note))

                    if cur.rowcount > 0:
                        print(f"Imported: {code}")
                    else:
                        print(f"Skipped (exists): {code}")

                except Exception as e:
                    print(f"Error importing {code}: {e}")

            conn.commit()

            # 显示所有激活码
            cur.execute("SELECT code, max_voices, max_characters, expires_at FROM activation_codes")
            rows = cur.fetchall()

            print("\n--- All codes in database ---")
            for row in rows:
                print(f"{row[0]}: {row[1]} voices, {row[2]} chars, expires {row[3]}")

            print(f"\nTotal: {len(rows)} codes")

        conn.close()
        print("\nSuccess!")

    except ImportError:
        print("ERROR: psycopg2 not installed")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()