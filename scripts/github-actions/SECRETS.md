# GitHub Actions Secrets 配置说明

定时任务迁移至 GitHub Actions 需要在数据仓库中配置以下 Secrets。

## Secrets 清单

| Secret 名称 | 用途 | 获取方式 |
|-------------|------|---------|
| `OPENAI_API_KEY` | LLM API 密钥（报告生成需要） | OpenAI / Kimi 等平台获取 |
| `SERVERCHAN_KEY` | Server酱 SendKey（微信通知推送） | [sct.ftqq.com](https://sct.ftqq.com/) 登录后获取 |

## 配置步骤

1. 打开数据仓库的 GitHub 页面
2. 进入 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 逐个添加上述 Secret：

```
Name:  OPENAI_API_KEY
Value: sk-xxxxxxxxxxxxxxxx

Name:  SERVERCHAN_KEY
Value: SCT123456xxxxxxxx
```

## 验证

配置完成后，在 Actions 页面手动触发任意 workflow（`workflow_dispatch`），观察：
- 报告是否成功生成
- 微信是否收到 Server酱 推送通知

## 安全提醒

- Secrets 仅在 workflow 运行时解密，GitHub 不会在日志中打印 Secret 值
- 请勿在 workflow YAML 中硬编码 API Key
- 定期轮换 API Key 以降低泄露风险
