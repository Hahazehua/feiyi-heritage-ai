# HeritageLink AI｜非遗礼遇

HeritageLink AI 是面向非遗礼品推荐与定制沟通的可解释 MVP。当前用飞颐铁画的 8 件演示产品，验证从客户需求理解、规则推荐、双语文化介绍到商家定制需求单的完整交易前流程。

> 当前产品、价格、产能、材料、交期和运输信息仅用于MVP演示，不代表飞颐铁画真实商业承诺。

本项目属于 SynNovator 数字文化赛道（原赛道标识：`track-98`）。

## 用户流程

用户可以选择两种入口：

1. “智能描述”：输入一段自然语言，由 DeepSeek 或本地演示解析器提取需求；
2. “详细表单”：逐项填写需求，完全不经过大模型；
3. 智能描述的解析结果必须先由用户查看、补充和修改；
4. 用户确认后，系统执行原有预算、数量、交期、定制、Logo 和国际运输硬性过滤；
5. 合格产品按固定 100 分规则评分，最多展示 3 件，并解释得分和风险；
6. 用户可查看模板化中英文文化介绍，并生成 JSON 定制需求单；
7. 没有合格产品时，系统说明冲突和调整建议，不强行推荐。

DeepSeek 只做自然语言字段提取，不决定推荐结果，也不能绕过硬性条件。

## 安装

需要 Python 3.11 或更高版本。建议在独立虚拟环境中运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## 配置 DeepSeek

在 [DeepSeek 开放平台](https://platform.deepseek.com/)创建 API Key。复制示例配置：

```powershell
Copy-Item .env.example .env
notepad .env
```

把 `.env` 中的占位符替换为自己的 Key：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

当前默认模型为 `deepseek-v4-flash`。程序使用 DeepSeek 官方 OpenAI 兼容接口和非思考模式，只请求 JSON 字段提取结果。

安全注意事项：

- 不要把真实 Key 写入代码、README、测试、日志或截图；
- 不要提交 `.env`；仓库只保留无密钥的 `.env.example`；
- 如果怀疑 Key 泄露，应立即在开放平台撤销并重新创建；
- 自动化测试全部使用 Mock，不会调用真实 API 或产生费用。

## 启动

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

浏览器通常会打开 `http://localhost:8501`。

### DeepSeek 模式与演示回退模式

- 自动模式：存在有效 `DEEPSEEK_API_KEY` 时优先调用 DeepSeek；用户仍须确认结果；
- 演示模式：使用有限的正则和关键词规则，页面会明确显示“当前使用演示解析模式”；
- 没有 API Key、认证失败、余额不足、超时、网络错误或空响应时，系统安全回退到演示模式；
- API 故障不会影响详细表单和原有推荐功能；
- 用户也可主动选择确定性演示解析，完全不发出 API 请求。

## 测试与代码检查

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

Streamlit 冒烟启动：

```powershell
python -m streamlit run app.py --server.headless true
```

## 演示数据

`data/demo/` 包含 1 个飞颐铁画演示商家、1 个 `unverified` 铁画演示项目、8 件演示产品、双语模板资料和演示定制能力。所有未确认的价格、产能、材料、交期、运输和定制能力均为 MVP 演示数据，不代表真实商业承诺；仓库不声明真实传承人身份、官方认证级别或政府背书。

## 当前限制

- 只有一个试点商家和少量演示产品；
- DeepSeek 只提取用户明确表达的字段，解析结果必须人工确认；
- 推荐仍是固定硬性过滤、权重和稳定排序，不是学习模型；
- 双语文化内容来自本地资料和模板，不由 DeepSeek 编写，仍需商家审核；
- 不提供登录、支付、库存、合同、物流、结算或商家后台；
- 不保存客户个人身份和联系方式；
- 当前不使用 RAG、向量数据库、数据库或 ORM。

## 后续大模型与 RAG 计划

在真实商家和用户验证规则基线后，可以让大模型辅助整理商家资料、生成待审核双语草稿和改写沟通文本。之后再评估 RAG，用于检索经过授权、审核且可追溯的非遗资料。大模型不会替代价格、产能、交期、运输和文化事实的人工确认，也不会替代现有硬性规则。
