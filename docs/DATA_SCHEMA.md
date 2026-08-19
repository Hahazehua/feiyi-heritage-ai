# 飞颐礼遇 MVP 数据模型

## 1. 通用约定

- MVP 使用 UTF-8 CSV 保存主数据，JSON 保存嵌套的需求、结果与导出。CSV 表头和代码字段使用英文 snake_case。
- 所有主键是稳定字符串：`mer_`、`heritage_`、`prod_`、`custopt_` 前缀；不得用展示名称作关联键。
- 金额以 CNY 分存为整数，字段后缀 `_fen`；日期使用 ISO 8601；布尔值使用 `true/false`。
- CSV 中的多值标签使用合法 JSON 数组字符串，例如 `["business","elder"]`，加载后转为集合。
- 所有演示记录含 `is_demo=true`；页面和导出显示 `MVP 演示数据 / MVP demo data`。
- `data_version` 建议使用日期加序号，如 `2026-07-14.1`，用于复现实验。
- 客户主界面不直接展示 `is_demo`、解析模式或内部字段名；这些字段继续保留在主数据、导出和赛事合规材料中。
- 用户陈述与受控推断必须分开记录；匿名跨会话数据只有在用户授权后才可写入 Repository。

### 1.1 匿名分析数据

分析数据分为 `sessions`、`final_requirements`、`recommendation_events` 和 `selection_events`。稳定 UUID、推荐签名、唯一约束和 upsert 保证幂等。会话同时记录授权版本、授权时间和 `data_source`，以区分真实授权事件与合成演示数据。字段、隐私边界、聚合指标和 SQLite/PostgreSQL 映射见 [`ANALYTICS_SCHEMA.md`](ANALYTICS_SCHEMA.md)。完整聊天原文、姓名、电话、邮箱、地址和证件不属于分析 schema。

### 1.2 推断来源

运行时 `RecommendationContext` 同时保存 `stated_request`、`effective_request`、`user_provided_fields`、`inferred_fields` 和自然语言方向摘要。每项推断包含值、原因、置信度和来源；允许与禁止字段见 [`INFERENCE_POLICY.md`](INFERENCE_POLICY.md)。

## 2. 主数据表

### 2.1 `merchants.csv`

| 字段 | 类型 | 必填 | 约束/说明 |
|---|---|---:|---|
| merchant_id | string | 是 | 主键 |
| merchant_name_zh | string | 是 | 商家中文名 |
| merchant_name_en | string | 是 | 商家英文展示名；演示翻译需审核 |
| city | string | 是 | 城市，不保存详细个人地址 |
| province | string | 是 | 省级行政区 |
| contact_channel | string | 否 | MVP 使用占位符，不放真实个人敏感信息 |
| status | enum | 是 | `active/inactive` |
| data_version | string | 是 | 数据版本 |
| is_demo | bool | 是 | MVP 必须为 true |

### 2.2 `heritage_items.csv`

| 字段 | 类型 | 必填 | 约束/说明 |
|---|---|---:|---|
| heritage_id | string | 是 | 主键 |
| heritage_name_zh | string | 是 | 非遗项目中文名 |
| heritage_name_en | string | 是 | 经审核的英文名 |
| category_code | string | 是 | 受控品类代码，如 `metal_craft` |
| region | string | 是 | 项目地域 |
| official_level | enum | 否 | `national/provincial/municipal/county/other/unverified` |
| verification_note | string | 是 | 信息来源或“待核验”；不得虚构认定级别 |
| status | enum | 是 | `active/inactive` |
| data_version | string | 是 | 数据版本 |
| is_demo | bool | 是 | MVP 必须为 true |

### 2.3 `products.csv`

| 字段 | 类型 | 必填 | 约束/说明 |
|---|---|---:|---|
| product_id | string | 是 | 主键 |
| merchant_id | string | 是 | 外键到 merchants |
| heritage_id | string | 是 | 外键到 heritage_items |
| sku | string | 是 | 商家内唯一 |
| product_name_zh | string | 是 | 中文名 |
| product_name_en | string | 是 | 英文名 |
| price_min_fen | int | 是 | `>=0` 且不大于 max |
| price_max_fen | int | 是 | `>= price_min_fen` |
| min_order_qty | int | 是 | `>=1` |
| recommended_max_qty | int | 否 | 建议批量上限；需 `>= min_order_qty` |
| demo_max_order_qty | int | 否 | 演示硬上限；非真实产能承诺 |
| lead_time_days | int | 是 | `>=0`，含基础制作时间假设 |
| dimensions_text | string | 是 | 展示值，不参与计算 |
| material_text | string | 是 | 已核实材料说明 |
| image_path | string | 是 | 本地商品图片；仅允许 `assets/products/` 或 `assets/catalog/products/` |
| image_alt_zh | string | 是 | 中文图片替代文本 |
| reference_source_url | string | 是 | 图片与设计参考的 HTTPS 来源 |
| image_license | string | 是 | 图片许可或使用依据 |
| category_code | string | 是 | 覆盖矩阵使用的稳定品类代码 |
| region_code | string | 是 | 地区或明确标注的文化语境；不得冒充商品产地 |
| price_tier | enum | 是 | `entry/mid/business/high/collector`；与金额字段一致 |
| source_product_url | string | 是 | 商品页或馆藏对象页 |
| source_culture_url | string | 是 | 官方文化/工艺背景页 |
| source_merchant_url | string | 否 | 无真实商家时为空，不能补造 |
| source_type | string | 是 | 如 `museum_open_collection` |
| source_accessed_at | date | 是 | 来源访问日期 |
| source_status | string | 是 | 来源可访问与审核状态 |
| verification_status | string | 是 | 整条记录的用途和验证状态 |
| merchant_fact_status | fact_status | 是 | 商家事实状态 |
| commercial_data_status | fact_status | 是 | 价格、交期、数量、运输等商业字段状态 |
| cultural_data_status | fact_status | 是 | 文化事实状态 |
| image_status | string | 是 | 本地副本、占位或待确认状态 |
| image_attribution | string | 是 | 图片署名/归属说明 |
| data_quality_level | enum | 是 | `A/B/C` |
| catalog_role | enum | 是 | `recommendation_demo/catalog_reference`；后者必须 inactive |
| recipient_tags | json[string] | 是 | 受控标签，可含 `universal` |
| occasion_tags | json[string] | 是 | 如 `business_gift/wedding/housewarming/memorial/collection` |
| style_tags | json[string] | 是 | 如 `traditional/modern/minimal/grand/elegant` |
| meaning_tags | json[string] | 是 | 如 `prosperity/harmony/blessing/heritage/remembrance` |
| supports_international_shipping | bool | 是 | 仅用于硬过滤的演示能力标记，不是运输承诺 |
| shipping_note | string | 是 | 明确说明演示设定及待确认项 |
| status | enum | 是 | `active/inactive` |
| data_version | string | 是 | 数据版本 |
| is_demo | bool | 是 | MVP 必须为 true |
| demo_disclaimer | string | 是 | 必须为完整指定免责声明 |

`fact_status` 允许 `verified_merchant_fact`、`verified_public_cultural_fact`、`public_listing_snapshot`、`demo_assumption`、`pending_verification`。`demo_assumption` 与 `pending_verification` 不能同时被标成商家已验证事实。`catalog_reference` 记录必须为 `inactive`，因此不会通过推荐硬过滤。

### 2.4 `product_texts.csv`

| 字段 | 类型 | 必填 | 约束/说明 |
|---|---|---:|---|
| product_id | string | 是 | 与 locale 组成联合主键 |
| locale | enum | 是 | MVP 为 `zh-CN/en` |
| craft_summary | string | 是 | 工艺摘要 |
| cultural_story | string | 是 | 文化介绍，不得包含未核实断言 |
| meaning_summary | string | 是 | 文化寓意 |
| source_note | string | 是 | 来源或审核说明 |
| review_status | enum | 是 | `draft/approved` |
| reviewed_at | datetime | 否 | approved 时必填 |
| is_demo | bool | 是 | MVP 必须为 true |

每个 active 产品必须各有一条 `zh-CN` 和 `en` 记录。

### 2.5 `customization_options.csv`

| 字段 | 类型 | 必填 | 约束/说明 |
|---|---|---:|---|
| customization_option_id | string | 是 | 主键 |
| product_id | string | 是 | 外键到 products |
| customization_type | enum | 是 | `inscription/pattern/size/packaging/color/logo/other` |
| description_zh | string | 是 | 可执行范围 |
| description_en | string | 是 | 英文说明 |
| price_impact | enum | 是 | `none/possible/required_quote` |
| extra_lead_days | int | 是 | `>=0`；推荐交期使用所选必需项的最大额外天数 |
| enabled | bool | 是 | 是否可选 |
| is_demo | bool | 是 | MVP 必须为 true |
| demo_disclaimer | string | 是 | 必须为完整指定免责声明 |
| commercial_data_status | fact_status | 是 | 当前演示选项均为 `demo_assumption`，需真实商家确认 |

## 3. `gift_request` JSON

```json
{
  "request_id": "req_demo_0001",
  "is_demo": true,
  "currency": "CNY",
  "budget_mode": "total",
  "budget_total_min_fen": 800000,
  "budget_total_max_fen": 1200000,
  "unit_budget_min_fen": 80000,
  "unit_budget_max_fen": 120000,
  "quantity": 10,
  "recipient_tags": ["business_partner"],
  "occasion_tags": ["business_gift"],
  "style_tags": ["elegant"],
  "meaning_tags": ["prosperity"],
  "customization": {
    "required_types": ["inscription"],
    "preferred_types": ["packaging"],
    "brief": "MVP 演示输入：企业周年纪念文字"
  },
  "desired_delivery_date": "2026-09-30",
  "destination_text": "上海（MVP 演示）",
  "notes": "MVP 演示输入"
}
```

校验规则：预算上限不小于下限；数量大于 0；`budget_mode=total` 时总预算必填，`per_item` 时单件预算必填；规范化后两组预算字段均应存在。自由文本设置合理长度上限（建议 500 字符）并不得用于构造文件路径。

## 4. `recommendation_result` JSON

每件候选结果至少包含：

```json
{
  "product_id": "prod_demo_001",
  "merchant_id": "mer_demo_feiyi",
  "eligible": true,
  "total_score": 86.5,
  "score_breakdown": {
    "budget": 25.0,
    "recipient": 15.0,
    "occasion": 15.0,
    "style": 12.0,
    "cultural_meaning": 10.0,
    "customization": 5.0,
    "quantity": 2.5,
    "lead_time": 2.0
  },
  "matched_reasons": ["预算区间匹配", "适合商务赠礼"],
  "warnings": ["批量产能需商家确认"],
  "data_version": "2026-07-14.1",
  "is_demo": true
}
```

`score_breakdown` 键和满分必须与架构文档的 25/15/15/15/10/10/5/5 一致。基础规则分等于八个分项之和；页面使用的 `match_score` 只根据已提供维度归一化到 0–100。未入选候选的过滤原因可在本次运行的 `filter_summary` 中聚合，不必暴露完整产品记录。

## 5. `customization_inquiry` JSON

需求单以机器可读 JSON 为准，页面可生成相同内容的人类可读预览：

```json
{
  "schema_version": "1.0",
  "inquiry_id": "inq_demo_20260714_0001",
  "created_at": "2026-07-14T10:00:00+08:00",
  "is_demo": true,
  "disclaimer_zh": "MVP 演示需求单；价格、产能、交期、运输和定制可行性均需商家确认。",
  "disclaimer_en": "MVP demo inquiry; price, capacity, lead time, shipping, and customization feasibility require merchant confirmation.",
  "customer_type": "corporate",
  "output_language": "中英双语",
  "additional_notes": "待确认",
  "request_snapshot": {
    "request_id": "req_demo_0001",
    "currency": "CNY",
    "unit_budget_min_fen": 80000,
    "unit_budget_max_fen": 120000,
    "budget_total_min_fen": 800000,
    "budget_total_max_fen": 1200000,
    "quantity": 10,
    "recipient_tags": ["business_partner"],
    "occasion_tags": ["business_gift"],
    "style_tags": ["elegant"],
    "meaning_tags": ["prosperity"],
    "pending_fields": ["logo_required"]
  },
  "customization_brief": {
    "required": true,
    "required_types": ["inscription"],
    "preferred_types": ["packaging"],
    "theme": "企业周年纪念",
    "inscription": "待确认",
    "logo_required": null,
    "logo_asset": "待确认",
    "packaging": "礼盒"
  },
  "delivery": {
    "destination": "上海（MVP 演示）",
    "international_shipping_required": false,
    "available_lead_days": 30,
    "delivery_requirement": "30 天内"
  },
  "selected_products": [
    {
      "product_id": "prod_demo_001",
      "merchant_id": "mer_demo_feiyi",
      "product_name_zh": "演示产品",
      "quantity": 10,
      "quoted_price_min_fen": 80000,
      "quoted_price_max_fen": 120000,
      "score_at_selection": 86.5,
      "data_version": "2026-07-14.1"
    }
  ],
  "merchant_action_items": [
    "确认文字内容、字体、位置及知识产权可用性",
    "确认含定制的最终报价、产能和交付日期"
  ],
  "open_questions": ["目的地对应的包装和物流方案是什么？"],
  "culture_copy": {
    "zh-CN": "已审核或明确标注待审核的演示文化介绍",
    "en": "Reviewed demo culture copy or copy explicitly marked pending review"
  }
}
```

### 必需校验

- `schema_version`、ID、时间、演示标记、声明、需求快照、一个已选产品、行动项和双语文案均必填。MVP 要求 `selected_products` 恰好一项；保留数组结构供未来多产品询价扩展。
- `selected_products` 保存选择时快照，避免主数据变化后需求单失真；金额范围与数量合法。
- 用户未表达的预算、数量和布尔条件在 `request_snapshot`、`customization_brief` 或 `delivery` 中保持 `null`，并进入 `pending_fields` 或 `open_questions`；推荐适配层使用的内部占位值不得写回需求单。
- 未决事实进入 `open_questions`，不得写成已确认事实；`false` 只能表示用户明确表示“不需要”，不能代替未知状态。
- MVP 不保存姓名、电话、邮箱等个人信息；若未来增加，必须取得同意并单独定义保留与删除策略。

## 6. 受控词表与扩展

词表集中定义在代码枚举或单独版本化配置中，测试确保输入、产品标签和 UI 选项一致。增加商家只需新增 `merchants` 记录并通过外键关联；增加非遗品类只需新增 `heritage_items` 记录和受控 `category_code`，推荐接口无需改变。不得把“飞颐铁画”或 `metal_craft` 写死在评分函数中。

## 7. `parsed_customer_request`（第三阶段运行时结构）

自然语言解析结果不写入 CSV。渐进式适配层只把已知字段转换为逐产品 `GiftRequest`，未知预算和数量使用不会淘汰该产品的内部占位值，且不在页面上表述为用户事实。

| 字段 | 类型 | 受控值/说明 |
|---|---|---|
| customer_type | string/null | `corporate/institution/individual/overseas` |
| budget_type | string/null | `per_item/total` |
| total_budget | number/null | CNY 元，必须大于 0 |
| budget_per_item | number/null | CNY 元，必须大于 0；总预算模式由本地确定性换算 |
| quantity | int/null | 必须大于 0 |
| recipient | string/null | 与 `GiftRequest.recipient_tags` 词表一致 |
| scene | string/null | 与 `GiftRequest.occasion_tags` 词表一致 |
| style_preferences | string[] | 与产品 `style_tags` 词表一致 |
| symbolism_preferences | string[] | 与产品 `meaning_tags` 词表一致 |
| customization_required | bool/null | 不允许字符串形式的真假值 |
| customization_types | string[] | `inscription/pattern/size/packaging/color/logo/other` |
| logo_required | bool/null | true 时 customization_required 必须为 true |
| international_shipping_required | bool/null | 只代表客户必要条件 |
| destination | string/null | 目的国家或地区，不推断具体物流能力 |
| required_delivery_days | int/null | 大于 0；未说明时为 null |
| output_language | string/null | `zh/en/bilingual` |
| requested_theme | string/null | 用户明确表达的主题 |
| requested_text | string/null | 用户明确提供的题字 |
| packaging_requirement | string/null | 用户明确表达的包装要求 |
| additional_notes | string/null | 其他明确要求，不参与隐式评分 |
| raw_user_text | string | 原始文本，最大 3000 字符 |
| parser_mode | string | `deepseek/deterministic_demo` |
| missing_fields | string[] | 本地重新计算，不盲信模型 |
| uncertain_fields | string[] | 只能引用本结构字段 |
| clarification_questions | string[] | 面向用户的补充问题 |

### 7.1 预算一致性

- `budget_type=total` 时必须保留 `total_budget`；数量存在时由本地计算 `budget_per_item=total_budget/quantity`。
- `budget_type=per_item` 时必须提供 `budget_per_item`；若同时提供总预算，则必须与单价乘数量在人民币 0.01 元误差内一致。
- 换算到推荐引擎时使用十进制定点计算并转换为整数分，不用二进制浮点数决定预算资格。

### 7.2 确认快照

session state 保存逐轮原文、累计解析结果和当前业务版本。参与推荐的字段改变后生成新签名并重新构造 `GiftRequest`；签名不变时不得重复推荐。
## 8. `conversation_state`（当前 session 运行时结构）

| 字段 | 类型 | 说明 |
|---|---|---|
| conversation_id | string | 当前会话随机演示 ID |
| messages | ConversationMessage[] | `user/assistant` 可显示消息，不保存模型推理 |
| raw_user_texts | string[] | 各轮用户原文 |
| accumulated_request | parsed_customer_request/null | 经本地校验的累计需求 |
| missing_blocking_fields | string[] | 预算、数量、对象、场景中的缺失项 |
| missing_optional_fields | string[] | 不阻塞推荐的偏好项 |
| uncertain_fields | string[] | 需要澄清的显式歧义 |
| clarification_questions | string[] | 当前最多一条问题 |
| current_stage | enum | `collecting/needs_clarification/ready_to_recommend/showing_recommendations/customization_brief` |
| ready_to_recommend | bool | 只能由本地规则计算 |
| user_confirmed_fields | string[] | 已从用户轮次明确得到的字段 |
| last_recommendation_signature | string/null | 防止同条件重复推荐 |
| clarification_rounds | int | 0–3 |
| manual_form_required | bool | 达到上限后引导详细表单 |

DeepSeek 对话响应采用固定 JSON envelope，包含 assistant_message、newly_extracted_fields、
updated_fields、缺失/不确定字段、clarification_questions、next_question、ready_to_recommend、
recommended_action 和 confidence_by_field。所有未知字段、非法动作或非法类型均被拒绝并安全回退。

## 9. `custom_heritage_gift_concept`

仅在推荐结果为零时生成。必须包含 `is_existing_product=false`、状态、需求条件、目录冲突、调整
建议及商家确认问题；禁止包含虚构 product_id/product_name。声明固定为：

> 该内容为系统整理的定制需求概念，不代表现有产品、正式报价、产能或交付承诺。

## 10. `progressive_recommendation_result`

运行时结果包含 `recommendation_mode`（`exploring/guided/constrained`）、
`information_coverage`（0–1）、`confidence_level`（低/中/高）、`known_fields`、
`missing_fields`、`participating_dimensions`、完全匹配推荐、过滤失败和独立替代建议。
`match_score` 仅根据参与维度归一化；未知维度不得记零分或中性命中。没有任何参与维度时，纯探索模式的整体展示分固定为 50，并按商品 ID 稳定排序；该回退值不表示某一未知维度命中，也不是业务指标。

## 11. 开放馆藏参考目录

`data/catalog/heritage_products.csv` 保存图片与历史资料来源；价格、起订量、交期、运输和定制能力仍只存放在 `data/demo/products.csv`，不会从馆藏信息推断。当前每行包含：

- 目录 ID、来源对象 ID、中英文名称和工艺分类；
- 与推荐商品一一对应的 `demo_product_id`；
- 来源页面记录的年代、地区、材质与尺寸；
- 基于来源元数据撰写的中英文简要介绍；
- 本地 `image_path` 与远程 `image_source_url`；
- 馆藏原页、来源机构、馆藏编号、图片许可和核验状态；
- 固定的 `museum_reference_not_for_sale` 商业状态。

`src/heritagelink/catalog.py` 校验必填字段、重复目录 ID、重复商品关联、HTTPS 来源、本地图片路径和图片文件。`data_loader.py` 同时强制每件推荐商品关联可读取图片。正式商家产品图片应进入独立的 `assets/products/<merchant_id>/`，不得覆盖可追溯的开放馆藏文件。

## 12. Artisan Studio 草稿模型

Artisan Studio 不直接构造严格的 canonical `Product`。不完整资料先进入独立 `ArtisanProductDraft`：

| 字段 | 类型 | 说明 |
|---|---|---|
| draft_id | string | `draft_` 前缀的随机稳定 ID |
| session_id | string | 当前 Artisan 会话 ID；不是 Buyer 分析 session |
| created_at | datetime | 含时区的创建时间 |
| updated_at | datetime | 含时区的最后更新时间 |
| facts | ProvenancedFact[] | 逐字段来源与核验状态；字段名不可重复 |
| publication_status | PublicationStatus | 默认 `draft` |
| image_name | string/null | 可选上传文件名；不得用于任意路径拼接 |
| image_bytes | bytes/null | 可选会话或草稿图片；SQLite 中使用 Base64 包装 |
| bilingual_draft | BilingualProductDraft/null | AI 或确定性模板生成的待审核双语草稿 |
| conflicts | FactConflict[] | 受保护字段的新旧值冲突 |
| submitted_at | datetime/null | `pending_review` 时必填 |
| reviewed_at | datetime/null | 独立审核产生的时间；模拟审核不等于生产认证 |

第一阶段可以保存作品名、工艺、地域、自由描述和图片。第二阶段商业字段均可为空或未知，包括价格区间、币种、起订量、交期、定制、Logo、包装、尺寸、材料、国内/国际运输和产能。第三阶段保存文化背景、寓意、制作流程、礼赠场景和来源 URL。

空字符串、空集合和 `unknown` 不覆盖已有值。价格、材料、定制、最低起订量、运输和交期发生不一致时必须创建 `FactConflict`，保留 `current_value`、`incoming_value` 和可选 `resolved_value`；存在未解决冲突时不得提交。

## 13. `ProvenancedFact`

| 字段 | 类型 | 说明 |
|---|---|---|
| field_name | string | 稳定 snake_case 字段名 |
| value | JSON-compatible value | 未知可为 null，不得用 false 替代未知 |
| group | FactGroup | `identity/cultural/commercial/content` |
| source | FactSource | 事实或候选的来源 |
| verification_status | VerificationStatus | 当前核验状态 |
| source_note | string/null | 面向审核的简短来源说明 |
| confirmed_at | datetime/null | `artisan_confirmed` 的显式确认时间 |

`FactSource` 允许：

- `artisan_provided`：手艺人录入，但尚未显式确认；
- `artisan_confirmed`：手艺人在审核步骤中逐项确认；
- `merchant_confirmed`：未来由经过认证的商家确认；
- `public_source`：有可追溯公开来源，仍需判断来源是否支持对应断言；
- `ai_inferred`：模型提取或生成的候选；
- `unknown`：没有可依赖来源。

`VerificationStatus` 允许 `confirmed`、`pending_review`、`unknown`、`not_applicable`。约束如下：

- `ai_inferred` 不能与 `confirmed` 组合；
- `confirmed` 只允许来自 `artisan_confirmed`、`merchant_confirmed` 或经过审核的 `public_source`；
- 人工确认按字段升级，不能通过确认一个字段升级整份草稿；
- `unknown` 不能解释为否定能力，`not_applicable` 需要明确适用性依据。

## 14. `BilingualProductDraft`

双语草稿包含以下十个文本字段：

- `overview_zh` / `overview_en`；
- `craft_background_zh` / `craft_background_en`；
- `cultural_meaning_zh` / `cultural_meaning_en`；
- `gifting_contexts_zh` / `gifting_contexts_en`；
- `customization_zh` / `customization_en`。

另含独立的 `source` 与 `verification_status`。默认组合为 `ai_inferred/pending_review`；即使事实字段已由手艺人确认，双语表达也不会自动升级。模型调用或输出校验失败时使用基于当前已知值的确定性模板，并继续保留待确认状态。

## 15. `HeritagePassport`

| 字段 | 类型 | 说明 |
|---|---|---|
| passport_id | string | 稳定文化护照 ID |
| product_id | string | 草稿使用 pending ID；canonical 商品使用原 product ID |
| artisan_or_merchant_name | string/null | 未核验时不得展示为认证主体 |
| product_name_zh / product_name_en | string / string/null | 中英文作品名 |
| craft_name | string | 工艺名称 |
| region | string/null | 地域或文化语境，不自动等于产地 |
| cultural_background_zh/en | string/null | 有来源边界的文化背景 |
| symbolism | string[] | 文化寓意 |
| cultural_sources | SourceReference[] | 名称、HTTPS URL、来源类型与来源自身的核验状态 |
| commercial_facts | ProvenancedFact[] | 商业字段保持逐项状态 |
| cultural_verification_status | VerificationStatus | 文化事实汇总状态 |
| commercial_verification_status | VerificationStatus | 商业事实汇总状态 |
| publication_status | PublicationStatus | 发布生命周期状态 |
| reviewed_at | datetime/null | 独立审核时间 |
| bilingual_content | BilingualProductDraft/null | 可选双语内容 |

Buyer 视图必须把内部枚举转换为客户可读文案。`catalog_reference` 可以展示文化来源，但其价格、起订量、交期、定制、运输和产能不能显示为已具备的商业能力。

## 16. 发布生命周期与推荐资格

`PublicationStatus` 允许：

```text
draft → pending_review → reference_only / recommendable / archived
```

- `draft`：填写中；
- `pending_review`：已提交，等待审核；
- `reference_only`：仅作文化参考；
- `recommendable`：满足独立审核门槛，可进入显式目录发布步骤；
- `archived`：撤回或停用。

`recommendable` 不触发自动目录写入。当前 Skill 3 候选仍由 canonical `Product` 的统一资格门控制，并且只接受逻辑发布状态 `recommendable`。为避免修改现有 CSV 合同，适配层把 `catalog_role=recommendation_demo` 且产品、商家和工艺状态全部为 `active` 的记录视为 legacy `recommendable`；`catalog_reference/inactive` 视为 `reference_only`。因此 21 条正式演示记录、30 条参考和 51 条总目录边界不因 Artisan 草稿而改变。

当前模拟审核要求规定的身份、文化与商业字段逐项为非空 `confirmed`，至少一个 `_source_url` 字段为 `confirmed`，并且存在图片；任一条件不足时结果为 `reference_only`。该规则只用于原型状态演示，不替代生产级身份、来源与商家审核。

## 17. Artisan 草稿持久化隔离

`ArtisanDraftRepository` 协议提供 `save`、`get` 和 `list_for_session`。当前有：

- 内存实现：用于当前 Streamlit 原型和隔离测试；
- SQLite 实现：表 `artisan_drafts` 保存 `draft_id`、`session_id`、`publication_status`、`payload_json`、`created_at` 和 `updated_at`。

该表不属于 [`ANALYTICS_SCHEMA.md`](ANALYTICS_SCHEMA.md) 中的 Buyer 匿名事件。Artisan 草稿不得写入 `sessions`、`recommendation_events` 或 `selection_events`，Buyer 的匿名授权也不覆盖手艺人资料。生产环境需要另行定义身份、商家主体、角色权限、加密、保留、删除和审计策略。
