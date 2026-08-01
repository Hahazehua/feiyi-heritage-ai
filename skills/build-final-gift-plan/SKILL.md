---
name: build-final-gift-plan
description: Build a downloadable HeritageLink customization inquiry from a selected real product, validated requirements, and grounded bilingual content. Use only after product selection while keeping unknown price, capacity, delivery, and service details pending.
---

# Build Final Gift Plan

Call `final_plan_skill.execute` only when the selected product belongs to the current recommendation and grounded content is available.

Return the existing inquiry JSON with product snapshot, requirement summary, cultural content, customization direction, and customer-friendly pending commercial fields. Never promise an unknown quote, production capacity, delivery date, or shipping ability.

Read [references/plan-schema.md](references/plan-schema.md) for the trigger, result, and fallback contract.

