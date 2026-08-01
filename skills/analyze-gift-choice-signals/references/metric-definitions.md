# Metric definitions

- `selection_rate`: sessions or recommendations with a selection divided by the relevant denominator.
- `customization_brief_rate`: sessions generating a brief divided by sessions started.
- `recommendation_without_selection_rate`: recommended sessions without a choice divided by recommended sessions.
- Product counts: explode each ordered recommendation list; count selection events by selected product.
- Rank counts: explode recommendation positions; count selections by selected rank.
- Conversation averages: mean persisted conversation-turn count for the included sessions.
- Segments: recipient, scene, budget bucket, customization requirement, Logo requirement, and coarse destination region.

Return a rate as `null` when its denominator is below `minimum_sample_size`. Always accompany insufficient overall data with: `当前样本量不足，仅展示观察结果，不代表稳定偏好。`
