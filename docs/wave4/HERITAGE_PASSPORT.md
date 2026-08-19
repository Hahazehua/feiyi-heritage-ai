# HAHA Heritage Passport｜作品文化护照

## 1. 目的

Heritage Passport 把作品身份、文化资料、商业条件、来源与审核状态组织成同一个可追溯视图。它服务两个不同场景：

- Artisan 侧：让手艺人在提交前逐项检查、修改和确认资料；
- Buyer 侧：在商品卡的“文化护照”中用客户可读语言说明作品背景、来源和待确认条件。

文化护照不是非遗证书、传承人认证、鉴定证书、商品质检报告或平台担保。它记录“当前系统知道什么、来源是什么、确认到哪一步”，而不是替代真实认证。

## 2. 核心模型

`HeritagePassport` 包含：

| 字段组 | 主要内容 |
|---|---|
| 稳定身份 | `passport_id`、`product_id`、中英文作品名 |
| 创作者与工艺 | 手艺人或商家名称、工艺名称、地域 |
| 文化资料 | 中英文文化背景、文化寓意、可追溯来源 |
| 商业资料 | 价格、起订量、交期、材料、尺寸、定制、运输、产能等逐项事实 |
| 审核摘要 | 文化核验状态、商业核验状态、审核时间 |
| 发布状态 | `draft/pending_review/reference_only/recommendable/archived` |
| 双语表达 | 中英文概览、工艺背景、文化含义、礼赠语境和定制说明 |

商业资料不被压缩为一个真假开关。每个字段都由 `ProvenancedFact` 保存独立来源和核验状态，避免“某一项已确认”被误解为“整件商品均已审核”。

## 3. 来源与核验是两个维度

`FactSource` 回答“这条内容从哪里来”，`VerificationStatus` 回答“它目前能否作为确认事实使用”。两者不能混用。

例如：

| 值 | 来源 | 核验状态 | 正确解释 |
|---|---|---|---|
| 手艺人首次填写“支持 Logo” | `artisan_provided` | `pending_review` | 已收到陈述，仍待明确确认 |
| AI 从描述中提取“支持题字” | `ai_inferred` | `pending_review` | 只是候选，不可作商业承诺 |
| 手艺人在审核页确认材料 | `artisan_confirmed` | `confirmed` | 本轮由手艺人明确确认 |
| 有 HTTPS 文化来源 | `public_source` | 视审核结果而定 | 有链接不等于链接支持所有断言 |
| 没有国际运输资料 | `unknown` | `unknown` | 未知，不等于不支持 |

允许的核验状态为：

- `confirmed`：有允许的人工确认或经过审核的公开来源；
- `pending_review`：已有候选值，但尚未确认；
- `unknown`：没有足够资料；
- `not_applicable`：该条件明确不适用于当前对象。

`unknown` 与 `not_applicable` 都不能改写成否定事实。只有可靠来源明确表示“不支持”时，才可以展示为否定能力。

## 4. 文化与商业核验分离

文化事实和商业事实使用独立聚合状态：

- `cultural_verification_status`：工艺背景、地域文化、寓意与来源的审核程度；
- `commercial_verification_status`：价格、最低起订量、交期、定制、材料、尺寸、运输和产能的审核程度。

文化资料有公开来源，不代表当代商品的价格和履约能力已确认。商业字段已由手艺人确认，也不代表非遗资质、传承关系或文化叙述已经过独立专家审核。

## 5. 发布状态与推荐资格

Heritage Passport 记录发布状态，但它不单独授予推荐资格：

```text
Artisan draft publication status
  + independent human/business review
  + explicit canonical catalog publication
  + recommendation qualification gate
  = may enter Skill 3
```

`draft`、`pending_review`、`reference_only` 和 `archived` 均不得进入 Skill 3。`recommendable` 只表示审核流程允许进入下一步；在当前原型中，它仍不会自动插入 canonical catalog。现有 CSV 通过兼容适配映射发布语义：21 条 `recommendation_demo/active` 视为 legacy `recommendable`，30 条 `catalog_reference/inactive` 视为 `reference_only`。因此 Buyer 正式推荐只读取前者，后者与所有 Artisan 草稿都被排除。

## 6. Buyer 侧展示规则

Buyer 商品卡中的“文化护照”采用客户友好表达，不直接暴露枚举或内部字段名：

- 优先展示作品名、工艺、地域和有来源的文化背景；
- 来源显示可理解的名称与 HTTPS 链接；
- 商业事实只有在相应状态允许时才显示为已确认；
- `pending_review` 和 `unknown` 使用“待确认”“暂无可靠资料”等明确文字；
- 不能只依靠颜色、图标或空白表达未知；
- 不显示 API 来源、Prompt、内部 ID、技术 Trace 或数据库信息。

对于 `catalog_reference`，文化护照可以展示馆藏、工艺和文化来源，但不得展示为具有价格、起订量、定制、交期、运输或产能能力的可购买商品。参考目录不能进入比较、选品或询盘路径。

## 7. Artisan 侧确认规则

Artisan 侧在生成护照前提供逐项人工审核：

1. 显示当前值、来源与核验状态；
2. 允许修改 AI 候选或手艺人早先录入的内容；
3. 由手艺人勾选本次明确确认的字段；
4. 仅升级这些字段为 `artisan_confirmed/confirmed`；
5. 双语内容单独确认，不因其他字段确认而自动通过；
6. 有未解决冲突时阻止提交。

提交后护照处于 `pending_review`。这不是公开上架，也不会改变 Buyer 目录。

## 8. 双语草稿边界

`BilingualProductDraft` 覆盖中英文：作品概览、工艺背景、文化寓意、礼赠场景和定制说明。默认来源为 `ai_inferred`，状态为 `pending_review`。

生成规则必须满足：

- 只重组当前已知字段；
- 不补写传承人身份、非遗级别、历史年代或政府背书；
- 不把待确认价格、材料、交期、运输、产能和定制能力写成确定事实；
- 失败时回退到明确标注待确认的确定性模板；
- 中英文内容需要独立人工确认。

## 9. 冲突、历史与可审计性

受保护字段发生冲突时，护照不能只保留最后一次输入。`FactConflict` 记录当前值、新值和明确选择的解决值；没有 `resolved_value` 时保持未解决。未来生产环境还应保存审核人、审核角色、原因、版本号、撤销记录和不可变审计事件。

当前草稿 Repository 保存的是原型所需的最新草稿对象和关键时间戳，不等于生产级审计账本。

## 10. 隐私、权利与生产要求

当前模型不要求身份证号、银行卡、详细住址或其他完成草稿所不必要的敏感信息。图片和来源链接的提交不代表上传者拥有相应版权、商标权或商业授权。

生产发布前至少需要：

- 身份、商家主体和授权关系认证；
- 文化事实审核与来源适用性判断；
- 图片、商标、题字和包装素材的权利审核；
- 商业条件的责任主体、有效期和定期复核；
- 分角色权限、数据保留、删除、加密和审计策略；
- 上架、下架、申诉和紧急撤回机制。

因此当前 Heritage Passport 是来源透明和人工审核的产品机制，不是“真实性已由平台全面认证”的声明。
