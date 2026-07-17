# Merchant-Ready Customization Brief

中文名称：商家可执行的定制需求单生成

## 提交信息

- Submitted Skill：4 / 4
- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2
- 报名并提交截止：2026年7月20日
- 社区交叉评测：2026年7月21日
- 晋级结果公布：2026年7月22日
- 当前实现状态：单件选中商品的需求快照、定制字段、交付字段、待确认问题、双语内容、预览、复制和 JSON 下载已实现

## 解决的问题

客户的礼赠需求通常散落在自然语言、偏好和商品选择中，商家仍需反复确认数量、预算、主题、题字、Logo、包装、目的地和交期。本 Skill 将确认后的客户需求、选中商品快照、双语文化内容和开放问题整理为结构化需求单，使商家可以直接核对缺失信息并进入后续人工报价沟通。

“Merchant-Ready / 商家可执行”在本轮指字段完整、机器可读、待确认事项清楚，适合商家继续处理；它不代表正式订单、合同、报价、产能、物流或交付承诺。

## 在主 Workflow 中的位置

```text
确认需求 + 一件符合条件的目录 MVP 演示方案 + 有事实边界的双语内容
→ [本 Skill：商家定制需求单]
→ 页面预览、可复制摘要和 UTF-8 JSON 下载
```

## 输入契约

### Python 入口

```python
build_customization_inquiry(
    request: GiftRequest,
    recommendation: Recommendation,
    content: BilingualContent,
    details: InquiryDetails,
    *,
    inquiry_id: str | None = None,
    created_at: datetime | None = None,
    customer_context: InquiryRequestContext | None = None,
) -> dict[str, Any]
```

输入要求：

- `request` 是推荐器为选中目录方案构造的确定性 `GiftRequest`；
- `recommendation` 必须来自满足全部明确硬约束的当前推荐结果；
- `content.product_id` 必须与选中商品一致；
- `details` 保存客户类型、输出语言、主题、题字、包装、目的地和其他说明；
- `customer_context` 保存客户实际已确认的预算、数量、标签、定制、运输和交期，并用 `None` 保留未知值；当前 Streamlit 通过 `_inquiry_context` 传入该对象，避免把推荐内部代理值写成客户事实；
- MVP 需求单恰好包含一个选中商品；
- 未提供字段不允许被猜测，必须进入待确认值或 `open_questions`。

## 输出契约

生成的 JSON-ready 字典包含：

| 字段 | 内容 |
|---|---|
| `schema_version` | 当前为 `1.0` |
| `inquiry_id` / `created_at` | 系统生成 ID 和 ISO 8601 时间，不拼接用户输入到文件名 |
| `is_demo` | 固定为 `true` |
| `disclaimer_zh` / `disclaimer_en` | 价格、产能、交期、运输和定制可行性均需商家确认的双语声明 |
| `customer_type` / `output_language` / `additional_notes` | 客户和内容需求 |
| `request_snapshot` | 数量、单件和总预算、对象、场景、风格、文化寓意及 `pending_fields` 快照 |
| `customization_brief` | 是否定制、必需/偏好类型、主题、题字、Logo 和包装 |
| `delivery` | 目的地、国际运输要求、可用天数和交付要求 |
| `selected_products` | 恰好一个商品的 ID、商家、名称、数量、价格、选择时分数、数据版本和演示声明 |
| `merchant_action_items` | 商家需要核对和确认的行动项 |
| `open_questions` | 未提供或仍需商家确认的问题 |
| `culture_copy` | 中文、英文及文化内容待确认字段 |

`validate_inquiry` 在序列化前检查顶层契约、选中商品数量和双语内容。`inquiry_to_json` 只序列化已经通过校验的完整对象。

## 如何运行

### Prototype 路径

1. 完成需求确认并获得合格推荐。
2. 查看商品文化内容。
3. 点击“选择此方案并生成需求单”或“继续生成商家需求单”。
4. 核对产品、数量、预算、定制和交付信息。
5. 展开“待商家确认信息”。
6. 复制文本摘要或点击“下载需求单 JSON”。

### Python 入口关系

```text
ParsedCustomerRequest
→ request_parser.to_inquiry_details
→ ProgressiveRecommendationResult 中对应 GiftRequest 和 Recommendation
→ content.generate_bilingual_content
→ inquiry.build_customization_inquiry
→ inquiry.validate_inquiry
→ inquiry.inquiry_to_json
```

该链路不调用真实外部 API。

## 实际代码映射

| 职责 | 文件与入口 |
|---|---|
| 需求单细节结构 | `src/heritagelink/inquiry.py::InquiryDetails` |
| 客户已确认事实与未知值 | `inquiry.py::InquiryRequestContext`、`app.py::_inquiry_context` |
| 生成完整需求单 | `inquiry.py::build_customization_inquiry` |
| 开放问题生成 | `inquiry.py::_open_questions` |
| 契约校验 | `inquiry.py::validate_inquiry` |
| UTF-8 JSON 序列化 | `inquiry.py::inquiry_to_json` |
| 解析结果转换为需求单细节 | `src/heritagelink/request_parser.py::to_inquiry_details` |
| 双语内容输入 | `src/heritagelink/content.py::generate_bilingual_content` |
| 页面组装、预览和下载 | `app.py::_build_inquiry_for_selection`、`_render_inquiry` |
| 可复制摘要 | `app.py::_inquiry_summary_text`、`src/heritagelink/ui/inquiry_summary.py` |

## 商家可执行边界

需求单可以帮助商家：

- 查看选择时的商品和数据版本；
- 核对预算、数量、主题、题字、Logo、包装、目的地和交付要求；
- 识别哪些信息是客户已提供、哪些仍待确认；
- 审核中英文文化文案；
- 继续进行人工可行性确认和报价沟通。

需求单不能：

- 自动创建订单或合同；
- 锁定价格、库存、产能或生产排期；
- 计算物流、税务、关税或支付；
- 代表商家接受需求；
- 把 40 条 `draft` 文化资料写成商家审核通过；
- 保存客户姓名、电话、邮箱等不必要个人信息。

## AI 职责边界

当前需求单由确定性 Python 模块构造。DeepSeek 不参与：

- 选择商品；
- 改写商品、价格或评分快照；
- 决定定制可行性；
- 补写缺失主题、题字、包装、目的地或交期；
- 删除待确认问题；
- 生成订单、合同或商家承诺。

AI 或模板表达只能组织已有字段；最终报价、材料、产能、工期、包装、运输和文化事实由商家确认。

## 失败与回退

| 失败情况 | 当前行为 |
|---|---|
| 双语内容与商品 ID 不一致 | 立即拒绝生成需求单 |
| 主题、题字、包装或目的地缺失 | 写入“待商家确认”，并生成对应开放问题 |
| 交期缺失 | 写入待确认，并要求补充期望日期 |
| 需要 Logo | `logo_asset` 保持待确认，要求提供可用文件和权利信息 |
| 选中商品不是恰好一件 | `validate_inquiry` 拒绝 |
| 中英文文化内容缺失 | `validate_inquiry` 拒绝部分输出 |
| JSON 序列化前对象不完整 | 不输出部分 JSON；保留页面流程供用户修正 |

无满足全部明确硬约束的商品时，不生成绑定冲突商品的正式需求单。用户只能生成带强制免责声明、`is_existing_product=false` 且无虚构商品身份的定制需求概念。

## 测试与验收

| 验收要求 | 对应测试 |
|---|---|
| 数量、预算、主题、题字、Logo、包装、目的地、交期和商品快照完整 | `tests/test_inquiry.py::test_customization_inquiry_contains_complete_business_fields` |
| 缺失信息进入待确认值和开放问题 | `test_missing_inquiry_information_is_marked_and_questioned` |
| 五阶段流程展示需求单和下载按钮 | `tests/test_app_smoke.py::test_product_culture_and_inquiry_complete_five_stage_flow` |
| 探索性需求保持未知预算、数量、Logo 和运输字段 | `tests/test_app_smoke.py::test_exploratory_flow_keeps_unknown_inquiry_facts_pending` |
| 重新开始清理需求单和推荐状态 | `test_restart_returns_to_clean_home` |
| 重新确认需求后清除旧需求单并按新值重建 | `test_reconfirming_request_invalidates_and_rebuilds_inquiry` |
| 无结果不允许选择冲突商品 | `test_precise_form_no_result_does_not_force_recommendation` |
| 数据声明完整 | `tests/test_data_loader.py::test_incomplete_demo_disclaimer_is_rejected` |

建议执行：

```powershell
python -m pytest tests/test_inquiry.py tests/test_app_smoke.py
```

2026年7月17日全量 pytest 实测为 `106 passed in 12.01s`。当前没有商家需求单满意度、实际报价转化率或履约成功率评测，不得声明数值。

## 当前限制与非目标

- MVP 需求单只支持一个选中商品。
- 需求单只在当前 session 内生成和下载，不写正式数据库。
- 当前没有商家后台、审批流、电子签名、版本协商、订单状态或支付。
- 所有演示商业字段和 40 条 `draft` 文化资料仍需商家复核。
- 当前没有公开在线 Demo 或真实商家接收系统集成。

## Specs 映射

- `docs/PRODUCT_SPEC.md`：§4 定制需求单相关 Skill、§8.3 输出、§13 失败与回退、§15 页面与状态、§16.4 需求单验收。
- `docs/DATA_SCHEMA.md`：§5 `customization_inquiry` JSON 及必需校验。
- `docs/ARCHITECTURE.md`：§3 端到端数据流、§7 商家需求单、§8 错误与降级。
- `docs/WAVE2_SKILLS.md`：定制需求单摘要；本文件为本轮详细提交契约。
