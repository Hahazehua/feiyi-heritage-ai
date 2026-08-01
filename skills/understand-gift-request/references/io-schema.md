# I/O Contract

- Input: current `ConversationState`, one non-empty user turn, runtime parser mode.
- Output: `DialogueTurnResult` with updated state, at most one question, next action, and parser source.
- Trigger: new message, clarification answer, or structured adjustment.
- Fallback: `deterministic_parser`; unknown values remain unknown.
- Entry: `heritagelink.skills.request_understanding_skill:execute`.

