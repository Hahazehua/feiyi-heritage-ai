# HAHA · 飞颐礼遇

**Heritage Artisans, Horizons Ahead** — an AI platform connecting Chinese
intangible-cultural-heritage (非遗) artisans with global gifting demand.

> **3rd place — S3 Final · Buildathon**, 21 August 2026
> Dishui Lake Global OPC AI Challenge & The 2nd Yanyuan "Xiechuangzhe" AI+ International Entrepreneurship Competition
>
> **Selected for incubation and investment at Shanghai Lingang New Area.**
> Terms are still being negotiated as of 21 August 2026 and nothing has been
> disbursed; this line will be made specific once an agreement is signed.

**Live demo:** http://203.205.91.2:8000/ — no login, no registration.
Ports 80/443 are blocked by the competition host, so the service runs on 8000
and HTTPS is unavailable.

---

## The idea in one paragraph

China has roughly 870,000 catalogued heritage resources, 100,000+ representative
projects across four administrative tiers, and 90,000+ recognised bearers. Craft
exports were US$29.79bn in 2025 — **down 6.3%**, the steepest fall among major
cultural export categories. Supply is not the problem. An overseas buyer cannot
tell what an object is, why it costs what it costs, or whether its provenance
claim is real, and a language model asked to help will cheerfully invent an
accession number that does not exist. **HAHA's differentiator is not generating
better content. It is refusing to generate content that cannot be sourced, and
making that refusal visible.**

## The rule the product is built on

Every fact is partitioned **verified / unverified / unknown** *before* any
generation, and agents may read only the verified partition. This is an
architectural constraint, not an instruction in a prompt:

- **Eligibility gating fails closed.** `catalog_eligibility.py` rejects anything
  not explicitly recommendation-eligible, including when the data is malformed.
  A corrupted row does not become recommendable by accident.
- **A separate Guardian agent reviews generated output**, so no model vouches for
  its own work. It is registered beside the buyer chain, not inside it.
- **Cultural and commercial facts carry separate status columns** and are never
  rendered as equally confirmed. A craft tradition can be a verified public fact
  while the price of a specific object is still a demo assumption.
- **Recommendability is a different axis from verification.** A record can be
  commercially recommendable while its object-level provenance is unverified.

**Never invent an identifier that looks checkable.** A missing accession number
becomes a blank plus a verification flag, not a plausible-looking string. The
value of fifty genuine records depends on every row being checkable; one invented
row poisons the set.

## How it works

Two audiences behind one entry screen.

**Buyer side.** A natural-language gifting request is parsed into structured
criteria — recipient, occasion, budget, quantity, lead time, customisation,
destination. A deterministic engine applies hard filters and stable ranking, then
explains each result in the buyer's language with sourced cultural context, and
emits a structured inquiry for the merchant.

Ranking normalises only over dimensions the user actually supplied. Unknown
dimensions display as "not provided" rather than scoring zero or counting as a
match, so a sparse request yields low stated confidence instead of a confidently
wrong answer. Budget is a **hard filter** — a product above the stated ceiling
never appears, however well it matches otherwise. When the language model is
unavailable the flow falls back to the deterministic scorer: the product degrades
rather than failing.

**Artisan side.** An application-layer workflow that turns raw material into a
catalogue-ready record. The artisan describes the piece once — typed, or dictated
with a phone keyboard — and AI drafts every field. Provenance is tracked per
field, and a publication lifecycle gates what may be recommended. It does not
auto-publish.

Confirmation is split by consequence. Descriptive facts are read through and
confirmed in one action; price, currency, MOQ, lead time, shipping, customisation
and source URLs each need their own confirmation, because a buyer transacts on
those. A guard test blocks a single bulk confirmation from ever marking a price
confirmed.

**Story Studio.** The artisan can turn confirmed Heritage Passport facts into a
deterministic 60-second Xiaohongshu package: one Story Core, six timed 9:16 scenes,
voiceover, on-screen copy, camera direction, and provider-neutral image/video
prompts. Every factual scene carries a stable fact reference. A separate Story
Guardian blocks pending facts and unsupported credentials, history, or logistics
claims; the package cannot become approved until a named human approves it.

After script approval, a second gated stage creates a six-image visual storyboard.
It supports a no-key deterministic demo provider and an OpenAI Image API adapter,
including rights-confirmed artisan, product, and workshop reference images. Every
candidate retains its provider, model, prompt, hash, selection, and human approval.
Approved packages export as JSON plus selected images and references in one ZIP.

After human script approval, a distribution adapter derives four publication
packages from the same closed fact set: Xiaohongshu, TikTok, Instagram Reels, and
YouTube Shorts. Each package includes platform-shaped copy, a controlled CTA,
generic discovery hashtags, the complete fact-reference snapshot, and a six-scene
SRT track ending at exactly 60 seconds. The adapter never translates or invents
facts; a translated story must pass Guardian and human approval as its own master.
See [`docs/STORY_STUDIO_PHASE1.md`](docs/STORY_STUDIO_PHASE1.md),
[`docs/STORY_STUDIO_PHASE2.md`](docs/STORY_STUDIO_PHASE2.md), and
[`docs/STORY_STUDIO_MULTIPLATFORM.md`](docs/STORY_STUDIO_MULTIPLATFORM.md).

## The seven Skills

The buyer chain (`customer_flow`). Each step's input, output, duration and safety
checks can be opened live at `?review_mode=1`.

| # | Skill | Required | Fallback |
|---|---|---|---|
| 1 | 礼赠需求理解 · Request understanding | yes | `deterministic_parser` |
| 2 | 受控软偏好推断 · Bounded preference inference | yes | `preserve_unknown` |
| 3 | 非遗礼品硬过滤与稳定推荐 · Hard filter and stable ranking | yes | `no_match_response` |
| 4 | 有事实边界的双语文化内容组织 · Grounded bilingual content | no | `omit_unverified_content` |
| 5 | 最终礼品方案生成 · Final gift plan | no | `omit_unknown_commercial_fields` |
| 6 | 匿名授权选择记录 · Consented choice capture | no | `continue_without_storage` |
| 7 | 匿名礼品选择信号分析 · Choice signal analysis (offline) | no | `insufficient_sample_report` |

The artisan growth chain (`artisan_growth`) is registered **beside** this one, not
inserted into it: Market Intelligence, Marketing Strategist, Creative Agent,
**Cultural Guardian** (`fail_closed_human_review`), Creative Revision.

## Catalogue

The figures below are computed from the current contents of
`data/demo/products.csv` and `data/demo/product_texts.csv`. They are not cached
from older documents, and a test recomputes every row.

| Metric | Current |
|---|---:|
| Catalogue records | 54 |
| Recommendation-eligible | 23 |
| Museum or cultural reference | 30 |
| Partner-supplied, pending verification | 4 |
| Bilingual content records | 108, i.e. 54 per locale |
| Category coverage | 11 |
| Data quality | 54 records, all Level C demo data |
| Verified merchants | 1 (安徽飞颐文化有限公司, supplying 4 partner works) |

Categories: `bamboo`, `calligraphy`, `ceramics`, `fan`, `iron_painting`, `jade`, `lacquer`, `seal`, `tea`, `textile`, `woodblock`.

23 `recommendation_demo` records are `active`. 30 `catalog_reference` and 1
`partner_pending_verification` record are `inactive` and carry no verified price,
capacity, customisation or delivery information.

**50 of the 54** carry Metropolitan Museum accession numbers and resolvable URLs
under CC0 1.0 / Public Domain; six were spot-checked against the museum's API and
matched exactly. The remaining **4** are partner-supplied contemporary Wuhu iron
paintings with no museum record. They are labelled `needs_verification` rather
than issued a plausible-looking identifier, and 3 of their photographs were
edited with generative AI (perspective, background, colour and exposure), which
is recorded as `image_status=generative_edit_from_photograph`. A museum source
does not imply the museum endorses this project.

## Evidence

**373 automated tests.** More important than the count is what several guard:

- A record declaring itself unverified may not appear in the museum table, may
  not claim an open museum licence, and may not present commercial terms as
  confirmed unless a real merchant — not the platform's own demo entity — stands
  behind them.
- **Every guard was mutation-tested**: the rule was deliberately broken to
  confirm the test actually fails. A guard that passes vacuously is worse than
  none, because it manufactures false confidence.
- A documentation guard recomputes this README's catalogue table from the CSVs,
  because the numbers had silently drifted once already.
- Interface copy is enforced key-for-key across locales, so a missed translation
  cannot surface as English inside Chinese output.

## Local setup

There is no virtualenv in this repository. Use the sibling clone's interpreter
with an explicit `PYTHONPATH`, or imports silently resolve to that other repo:

```bash
PYTHONPATH="$(pwd)/src" ../feiyi-heritage-ai/.venv/Scripts/python.exe -m pytest -q
```

```bash
PYTHONPATH="$(pwd)/src" ../feiyi-heritage-ai/.venv/Scripts/python.exe -m streamlit run app.py
```

Streamlit does not hot-reload modules reached through `PYTHONPATH`; restart the
server after editing anything under `src/`. Lint and format with `ruff check` and
`ruff format`.

## Deployment

Docker + nginx on a China-hosted ECS instance. GitHub and Docker Hub are
unreachable from that host, so the pipeline pushes to GitHub, mirrors through
Gitee, and pulls from Gitee on the server. `deploy/deploy.sh` is idempotent —
pull, rebuild, restart, poll health — and safe to re-run. See
`docs/wave3/ECS_DEPLOYMENT.md` for the China-network workarounds.

## Scope and limitations

Stated plainly, because the product's credibility depends on the boundary being
visible:

- No verified merchants beyond a single affiliated partner entity — not an
  arm's-length third party.
- No customers, orders, transactions, revenue, or market impact.
- All 108 cultural content records are `draft`; none has been signed off by a
  merchant or cultural reviewer.
- Commercial terms on the 50 museum-derived products are demo assumptions.
- The relationship between a partner work offered for sale and the accessioned
  object behind its number is **not yet confirmed**, and the record says so.
- The evidence here is engineering evidence, not commercial validation.

## Who it serves

Overseas buyers who want a culturally meaningful gift and need to understand what
they are buying; heritage artisans who make the work but cannot produce listing
material an overseas buyer can read; and institutions that need provenance they
can check rather than prose they must trust.

## Why this exists

Digitising heritage is usually framed as preservation. The harder problem is
sustainable participation: an artisan needs a channel, and a channel needs trust.
Trust cannot be generated. It can only be sourced, bounded, and shown — which is
what this codebase tries to make structurally true rather than merely claimed.
