# 匿名推荐选择分析模型

## 1. 隐私原则

- 默认不开启跨会话偏好保存；
- 用户勾选“允许匿名保存本次礼品偏好和选择，用于优化未来推荐”后才写入；
- 拒绝授权不影响聊天、推荐、选择或方案下载；
- 不记录姓名、电话、邮箱、地址、公司全称、证件或完整聊天原文；
- `ANALYTICS_STORE_RAW_CHAT` 默认 `false`，当前数据模型没有原文列。

## 2. 表结构

### `sessions`

`anonymous_session_id`、开始/完成时间、对话轮数、入口来源、应用版本、授权版本、授权时间和 `data_source`。匿名会话 ID 为随机 UUID，不从用户身份生成；`data_source` 区分真实授权事件和 `synthetic_demo`。

### `final_requirements`

保存对象、场景、预算类型和金额、数量、风格、寓意、定制类型、Logo、目的地、交付天数、内容语言，以及 `user_provided_fields` 与 `inferred_fields`。不保存原始消息。

### `recommendation_events`

保存稳定事件 UUID、会话 ID、`recommendation_signature`、推荐产品 ID、排名、匹配分和时间。`anonymous_session_id + recommendation_signature` 唯一，Streamlit rerun 不重复插入。

### `selection_events`

保存稳定事件 UUID、对应推荐事件、选中产品、排名、选择时间、最终动作、是否生成方案，以及可选的选择原因、拒绝原因和 1–5 满意度。相同推荐、产品和最终动作的 rerun 不重复插入；改选产品或进入“生成方案”最终动作时产生独立事件。

## 3. Repository

统一接口位于 `repositories/choice_repository.py`：

```python
save_session(session)
save_final_requirement(requirement)
save_recommendation(event)
save_selection(event)
```

每个写入返回 `SaveResult(saved, duplicate)`。可执行记录入口是 `analytics_service.capture_consented_choice`，返回 `saved`、`skipped_no_consent`、`skipped_no_selection`、`duplicate_ignored`、`storage_unavailable` 或 `validation_failed`。

- `SQLiteChoiceRepository`：仅用于本地开发和测试；数据库扩展名已加入 `.gitignore`。
- `PostgresChoiceRepository`：使用参数化 SQL 和 `ON CONFLICT`，适合 PostgreSQL/Supabase；连接 URL 只从环境变量或 Secrets 读取。
- `MemoryChoiceRepository`：用于不连接外部数据库的确定性测试。
- 未配置或数据库失败：Repository 返回关闭状态或由分析编排层捕获异常，不中断客户流程。

## 4. 配置

```dotenv
ANALYTICS_ENABLED=false
ANALYTICS_DATABASE_URL=
ANALYTICS_BACKEND=auto
ANALYTICS_STORE_RAW_CHAT=false
APP_VERSION=0.1.0
```

Streamlit Cloud 应在 Secrets 中配置上述值；不得把实际密码提交到仓库。SQLite 不适合作为 Streamlit Cloud 的跨实例持久存储。

## 5. 聚合分析

`choice_analysis.ChoiceAnalysisService` 已支持漏斗、产品、排名、对象、场景、预算区间、定制、目的地区域、未选择比例和对话轮数统计。默认最小样本量为 5；低于阈值的百分比返回 `null` 并附带样本不足提示。分析只输出聚合结果，不在公开客户页面展示。

合成数据固定随机种子并写入独立 `.local/` 数据库，所有会话标记 `data_source=synthetic_demo`；包含该来源的报告必须显示“当前结果基于合成演示数据，不代表真实客户偏好”。
