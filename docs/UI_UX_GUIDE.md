# HAHA UI/UX Guide

## Product character

HAHA should feel calm, trustworthy, international, and human-centered. Cultural heritage is expressed through product imagery, craftsmanship, sources, and stories—not decorative clichés.

The interface should avoid looking like a database admin tool, a collection of AI demos, or a technical execution console.

## Information architecture

The global header has three destinations:

1. **AI Shopping / 我是买家** — describe a real gift need, compare grounded recommendations, understand cultural meaning, and create an inquiry-ready gift plan.
2. **Artisan Studio / 我是手艺人** — structure artisan-provided knowledge, confirm facts, create a Heritage Passport, and use Growth Studio.
3. **How HAHA Works / 了解 HAHA** — explain the Digitize → Grow → Connect platform story.

Artisan Studio keeps two primary workspaces visible without adding deep navigation:

- Products & Heritage Passport
- Growth Studio

## Visual system

Core styles live in `src/heritagelink/ui/theme.py`. New screens should reuse the established tokens and components instead of adding isolated page CSS.

| Element | Direction |
|---|---|
| Background | Warm neutral, low visual noise |
| Text | Charcoal with muted secondary copy |
| Accent | Restrained heritage-inspired bronze/brown |
| Cards | Thin borders, moderate radius, limited shadow |
| Spacing | Prefer whitespace over extra containers |
| Typography | System and web-safe Chinese/English fallbacks |
| Status | Use semantic tone and text; never rely on color alone |

Reusable presentation helpers are in:

- `ui/system.py`: status badges, metrics, empty states, demo labels
- `ui/header.py`: navigation, language selection, competition demo controls
- `ui/home.py`: landing and platform story
- `ui/artisan_studio.py`: supportive onboarding and progress
- `ui/heritage_passport.py`: source and verification presentation
- `ui/growth_studio.py`: agent flow, opportunities, Guardian review, assets, completion

## Language rules

- All important interface copy belongs in `src/heritagelink/i18n/zh_CN.py` and `en_US.py`.
- Use `t("namespace.key")`; do not scatter page-level language conditionals for copy.
- Chinese and English translation resources must have identical key sets.
- Interface language and campaign output language are separate settings.
- Stable domain values, IDs, repository values, and test-sensitive Chinese defaults remain unchanged internally.
- Product names and bilingual source content may select the appropriate stored language field.

## Trust and status rules

- **Profile completeness** means information coverage, not verification.
- Unknown information is normal and uses a neutral presentation.
- Demo price, inventory, shipping, capacity, merchant, and lead-time information must not appear verified.
- Museum/reference objects must remain visually distinct from recommendation-eligible demo products.
- Artisan drafts and Growth campaigns do not automatically enter Buyer recommendations.
- Guardian output should show supported claims, revisions, remaining risks, and raw-versus-revised evidence in human-readable form.

## Loading, empty, and error states

- Show named workflow stages during long AI operations; do not invent percentages.
- Empty states should explain why the area is empty and offer one safe next action.
- User-facing errors describe what was preserved or not saved. Detailed exceptions remain in logs.
- Storage or optional AI failures must not erase the current safe draft.

## Responsive behavior

Validate at 1440 px, 1024 px, and 390 px.

At narrow widths:

- navigation and primary actions stack cleanly;
- primary CTAs may become full width;
- story, metric, opportunity, and agent-flow cards become one column;
- comparison cards replace wide tables;
- tabs remain usable without forcing page-level horizontal scrolling;
- long source text and campaign assets wrap safely.

## Accessibility and content quality

- Maintain logical heading order and descriptive button labels.
- Keep visible focus behavior provided by Streamlit.
- Escape user or model content before inserting it into HTML.
- Do not expose raw JSON, implementation types, or internal state-machine vocabulary in standard user views.
- Keep review-only execution details behind the existing environment and query gates.

## Validation checklist

Before release:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
python -m streamlit run app.py --server.headless true
```

Manually verify both interface languages, Buyer, Artisan, Growth Studio, Guardian revisions, save/reopen, About, Competition Demo reset, and all three target widths.

