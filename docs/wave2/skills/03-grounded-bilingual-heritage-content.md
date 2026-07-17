# Grounded Bilingual Heritage Content

中文名称：有事实边界的双语文化内容组织

## 提交信息

- Submitted Skill：3 / 4
- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2
- 报名并提交截止：2026年7月20日
- 社区交叉评测：2026年7月21日
- 晋级结果公布：2026年7月22日
- 当前实现状态：本地中英文资料加载、模板组织、来源/审核状态展示和缺失字段回退已实现

## 解决的问题

礼赠场景需要清楚的中文和英文文化说明，但生成式补写容易混淆历史事实、商品事实和营销表达。本 Skill 只把本地已有的商品名称、工艺摘要、文化介绍、寓意、来源说明和审核状态组织为双语内容，并把缺失或未审核信息显式保留给商家确认。

它不负责联网检索、RAG、机器翻译、历史事实推断或把开放馆藏物件描述为在售商品。

## 在主 Workflow 中的位置

```text
用户选择一件满足明确硬约束的商品
→ [本 Skill：组织有来源和审核状态的中英文内容]
→ Merchant-Ready Customization Brief
```

## 输入契约

### Python 入口

```python
generate_bilingual_content(
    product: Product | ProductSummary,
    product_texts: pandas.DataFrame,
) -> BilingualContent
```

输入要求：

- `product` 提供稳定 `product_id` 和中英文商品名称；
- `product_texts` 至少含 `product_id` 和 `locale`；正常数据还包括 `craft_summary`、`cultural_story`、`meaning_summary`、`source_note`、`review_status`；
- 每个 active 商品的本地数据应各有一条 `zh-CN` 和 `en` 记录；
- 文化内容、图片来源元数据和商品商业字段分别维护，不能相互推断。

## 输出契约

`BilingualContent` 包含：

| 字段 | 含义 |
|---|---|
| `product_id` | 与选中商品一致的稳定 ID |
| `zh` | 中文 `LocalizedContent` |
| `en` | 英文 `LocalizedContent` |
| `pending_confirmations` | 缺失字段对应的语言和字段路径 |

每个 `LocalizedContent` 包含：

- `locale`；
- `text`：带标题、工艺、文化介绍、寓意、来源和审核状态的模板文本；
- `craft_summary`；
- `cultural_story`；
- `meaning_summary`；
- `source_note`；
- `review_status`；
- `pending_fields`。

## 当前数据事实

`data/demo/product_texts.csv` 当前有 40 条双语资料，对应 20 件商品的中文和英文记录。经只读盘点：

- `review_status=draft`：40 条；
- `review_status=approved`：0 条。

因此当前所有文化内容必须表述为 MVP 演示文案、待商家审核，不能称为已经商家审核通过。资料有值不等于事实已经获得商家商业确认。

`data/catalog/heritage_products.csv` 另行保存开放馆藏来源、对象编号、图片许可和历史元数据。商品价格、起订量、交期、运输与定制能力只来自 `data/demo/products.csv`，不会从馆藏资料推断。

## 如何运行

### Prototype 路径

1. 完成需求确认和推荐。
2. 点击一件符合条件的目录 MVP 演示方案的“查看文化故事”。
3. 查看“中文文化介绍”“English Cultural Story”“工艺与依据”“定制建议”。
4. 在“工艺与依据”中查看来源说明、数据版本、审核状态和图片许可。

### Python 入口示例

```python
from heritagelink.content import generate_bilingual_content
from heritagelink.data_loader import build_products, load_data

bundle = load_data("data/demo")
product = build_products(bundle)[0]
content = generate_bilingual_content(product, bundle.product_texts)
```

该路径只读取本地数据，不调用 DeepSeek、翻译服务或其他外部 API。

## 实际代码映射

| 职责 | 文件与入口 |
|---|---|
| 双语数据结构和模板组织 | `src/heritagelink/content.py` |
| 双语 CSV 加载、必填列、locale 和审核状态校验 | `src/heritagelink/data_loader.py` |
| 商品和文化资料 | `data/demo/products.csv`、`data/demo/product_texts.csv` |
| 开放馆藏来源目录 | `data/catalog/heritage_products.csv`、`src/heritagelink/catalog.py` |
| 文化页面 | `app.py::_render_culture` |
| 商品图片、来源和徽章 | `src/heritagelink/ui/components.py`、`ui/product_card.py` |

## 事实边界与模板行为

允许组织的内容：

- 本地商品中英文名称；
- 本地 `craft_summary`、`cultural_story`、`meaning_summary`；
- 本地 `source_note`、数据版本、图片许可和 `review_status`；
- 与推荐结果中已命中标签有关的场景说明；
- “待商家确认”或“演示文案，待商家审核”等状态表达。

禁止新增的内容：

- 数据中不存在的传承人、认证等级、历史事件、材料、工艺、功效或政府背书；
- 由开放馆藏图片推断出的商品价格、库存、交期、产能、运输或定制能力；
- 把 `draft` 改写为已审核；
- 把文化表达写成正式商业承诺。

## AI 职责边界

当前本 Skill 不调用 DeepSeek。中文和英文是本地两条独立资料，不在运行时机器翻译。模型不负责生成、补全、核验或重写文化事实。

如果未来增加模型辅助草稿或 RAG，也必须使用经过授权、可追溯和人工审核的数据，并保留当前本地模板作为审计和回退基线；这些未来能力不属于本轮提交。

## 失败与回退

| 失败情况 | 当前行为 |
|---|---|
| 找不到对应语言行 | 对应字段显示“待商家确认 / Pending merchant confirmation” |
| 某内容字段为空 | 只替换该字段为待确认，并加入 `pending_fields` |
| `review_status` 缺失 | 显示待确认并加入待确认字段 |
| `review_status` 不是 `approved` | 模板明确写“演示文案，待商家审核” |
| 数据缺少 `product_id` 或 `locale` 列 | 内容模块使用空结构并回退待确认；正常数据加载层应更早拒绝无效数据 |
| 单一语言缺失 | 不自动翻译；数据质量测试应失败或页面明确待补充 |

## 测试与验收

| 验收要求 | 对应测试 |
|---|---|
| 使用存储事实，不引入未知断言 | `tests/test_content.py::test_bilingual_content_uses_stored_facts_without_unknown_claims` |
| 缺失内容标记待确认 | `test_missing_content_is_marked_pending_confirmation` |
| 英文来源说明完成本地化并保留来源 URL | `test_english_source_notes_are_localized_and_keep_provenance` |
| 演示数据包含双语记录和预期规模 | `tests/test_data_loader.py::test_loads_expected_demo_dataset` |
| 缺失 CSV、列、外键、图片和声明给出明确错误 | `tests/test_data_loader.py` 对应失败测试 |
| 文化页面展示中文、英文、工艺和定制标签页 | `tests/test_app_smoke.py::test_product_culture_and_inquiry_complete_five_stage_flow` |
| 20 件图片和来源可追溯 | `tests/test_catalog.py`、`tests/test_catalog_app.py` |

建议执行：

```powershell
python -m pytest tests/test_content.py tests/test_data_loader.py tests/test_catalog.py tests/test_catalog_app.py
```

2026年7月17日全量 pytest 实测为 `106 passed in 12.01s`。当前没有商家内容审核完成率或内容满意度指标，不得编造数值。

## 当前限制与非目标

- 40 条资料全部为 `draft`，仍需商家逐条审核。
- 当前英文内容是本地演示字段，不代表已由母语编辑或商家独立审校。
- 当前不使用 RAG、知识库、实时网页检索或机器翻译。
- 开放馆藏资料用于来源和设计参考，馆藏物件不是在售商品。
- 本 Skill 不对价格、数量、工期、物流、税务或定制可行性作承诺。

## Specs 映射

- `docs/PRODUCT_SPEC.md`：§4 双语文化内容相关 Skill、§8.2 推荐内容、§10 AI 边界、§11 数据与事实来源、§13.3 资料缺失、§16.3 内容验收。
- `docs/ARCHITECTURE.md`：§6 数据与内容边界、§8 信任边界、错误与降级。
- `docs/DATA_SCHEMA.md`：§2.4 `product_texts.csv`、§11 开放馆藏参考目录。
- `docs/WAVE2_SKILLS.md`：双语文化内容摘要；本文件为本轮详细提交契约。
