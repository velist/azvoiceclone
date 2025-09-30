#!/usr/bin/env python3
import os
import sys

print("=" * 60)
print("环境变量测试")
print("=" * 60)

# 测试所有环境变量
print("\n所有环境变量:")
for key in ['APP_HOST', 'APP_PORT', 'API_KEY', 'ADMIN_PASSWORD', 'PORT']:
    value = os.environ.get(key, 'NOT_SET')
    if key == 'API_KEY' and value != 'NOT_SET':
        value = value[:8] + '***'
    print(f"  {key} = {value}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
sys.exit(0)