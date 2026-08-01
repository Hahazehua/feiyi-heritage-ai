---
name: understand-gift-request
description: Understand and merge HeritageLink natural-language or structured gift requirements across turns. Use for every new customer requirement, clarification answer, or manual adjustment when commercial fields must remain user-provided and DeepSeek failure must fall back safely.
---

# Understand Gift Request

Validate the incoming turn, call `request_understanding_skill.execute`, and merge it into the existing `ConversationState`.

Use DeepSeek only through the existing dialogue client. On unavailability or invalid output, use `deterministic_demo`; preserve unrecognized fields as unknown. Ask no more than one active question.

Never invent budget, quantity, delivery, shipping, customization, or product facts. Send only field names, counts, and parser source to execution trace.

Read [references/io-schema.md](references/io-schema.md) for the formal input, output, trigger, fallback, and safety contract.

