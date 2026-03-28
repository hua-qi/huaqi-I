#!/usr/bin/env python3
"""测试 LLM 连接"""
import sys
sys.path.insert(0, '.')

from huaqi_src.core.llm import LLMManager, LLMConfig, Message

print("=== 测试 LLM 连接 ===\n")

manager = LLMManager()

# 从配置读取
import yaml
config_path = "/Users/lianzimeng/workspace/huaqi/memory/config.yaml"
with open(config_path) as f:
    data = yaml.safe_load(f)

provider_data = data['llm_providers']['openai']
print(f"提供商: openai")
print(f"模型: {provider_data['model']}")
print(f"地址: {provider_data['api_base']}")
print(f"API Key: {provider_data['api_key'][:10]}...")

config = LLMConfig(
    provider='openai',
    model=provider_data['model'],
    api_key=provider_data['api_key'],
    api_base=provider_data['api_base'],
    temperature=provider_data['temperature'],
    max_tokens=provider_data['max_tokens'],
)

manager.add_config(config)
manager.set_active('openai')

print("\n=== 发送测试消息 ===")
messages = [
    Message.system("你是一个AI助手"),
    Message.user("你好")
]

print("开始流式输出...")
for chunk in manager.chat(messages, stream=True):
    print(chunk, end='', flush=True)
print("\n=== 完成 ===")
