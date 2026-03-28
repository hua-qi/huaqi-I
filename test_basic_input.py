#!/usr/bin/env python3
"""测试基本输入"""
import sys

print("测试 1: 基本 input()")
print("> ", end="", flush=True)
try:
    result = input()
    print(f"收到: [{result}]")
except Exception as e:
    print(f"错误: {e}")
