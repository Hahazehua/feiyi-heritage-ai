# HAHA｜飞颐礼遇 — working notes

An AI platform connecting Chinese intangible-cultural-heritage (非遗) artisans
with global gifting demand. Streamlit single-page app, two audiences behind one
entry screen: buyers and artisans.

## Running it

There is no venv in this repo. Use the sibling clone's interpreter with an
explicit `PYTHONPATH`, or imports silently resolve to that other repo's source:

```bash
PYTHONPATH="$(pwd)/src" ../feiyi-heritage-ai/.venv/Scripts/python.exe -m pytest -q
```

```bash
PYTHONPATH="$(pwd)/src" ../feiyi-heritage-ai/.venv/Scripts/python.exe -m streamlit run app.py
```

PowerShell equivalent: `$env:PYTHONPATH = (Resolve-Path "src").Path` first.

**Streamlit does not hot-reload modules reached through `PYTHONPATH`.** After
editing anything under `src/`, restart the server — otherwise a CSS or agent
change looks like it had no effect.

Lint and format with `ruff check` and `ruff format`.

## The rule the product is built on

Facts are partitioned **verified / unverified / unknown** before any generation,
and agents may only use the verified set. This is architectural, not a line in a
prompt. A separate Guardian agent reviews generated output, so no model vouches
for its own work.

Practical consequences when changing anything:

- Never invent an identifier that looks checkable. Missing accession number
  means blank plus `needs_verification`, not a plausible-looking string. The
  surrounding rows are genuinely verifiable and an invented one poisons them.
- Cultural facts and commercial terms carry **separate** status columns and must
  never be presented as equally confirmed. Every price in this repo is
  `demo_assumption`.
- `recommendable` is a different axis from `verified`. All twenty demo products
  are recommendable and commercially unverified at the same time.

## Catalogue model

Two sources, deliberately distinct:

- `data/catalog/heritage_products.csv` — 50 Metropolitan Museum open-access
  objects, CC0, each with an accession number and a resolvable URL. Drives the
  catalogue gallery. **Do not add rows here without a real accession number**;
  the value of the other fifty depends on every row being checkable.
- `data/demo/products.csv` — the sellable catalogue. Most rows join to a museum
  record via `demo_product_id`; work with no such record is selected into its
  own labelled group in the gallery.

`catalog_role` gates recommendation: only `recommendation_demo` can be
recommended, and `catalog_eligibility.py` fails closed for everything else even
if the data is malformed. `partner_pending_verification` exists for work that
should be displayable but never recommended.

Budget is a **hard filter** (`price_min_fen > unit_budget_max_fen` rejects), so a
product priced above a request's budget never appears no matter how well it
matches otherwise.

## Deployment

Ships to `http://203.205.91.2:8000/` through a Gitee mirror, because GitHub and
Docker Hub are unreachable from that host. Push to GitHub, sync Gitee from its
web UI, then `bash deploy/deploy.sh` on the server. Ports 80/443/8080/8443 are
blocked by the competition organisers, so HTTPS is not available.

See `docs/wave3/ECS_DEPLOYMENT.md` for the full procedure and the China-network
workarounds (registry mirrors, PyPI index).

## Interface copy

All user-facing strings live in `src/heritagelink/i18n/{zh_CN,en_US}.py` and the
two files must stay key-for-key identical. Deterministic Growth Studio copy lives
separately in `growth_phrases.py`, with a test asserting every field differs
between languages so a missed translation cannot surface as English inside
Chinese output.

## Styling

`ui/theme.py` is token-first: colour, type, spacing, radius and elevation all
come from `:root` custom properties. Add a token rather than a literal.

Streamlit emits hashed class-scoped rules (`.st-emotion-cache-x h1`) whose
specificity beats a bare class, and the hash changes between releases. Raise
specificity by doubling an attribute or class selector rather than reaching for
`!important`. To target one specific element, give its container a `key` and
style the generated `.st-key-<key>` class.

Images crop to 4:3 for the grid. Work that must be seen whole (a framed artwork,
where cropping would cut the frame, inscription and seals) passes
`uncropped=True` to `product_image`.
