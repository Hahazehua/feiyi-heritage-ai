# HeritageLink AI 目录扩展审计报告

审计日期：2026-07-30  
数据版本：`2026-07-30.1`

## 结论

目录已从 20 件扩展到 50 件，同时保留全部 20 件不重复、图片与馆藏来源可读取的原有记录。新增 30 件均是 The Metropolitan Museum of Art Open Access 中真实存在且标记为 Public Domain 的馆藏对象，不是商品销售页。它们被明确设为 `inactive`、`catalog_reference`、`catalog_reference_not_for_sale` 和 Level C，只用于目录探索，不参与正式推荐、询价或定制需求单。

原有 20 件记录仍是“馆藏启发的 MVP 礼赠方案”，不是已核验商家 SKU。其文化资料和图片来源可验证；价格、起订量、交期、运输及定制能力均为 `demo_assumption`。本轮没有把这些字段升级成商家事实，也没有改变推荐八维权重、硬过滤或稳定排序规则。

## 修改前审计

| 指标 | 结果 |
|---|---:|
| 原始记录 / 去重有效记录 | 20 / 20 |
| 商家记录 | 1 个平台 Demo 选品主体 |
| 非遗/工艺分类 | 4 |
| 图片 | 20/20，路径唯一且存在 |
| 双语文本 | 40 条，全部 draft |
| 定制类型 | 4（inscription、logo、pattern、packaging） |
| 价格层级 | 4；entry 1、mid 9、business 9、high 1、collector 0 |
| 来源状态 | 馆藏与图片可验证；全部商业字段未由商家验证 |

未发现重复 `product_id`、重复图片路径、失效外键或缺失本地图片。主要质量问题不是记录损坏，而是“馆藏事实”和“商业 Demo 假设”过去只通过免责声明区分，机器可读边界不足。

## 修改结果

| 动作 | 数量 |
|---|---:|
| 保留 | 20 |
| 修复/补充来源与质量字段 | 20 |
| 替换/删除 | 0 |
| 新增馆藏参考 | 30 |
| 最终总数 | 50 |

新增六类各 5 件：传统折扇与纸艺、印章艺术、竹木文房器物、传统茶生活器物、雕版印刷与版画、中国书法。连同原有漆器、陶瓷、织绣和玉石，共 10 类；每类 5 件，占比均为 10%，低于 40% 上限。

地区/文化语境字段形成 11 个明确标签，包括全国性中国文化语境、浙江印章艺术语境、福建/浙江/广西/云南/四川茶文化语境等。带“文化语境”或“非器物产地声明”的值只用于覆盖分析，不能解释为馆藏对象的制作地或当前商品产地。

## 覆盖矩阵摘要

| 维度 | 覆盖结果 |
|---|---|
| 价格层级 | entry 7、mid 15、business 15、high 7、collector 6 |
| 场景 | 16 种 |
| 对象 | 10 种 |
| 风格 | 13 种 |
| 文化寓意索引 | 14 种 |
| 定制类型 | 5 种；新增 size 仅为 Demo 评估入口 |
| 图片 | 50/50，100%；50 条唯一相对路径 |
| 双语文本 | 100/100，50 件各一条 zh-CN 和 en |

新增 30 件的价格带、数量和交期只是为本地 schema 与覆盖测试保留的宽粒度 `demo_assumption`，不显示为公开售价，也不参与推荐。寓意、对象、场景和风格属于策展索引，不是馆方对对象含义的认定。

## 数据质量和来源

| 等级 | 数量 | 用途 |
|---|---:|---|
| A | 0 | 尚无商家与关键商业字段全部核验的真实 SKU |
| B | 0 | 尚无部分商业字段已核验的真实 SKU |
| C | 50 | 20 件推荐流程 Demo + 30 件不可推荐馆藏参考 |

`source_registry.csv` 覆盖全部 50 件记录；新增对象各保存馆藏对象来源和文化背景来源。`research_log.csv` 保存 30 条新增研究记录，并明确列出没有使用的商家、价格、库存、交期、定制和运输事实。新增图片来自 Met Open Access API 的 Public Domain 对象，保留原图 URL、对象页、馆藏号、许可和署名；未抓取电商或社交平台图片。

文化背景补充使用 UNESCO 官方页面：Chinese calligraphy、Art of Chinese seal engraving、China engraved block printing technique、Traditional tea processing techniques and associated social practices in China。竹木文房对象只引用馆藏自身资料，未强行声明某个非遗项目身份。

## 推荐兼容性

新增 30 件记录满足以下边界：

- `status=inactive`，先被现有硬过滤排除；
- `catalog_role=catalog_reference`，加载器强制该角色不得 active；
- `supports_international_shipping=false`，不会冒充跨境能力；
- 没有定制选项，不会通过 Logo 或定制必须条件；
- `commercial_data_status=demo_assumption`、`merchant_fact_status=pending_verification`；
- 页面显示“馆藏探索参考 · 不参与推荐”，价格旁显示“演示预算带，不是商家公开报价”。

现有 20 件仍只适合演示推荐，不应在评审陈述中称为可交易、商家已确认或 Level A/B 产品。推荐引擎权重仍为 25/15/15/15/10/10/5/5，排序逻辑未修改。

## 待确认字段与风险

所有 50 件都仍缺少真实商家对价格、库存/产能、起订量、交期、国际运输、定制范围和材料商品规格的确认。30 件新增馆藏参考不适合进入正式推荐；原有 20 件也只适合 MVP 流程演示。正式上线前应以真实商家 SKU 替换或补充，并在获得商家来源后重新评为 Level A/B。

没有采用的候选包括无明确来源的电商转卖页、社交平台图片、搜索摘要中的所谓热销商品、无法确认授权的商业图，以及只有传统品类名称但没有真实对象或官方记录的 AI 概念商品。原因是它们无法满足真实性、归属或版权要求。

## 复现与文件

来源收集脚本：`scripts/expand_catalog.py`。它只使用固定对象 ID、Met 官方 API 与已记录的官方文化链接；运行时需要网络，自动化测试不访问网络。

主要数据文件：`data/demo/products.csv`、`heritage_items.csv`、`product_texts.csv`、`customization_options.csv`，以及 `data/catalog/heritage_products.csv`、`source_registry.csv`、`research_log.csv`、`coverage_matrix.csv`。

自动化验证覆盖数量、唯一性、外键、双语文本、10 类/6 地区/5 价格带、来源与事实边界、图片、加载性能、稳定排序，以及 30 件参考记录不进入推荐。
