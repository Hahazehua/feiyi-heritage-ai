# Inference Contract

- Input: validated `ParsedCustomerRequest`.
- Output: `RecommendationContext` with stated/effective requests, provenance, reasons, and confidence.
- Trigger: immediately before recommendation.
- Allowed: style, symbolism, packaging tone, output language.
- Fallback: `preserve_unknown`.
- Entry: `heritagelink.skills.preference_inference_skill:execute`.

