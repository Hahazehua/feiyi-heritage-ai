---
name: infer-soft-preferences
description: Apply HeritageLink's allowlisted local inference policy before recommendation. Use when a validated request needs optional style, symbolism, packaging tone, or bilingual direction while commercial facts must remain unknown unless supplied by the customer.
---

# Infer Soft Preferences

Call `preference_inference_skill.execute` with a validated `ParsedCustomerRequest`.

Infer only allowlisted soft fields, keep provenance and confidence, and allow customer override. Preserve budget, quantity, price, capacity, lead time, shipping, MOQ, materials, dimensions, certification, and merchant customization ability exactly as stated or unknown.

Read [references/inference-policy.md](references/inference-policy.md) for the formal contract and safe fallback.

