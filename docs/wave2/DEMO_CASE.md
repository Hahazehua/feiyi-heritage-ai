# Wave 2 代表性演示案例

本文件服务于 OPC 2026 Youth S3 第二轮 Wave 2：报名并提交截止为2026年7月20日，社区交叉评测为2026年7月21日，晋级结果公布为2026年7月22日。当前没有可公开验证的在线 Demo 链接，因此不提供占位 URL。

## 案例 A：企业海外礼赠完整路径

### 目标

用一条内置案例展示四个 Submitted Skills 如何串联为完整的 Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流。

### 输入

Streamlit 内置 `DEMO_CASE` 为：

> 企业计划为20位美国商务合作伙伴准备商务答谢礼物，每件预算300元，希望风格典雅、现代，可以加公司Logo，21天内完成，并提供中英文文化介绍。

### 运行前准备

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m streamlit run app.py
```

DeepSeek API Key 不是本案例的前置条件。为获得完全确定且不发送外部请求的路径，保留或选择“确定性演示模式”。

### 操作步骤与可观察证据

1. 在首页点击“体验企业海外礼赠案例”。
   - 页面进入需求确认阶段。
   - 当前 AppTest 校验数量为 20、单件预算为 300 元、Logo 要求为真、目的地为美国。
2. 查看“连续对话记录与补充”和结构化需求摘要，确认哪些字段已识别、缺失或仍需补充。
   - 可选多轮检查：在“继续补充或修正需求”输入一条新信息，点击“合并这条补充”，确认历史保留且累计需求更新。
   - 字段合并逻辑由 `tests/test_dialogue_manager.py::test_second_turn_merges_new_fields_instead_of_restarting` 覆盖；UI 补充路径由 `tests/test_app_smoke.py::test_confirmation_supports_a_second_conversation_turn` 覆盖。最终执行结果仍以 `EVALUATION.md` 的主线记录为准。
3. 点击“确认并查看推荐”。
   - 页面进入推荐阶段。
   - 结果数量为 1–3 件，不超过 3 件。
   - 页面显示需求信息覆盖度、当前置信度、推荐方式、匹配理由和约束状态。
4. 点击任一符合条件的目录 MVP 演示方案的“查看文化故事”。
   - 页面展示“中文文化介绍”“English Cultural Story”“工艺与依据”“定制建议”四个标签页。
   - 文化内容来自本地资料；当前 40 条双语资料均为 `draft`，页面提示待商家审核。
5. 点击“选择此方案并生成需求单”。
   - 页面进入商家需求单阶段。
   - 页面展示产品快照、数量、预算、主题、题字、Logo、包装、目的地、交付要求和待商家确认问题。
   - 页面提供可复制摘要和 JSON 下载按钮。

对应自动化证据：

- `tests/test_app_smoke.py::test_home_explains_value_and_demo_case_reaches_confirmation`
- `tests/test_app_smoke.py::test_confirmation_supports_a_second_conversation_turn`
- `tests/test_app_smoke.py::test_confirmation_is_required_before_recommendations`
- `tests/test_app_smoke.py::test_product_culture_and_inquiry_complete_five_stage_flow`

## 案例 B：无满足全部明确硬约束时不强行推荐

### 输入与操作

1. 首页选择“精准填写需求”。
2. 单件预算填写 `100` 元。
3. 采购数量填写 `1`。
4. 点击“确认这些需求”，再点击“确认并查看推荐”。

### 预期行为

- 页面进入推荐阶段，但不显示任何合格推荐。
- 页面明确显示“当前没有满足全部明确条件的现有产品，我们不会强行推荐”；这里的“现有产品”是当前 UI 对目录中 MVP 演示方案的简称。
- 页面不出现“选择此方案”操作。
- 冲突商品只能作为明确标注冲突的参考方案展示。
- 可选定制概念必须声明其不是现有产品、正式报价、产能或交付承诺。

对应自动化证据：

- `tests/test_app_smoke.py::test_precise_form_no_result_does_not_force_recommendation`
- `tests/test_recommender.py::test_no_eligible_products_return_conflicts_and_suggestions`
- `tests/test_customization_concept.py::test_no_result_can_generate_concept_without_inventing_product`

## 案例 C：无 DeepSeek API Key 的回退路径

### 操作

- 不创建 `.env`，或在页面主动选择“确定性演示模式”。
- 使用案例 A 的输入继续完成五阶段流程。

### 预期行为

- 页面明确提示当前使用演示解析模式。
- 结构化需求仍需用户核对。
- 推荐规则、文化内容和需求单继续运行，不依赖外部 API。
- API Key、底层 Prompt、模型推理和异常堆栈不会显示给用户。

对应自动化证据：

- `tests/test_request_parser.py::test_no_api_key_uses_demo_mode`
- `tests/test_request_parser.py::test_timeout_safely_falls_back_to_demo_mode`
- `tests/test_dialogue_manager.py::test_invalid_model_envelope_safely_uses_demo_parser`
- `tests/conftest.py::block_real_deepseek`

## 演示数据边界

- 所有价格、数量、交期、运输和定制能力均为 MVP 演示方案字段，仍需商家复核。
- 当前文化资料 40 条，全部为 `review_status=draft`；演示不等于商家审核通过。
- 图片与历史元数据来源和商品业务字段分开维护；开放馆藏物件本身不作为商品出售。
- 案例只证明当前 Prototype 的交易前匹配和需求整理能力，不证明支付、物流、库存、订单或真实履约能力。

## 验证状态

文档中的操作路径与现有代码和测试名称相对应。2026年7月17日的全量测试和独立 Streamlit 启动记录见 [`EVALUATION.md`](EVALUATION.md)；本文件不把自动化通过数改写为 Top-3 命中率或商家满意度。
