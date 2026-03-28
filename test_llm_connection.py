#!/usr/bin/env python3
"""测试 LLM API 连接

使用方法:
    python3 test_llm_connection.py

支持的环境变量:
    WQ_API_KEY: 万擎 API 密钥
"""

import os
import sys


def test_import():
    """测试 openai 包是否安装"""
    print("=" * 50)
    print("[1/5] 检查 openai 包...")
    try:
        from openai import OpenAI
        print("  ✅ openai 包已安装")
        return True
    except ImportError:
        print("  ❌ openai 包未安装")
        print("  请运行: pip install openai")
        return False


def test_api_key():
    """测试 API Key 是否配置"""
    print("\n[2/5] 检查 API Key...")
    api_key = os.environ.get("WQ_API_KEY")
    if api_key:
        print(f"  ✅ API Key 已配置: {api_key[:8]}...{api_key[-4:]}")
        return api_key
    else:
        print("  ❌ API Key 未配置")
        print("  请设置环境变量:")
        print("    export WQ_API_KEY=sk-xxx")
        return None


def test_api_base():
    """测试 API Base"""
    print("\n[3/5] 检查 API Base...")
    # 办公网调用地址
    api_base = "https://wanqing-api.corp.kuaishou.com/api/gateway/v1/endpoints"
    print(f"  ✅ 使用内网 API Base: {api_base}")
    return api_base


def test_connection(api_key, api_base):
    """测试 API 连接"""
    print("\n[4/5] 测试 API 连接...")
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=30,
        )

        # 尝试调用 API
        response = client.chat.completions.create(
            model="ep-czo1x9-1774507780045283571",
            messages=[
                {"role": "system", "content": "你是一个 AI 人工智能助手"},
                {"role": "user", "content": "你好"},
            ],
            max_tokens=10,
        )

        print("  ✅ API 连接成功!")
        print(f"  模型: {response.model}")
        print(f"  回复: {response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"  ❌ API 连接失败: {e}")

        error_msg = str(e).lower()
        if "connection" in error_msg or "timed out" in error_msg:
            print("\n  可能原因:")
            print("  1. 不在办公网环境（需要连接公司网络或 VPN）")
            print("  2. DNS 解析失败（尝试使用 IP 或检查网络配置）")

        if "authentication" in error_msg or "api key" in error_msg:
            print("\n  可能原因:")
            print("  1. API Key 无效或已过期")

        return False


def test_streaming(api_key, api_base):
    """测试流式 API 调用"""
    print("\n[5/5] 测试流式调用...")
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=30,
        )

        stream = client.chat.completions.create(
            model="ep-czo1x9-1774507780045283571",
            messages=[
                {"role": "system", "content": "你是一个 AI 人工智能助手"},
                {"role": "user", "content": "请用两个字回复"},
            ],
            max_tokens=10,
            stream=True,
        )

        content = ""
        for chunk in stream:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content

        print(f"  ✅ 流式调用成功! 收到内容: '{content}'")
        return True

    except Exception as e:
        print(f"  ❌ 流式调用失败: {e}")
        return False


def main():
    """主函数"""
    print("Huaqi LLM 连接测试")

    # 检查依赖
    if not test_import():
        sys.exit(1)

    # 检查配置
    api_key = test_api_key()
    if not api_key:
        sys.exit(1)

    api_base = test_api_base()

    # 测试连接
    if not test_connection(api_key, api_base):
        sys.exit(1)

    # 测试流式
    test_streaming(api_key, api_base)

    print("\n" + "=" * 50)
    print("测试完成! 如果上述都通过，LLM 应该可以正常工作。")
    print("=" * 50)


if __name__ == "__main__":
    main()
