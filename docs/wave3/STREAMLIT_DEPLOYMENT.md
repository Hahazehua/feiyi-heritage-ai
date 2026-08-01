# Streamlit Cloud 部署指南

## 部署配置

1. 将当前分支合并或推送到准备部署的 GitHub 仓库。
2. 在 Streamlit Community Cloud 选择该仓库和实际部署分支。
3. Main file path 填写 `app.py`。
4. Python 选择 3.11；本项目发布检查使用 Python 3.11.4。
5. 保存后等待构建，并从日志确认 editable package 安装成功。

`requirements.txt` 会先安装当前项目，再将 Streamlit 固定到仓库已验证版本。`pyproject.toml` 是应用及其余依赖的来源。

## Secrets 示例

以下均为占位符，不要把真实值提交到 Git：

```toml
DEEPSEEK_API_KEY = "<DEEPSEEK_API_KEY>"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
LLM_ENABLED = "true"

AGENT_REVIEW_MODE_ENABLED = "false"
AGENT_REVIEW_TOKEN = "<OPTIONAL_REVIEW_TOKEN>"

ANALYTICS_ENABLED = "false"
ANALYTICS_BACKEND = "auto"
ANALYTICS_DATABASE_URL = "<OPTIONAL_DATABASE_URL>"
ANALYTICS_STORE_RAW_CHAT = "false"
APP_VERSION = "0.1.0"
```

- 无 DeepSeek Key：自动使用确定性本地解析器，推荐和方案仍可运行。
- 无分析数据库：保持 `ANALYTICS_ENABLED=false`；授权记录跳过或安全降级，不阻断客户流程。
- 原始聊天不会写入分析库；`ANALYTICS_STORE_RAW_CHAT` 必须保持 `false`。

## 访问地址

- 普通客户模式：`<LIVE_DEMO_URL>`
- 评审模式：`<LIVE_DEMO_URL>/?review_mode=1`
- 配置 Token 时：`<LIVE_DEMO_URL>/?review_mode=1&review_token=<REVIEW_TOKEN>`
- 最终提交用评审地址：`<REVIEW_MODE_URL>`

评审模式必须同时满足服务端 `AGENT_REVIEW_MODE_ENABLED=true` 和 URL `review_mode=1`。若配置 `AGENT_REVIEW_TOKEN`，URL Token 也必须匹配。仅添加 URL 参数不能绕过服务端开关。

## 常见问题

| 现象 | 检查 |
|---|---|
| `ModuleNotFoundError: heritagelink` | 确认仓库根目录包含 `pyproject.toml`，Main file 为 `app.py`，构建日志执行了 `-e .` |
| 数据或图片找不到 | 确认 `data/`、`assets/` 已提交且文件名大小写与 CSV 完全一致 |
| DeepSeek 调用失败 | 暂时不配置 Key 验证本地回退，再检查 Secrets 名称和账户状态 |
| 授权记录未保存 | 检查 `ANALYTICS_ENABLED`、backend 和数据库地址；客户流程不应因此失败 |
| 评审 Trace 不显示 | 同时检查环境开关、`review_mode=1` 和可选 Token |
| 应用休眠或代码未更新 | 在 Streamlit Cloud 管理页 Reboot app；必要时清除缓存后重新部署 |

## 部署后检查

- [ ] 普通 URL 可在无痕窗口打开，且不显示 Agent Trace。
- [ ] 评审 URL 只在双重门控满足时显示 Trace。
- [ ] 无 Key 场景仍能推荐或给出明确无匹配结果。
- [ ] 完成推荐、选品、方案生成和 JSON 下载。
- [ ] 1440×1000 与 390×844 均无横向滚动。
- [ ] 20 件正式商品可推荐，30 件参考商品不进入正式推荐。
- [ ] 日志无 Key、数据库 URL、聊天原文或完整异常堆栈泄露到页面。

