# Plan Contract

- Input: product-specific `GiftRequest`, selected `Recommendation`, grounded `BilingualContent`, and validated final request.
- Output: validated customization inquiry dictionary, downloadable as JSON.
- Trigger: selected product plus explicit generate-plan action.
- Fallback: `omit_unknown_commercial_fields`.
- Entry: `heritagelink.skills.final_plan_skill:execute`.

