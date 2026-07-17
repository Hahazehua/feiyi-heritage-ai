# Progressive Heritage Gift Recommendation

中文名称：渐进式非遗礼品推荐

## 提交信息

- Submitted Skill：2 / 4
- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2
- 报名并提交截止：2026年7月20日
- 社区交叉评测：2026年7月21日
- 晋级结果公布：2026年7月22日
- 当前实现状态：确定性渐进式适配、硬过滤、八维评分、稳定排序、无结果解释和独立定制概念已实现

## 解决的问题

用户经常只提供部分礼赠信息。本 Skill 在不猜测未知条件的前提下，立即基于当前已知需求返回探索、引导或约束推荐；随着用户补充条件，推荐模式、参与维度和结果可以重新计算。

它特别保证：用户明确提出的预算、数量、交期、定制、Logo 和国际运输要求不能为了“有结果”而被降低或忽略。

## 在主 Workflow 中的位置

```text
经过本地校验并由用户确认的 ParsedCustomerRequest
→ [本 Skill：渐进式推荐、硬过滤、评分和稳定排序]
→ 0–3 件符合全部明确硬约束的目录 MVP 演示方案或明确的无结果说明
→ Grounded Bilingual Heritage Content
```

## 输入契约

### Python 入口

```python
recommend_progressively(
    products: tuple[Product, ...] | list[Product],
    parsed: ParsedCustomerRequest,
    *,
    limit: int = 3,
) -> ProgressiveRecommendationResult
```

输入要求：

- `products` 来自经过 `data_loader.load_data` 和 `build_products` 校验的本地商品数据；
- `parsed` 只包含用户明确表达或用户确认的字段；
- `limit` 必须为 1–3；Wave 2 页面使用最多 3 件；
- 金额资格由整数分和确定性换算决定；
- 未知预算、数量或偏好不能被页面或模型补成用户事实。

## 输出契约

`ProgressiveRecommendationResult` 包含：

| 字段 | 含义 |
|---|---|
| `mode` | `exploring`、`guided` 或 `constrained` |
| `information_coverage` | 当前已知字段覆盖度，0–1 |
| `confidence_level` | 低、中、高；表示信息覆盖，不是成功概率 |
| `known_fields` / `missing_fields` | 当前已知与缺失字段 |
| `participating_dimensions` | 本轮实际参与个性化评分的维度 |
| `response.recommendations` | 0–3 件满足全部明确硬约束的目录 MVP 演示方案 |
| `response.filter_failures` | 被过滤商品及结构化原因 |
| `response.primary_conflicts` | 无结果时的主要冲突 |
| `response.adjustment_suggestions` | 无结果时可由用户决定是否调整的方向 |
| `alternatives` | 明确标注冲突的参考方案，不属于合格推荐 |
| `request_by_product` | 为每件商品构造的确定性 `GiftRequest` 快照 |

## 推荐模式

- **探索推荐**：信息很少，展示当前可用方向并明确低覆盖度。
- **引导推荐**：已有对象、场景或部分偏好，按已知维度评分。
- **约束推荐**：已有预算、数量、交期、Logo、定制或运输等明确必要条件，严格过滤后评分。

缺失字段只影响模式、覆盖度、参与维度和待补充提示，不直接淘汰商品，也不记为零分。

## 明确硬约束

`recommender._hard_filter` 按结构化原因处理：

1. 商品、商家或非遗项目状态无效；
2. 商品最低演示单价超过明确单件预算上限；
3. 数量低于起订量或超过非空演示数量上限；
4. 明确必需的定制或定制类型不支持；
5. 明确需要 Logo 但商品不支持；
6. 商品基础工期加必需定制附加工期超过可用天数；
7. 明确要求国际运输但商品未标记支持。

除状态外，只有用户明确提供的条件才启用对应过滤。

## 八维评分与稳定排序

| 维度 | 基础权重 |
|---|---:|
| 预算 | 25 |
| 赠礼对象 | 15 |
| 使用场景 | 15 |
| 风格 | 15 |
| 文化寓意 | 10 |
| 定制 | 10 |
| 数量 | 5 |
| 交付时间 | 5 |

只对当前已知且有效的参与维度归一化为 0–100 的 `match_score`。排序固定为：

```text
match_score 降序 → product_id 升序
```

同一商品目录、同一输入和同一规则版本必须得到相同结果。DeepSeek、Prompt 和 UI 均不能修改权重或排序。

## 如何运行

### Prototype 路径

1. 完成需求理解和确认。
2. 点击“确认并查看推荐”。
3. 查看推荐方式、覆盖度、0–3 件结果、匹配原因、维度状态和风险提示。
4. 点击“重新调整需求”修改字段并重新计算。

### 确定性 Python 示例

```python
from heritagelink.data_loader import build_products, load_data
from heritagelink.progressive_recommender import recommend_progressively
from heritagelink.request_parser import parse_request

bundle = load_data("data/demo")
products = build_products(bundle)
parsed = parse_request("给海外合作伙伴准备每件300元的礼物", mode="deterministic_demo")
result = recommend_progressively(products, parsed)
```

该路径不调用真实外部 API。

## 实际代码映射

| 职责 | 文件与入口 |
|---|---|
| 推荐模式、覆盖度、已知维度归一化 | `src/heritagelink/progressive_recommender.py` |
| 硬过滤、基础分、解释和稳定排序 | `src/heritagelink/recommender.py` |
| 请求、商品、维度、推荐和失败数据结构 | `src/heritagelink/models.py` |
| CSV 加载和业务数据校验 | `src/heritagelink/data_loader.py` |
| 无结果定制概念 | `src/heritagelink/customization_concept.py` |
| 推荐页面和不强推提示 | `app.py::_render_recommend` |
| 商品卡和八维状态 | `src/heritagelink/ui/product_card.py` |

## AI 职责边界

推荐资格、过滤、分数和排序完全由本地确定性代码负责。DeepSeek：

- 不读取商品目录；
- 不决定候选商品；
- 不修改权重、得分、过滤原因或排序；
- 不把冲突商品升级为合格推荐；
- 不生成虚构商品。

结果对象中的 `confidence_level` 只反映信息覆盖度，不是 AI 预测概率、购买概率或商家满意度。当前 Streamlit 推荐页会同时展示需求信息覆盖、当前置信度和推荐方式。

## 无结果与回退

无商品满足全部明确硬约束时：

- `response.recommendations` 为空；
- 页面明确说明不会强行推荐；
- 展示主要冲突和可调整方向；
- 冲突商品只进入独立替代区域，并列出冲突；
- 用户可生成 `is_existing_product=false` 的定制需求概念；
- 定制概念不得包含虚构 `product_id` 或 `product_name`，也不代表正式报价、产能或交付承诺。

DeepSeek 失败不会改变推荐器，因为本 Skill 不调用模型。

## 测试与验收

| 验收要求 | 对应测试 |
|---|---|
| 部分需求仍返回引导推荐 | `tests/test_progressive_recommender.py::test_partial_request_returns_guided_recommendations` |
| 未知字段不淘汰商品 | `test_unknown_fields_do_not_filter_products` |
| 不确定字段按未知处理 | `test_uncertain_fields_are_treated_as_unknown_by_public_recommender` |
| 明确预算仍是硬约束 | `test_explicit_budget_remains_a_hard_constraint` |
| 缺失维度不参与归一化 | `test_missing_dimensions_are_excluded_from_normalized_score` |
| 结果稳定 | `test_progressive_results_are_stable`、`test_same_input_produces_stable_results` |
| 预算、数量、交期、定制、Logo、运输过滤 | `tests/test_recommender.py` 中对应硬过滤测试 |
| 最多返回 3 件 | `test_results_never_exceed_three` |
| 同分使用商品 ID 稳定排序 | `test_tied_scores_sort_by_product_id` |
| 无结果返回冲突和建议 | `test_no_eligible_products_return_conflicts_and_suggestions` |
| 无结果概念不虚构商品 | `tests/test_customization_concept.py` |
| Streamlit 无结果不强推 | `test_app_smoke.py::test_precise_form_no_result_does_not_force_recommendation` |

建议执行：

```powershell
python -m pytest tests/test_progressive_recommender.py tests/test_recommender.py tests/test_customization_concept.py
```

2026年7月17日全量 pytest 实测为 `106 passed in 12.01s`。`tests/evaluation_cases.json` 的 14 个案例只作为确定性回归，不作为已有人类标注的 Top-3 业务指标证据。

## 当前限制与非目标

- 当前目录为 20 件 MVP 演示商品方案，不能代表完整市场供给。
- 价格、数量上限、工期、运输和定制能力需要真实商家复核。
- 当前没有 AI 语义重排、学习排序、用户画像、协同过滤或在线学习。
- 纯探索模式没有参与评分维度时使用中性展示分 50；它不是购买概率、成功率或业务指标。
- Top-1、Top-3 命中率和商家满意度当前未评测。
- 本 Skill 不实现正式库存、报价、支付、物流或订单处理。

## Specs 映射

- `docs/PRODUCT_SPEC.md`：§6 渐进式推荐模式、§8.2 推荐输出、§9 推荐方法、§13.2 无完全匹配、§16.2/16.4/16.5 验收要求。
- `docs/RECOMMENDATION_DESIGN.md`：职责、硬过滤、固定评分、排序和无结果边界。
- `docs/ARCHITECTURE.md`：§5 推荐引擎。
- `docs/DATA_SCHEMA.md`：§4 `recommendation_result`、§10 `progressive_recommendation_result`。
- `docs/WAVE2_SKILLS.md`：Skill 2 摘要；本文件为本轮详细提交契约。
