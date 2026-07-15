# HeritageLink AI MVP 数据模型

## 1. 通用约定

- MVP 使用 UTF-8 CSV 保存主数据，JSON 保存嵌套的需求、结果与导出。CSV 表头和代码字段使用英文 snake_case。
- 所有主键是稳定字符串：`mer_`、`heritage_`、`prod_`、`custopt_` 前缀；不得用展示名称作关联键。
- 金额以 CNY 分存为整数，字段后缀 `_fen`；日期使用 ISO 8601；布尔值使用 `true/false`。
- CSV 中的多值标签使用合法 JSON 数组字符串，例如 `["business","elder"]`，加载后转为集合。
- 所有演示记录含 `is_demo=true`；页面和导出显示 `MVP 演示数据 / MVP demo data`。
- `data_version` 建议使用日期加序号，如 `2026-07-14.1`，用于复现实验。

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

`score_breakdown` 键和满分必须与架构文档的 25/15/15/15/10/10/5/5 一致，总分等于分项和且在 0–100。未入选候选的过滤原因可在本次运行的 `filter_summary` 中聚合，不必暴露完整产品记录。

## 5. `customization_inquiry` JSON

需求单以机器可读 JSON 为准，页面可生成相同内容的人类可读预览：

```json
{
  "schema_version": "1.0",
  "inquiry_id": "inq_demo_20260714_0001",
  "created_at": "2026-07-14T10:00:00+08:00",
  "is_demo": true,
  "disclaimer_zh": "MVP 演示需求单，价格、库存、产能和交期均需商家确认。",
  "disclaimer_en": "MVP demo inquiry; price, availability, capacity and lead time require merchant confirmation.",
  "request_snapshot": {
    "request_id": "req_demo_0001",
    "currency": "CNY",
    "budget_total_min_fen": 800000,
    "budget_total_max_fen": 1200000,
    "quantity": 10,
    "recipient_tags": ["business_partner"],
    "occasion_tags": ["business_gift"],
    "style_tags": ["elegant"],
    "meaning_tags": ["prosperity"],
    "desired_delivery_date": "2026-09-30",
    "destination_text": "上海（MVP 演示）"
  },
  "customization_brief": {
    "required_types": ["inscription"],
    "preferred_types": ["packaging"],
    "content": "MVP 演示输入：企业周年纪念文字",
    "reference_asset_names": []
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
- 未决事实进入 `open_questions`，不得写成已确认事实。
- MVP 不保存姓名、电话、邮箱等个人信息；若未来增加，必须取得同意并单独定义保留与删除策略。

## 6. 受控词表与扩展

词表集中定义在代码枚举或单独版本化配置中，测试确保输入、产品标签和 UI 选项一致。增加商家只需新增 `merchants` 记录并通过外键关联；增加非遗品类只需新增 `heritage_items` 记录和受控 `category_code`，推荐接口无需改变。不得把“飞颐铁画”或 `metal_craft` 写死在评分函数中。

## 7. `parsed_customer_request`（第三阶段运行时结构）

自然语言解析结果不写入 CSV，也不直接进入推荐引擎。它包含客户类型、赠礼对象、单件预算、数量、场景、风格、寓意、定制、Logo、目的地、国际运输、交付天数、输出语言、主题、题字和包装，以及 `uncertain_fields`、`missing_fields`、`clarification_questions`、`parser_mode`、`raw_user_text`。数值和布尔值保留原生 JSON 类型；缺失值为 `null` 或空列表。用户确认后才转换为既有 `GiftRequest`。
