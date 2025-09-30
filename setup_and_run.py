#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

def install_packages():
    """安装必要的包"""
    packages = ['gradio', 'requests', 'python-dotenv']

    print("="*50)
    print("  安装TTS系统依赖包")
    print("="*50)

    for package in packages:
        print(f"\n安装 {package}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ {package} 安装成功")
        except subprocess.CalledProcessError:
            print(f"✗ {package} 安装失败，请手动运行: pip install {package}")
            return False

    print("\n" + "="*50)
    print("  所有依赖包安装完成！")
    print("="*50)
    return True

def run_app():
    """运行应用"""
    print("\n" + "="*50)
    print("  启动TTS声音合成系统")
    print("="*50)
    print()

    # 检查app_simple.py是否存在
    if not os.path.exists('app_simple.py'):
        print("错误：找不到 app_simple.py 文件")
        return

    try:
        subprocess.call([sys.executable, 'app_simple.py'])
    except KeyboardInterrupt:
        print("\n\n程序已停止")
    except Exception as e:
        print(f"运行出错: {e}")

def main():
    print("TTS声音合成系统 - 安装和启动工具\n")

    choice = input("请选择操作：\n1. 安装依赖包\n2. 直接运行程序\n3. 安装并运行\n请输入选项 (1/2/3): ").strip()

    if choice == '1':
        install_packages()
    elif choice == '2':
        run_app()
    elif choice == '3':
        if install_packages():
            run_app()
    else:
        print("无效选项")

if __name__ == "__main__":
    main()
    input("\n按Enter键退出...")