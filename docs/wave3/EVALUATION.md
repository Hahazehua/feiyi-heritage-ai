# W3 评测与复现

## 环境与启动

- Python 3.11+
- DeepSeek API Key 不是确定性评审路径的前置条件

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m streamlit run app.py
```

## 自动化验收

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

按能力复现：

```powershell
python -m pytest tests/test_request_parser.py tests/test_dialogue_manager.py tests/test_inference_policy.py
python -m pytest tests/test_progressive_recommender.py tests/test_recommender.py
python -m pytest tests/test_content.py tests/test_inquiry.py
python -m pytest tests/test_analytics.py tests/test_analytics_service.py tests/test_choice_repositories.py
python -m pytest tests/test_choice_analysis.py
python -m pytest tests/test_app_smoke.py tests/test_catalog_app.py
python -m pytest tests/test_agent_orchestration.py tests/test_agent_manifest.py
```

启动后访问 `http://127.0.0.1:8501/_stcore/health`，预期 `200` 和 `ok`。健康检查不能替代 `DEMO.md` 的人工交互验收。

## 当前验证记录

- 最终执行日期：2026-08-01
- Ruff format：通过
- Ruff lint：通过
- 最终 pytest：164 passed in 128.27s
- Streamlit Cloud 依赖复现：`requirements.txt` 安装成功；Streamlit 1.59.2 / Starlette 0.52.1 导入通过
- 最终运行时冒烟：Streamlit 1.59.2 真实浏览器桌面首屏正常；390×844 视口 `scrollWidth=390`，无横向溢出
- 无 Key Streamlit 健康检查：通过，`200:ok`
- SQLite 幂等与未同意零写入：通过自动化测试
- Postgres SQL 路径：使用 fake connection 测试，无真实数据库写入
- 七个正式 Skill 包：使用 `skill-creator` 初始化/验证；最终结果以本轮完成验证为准
- 合成数据生成、CLI table/JSON、空库和不存在数据库：通过
- 真实浏览器桌面/窄屏走查：通过；实际结果与截图见 `BROWSER_ACCEPTANCE.md`
- 最终 commit、在线 Demo、第三方走查：提交前补充

## 测试安全边界

`tests/conftest.py` 阻断真实 DeepSeek 调用。自动化测试只使用占位 Key、Fake 或 Mock；数据库测试使用临时 SQLite 或 fake Postgres connection，不连接生产数据库，也不产生 API 费用。

Streamlit AppTest 的图片元素兼容 `imgs` 与旧版 `image` 命名，但仍严格验证推荐图像数量与结果一致、目录渲染 20 张图片；这不是放宽图片断言。
