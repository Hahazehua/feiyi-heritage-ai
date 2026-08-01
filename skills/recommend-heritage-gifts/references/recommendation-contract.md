# Recommendation Contract

- Input: formal product tuple and `RecommendationContext`.
- Output: `ProgressiveRecommendationResult` containing 0–3 recommendations, failures, alternatives, participating dimensions, and stable request mapping.
- Trigger: user requests recommendation, direction is sufficient, or clarification limit is reached.
- Fallback: `no_match_response`.
- Entry: `heritagelink.skills.recommendation_skill:execute`.

