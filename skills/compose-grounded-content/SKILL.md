---
name: compose-grounded-content
description: Compose bilingual HeritageLink product content from approved catalog text. Use after a customer selects a formally recommended product or requests a final plan, with strict boundaries against invented certification, people, materials, prices, process, or history.
---

# Compose Grounded Content

Call `content_skill.execute` only for a selected product in the current formal recommendation result. Use approved product text and source notes; templates may organize wording but may not create facts.

Omit missing claims or use neutral pending language. Do not call this Skill when recommendation returns zero products.

Read [references/content-boundary.md](references/content-boundary.md) for the source and omission contract.

