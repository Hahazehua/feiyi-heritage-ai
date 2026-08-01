---
name: recommend-heritage-gifts
description: Produce zero to three stable HeritageLink recommendations from the formally eligible catalog. Use after validated requirements and controlled inference when hard constraints, fixed eight-dimension scoring, reference-product exclusion, and truthful no-match handling are required.
---

# Recommend Heritage Gifts

Call `recommendation_skill.execute` with the effective recommendation context and the formally recommendable product tuple.

Preserve the existing hard filters, weights, stable product-ID tie break, and rule that missing fields do not score zero. Return zero products plus conflicts and adjustment suggestions when nothing qualifies; never substitute a reference-only item.

Read [references/recommendation-contract.md](references/recommendation-contract.md) for inputs, outputs, catalog counts, and fallback.

