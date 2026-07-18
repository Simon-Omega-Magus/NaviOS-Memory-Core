---
tags: [memory, compaction, codex]
links: [safety.md, decisions.md]
---
# Memory Reflex Architecture

Each prompt is used as an ephemeral query over provenance-addressed memory cells; the raw prompt is not persisted.

Lexical matches seed retrieval, typed graph edges expand to neighboring cells, and multiple query formulations provide a triangulation bonus.

# Compaction Lifecycle

Before compaction, NaviOS freezes the authoritative checkpoint and the last retrieved evidence into a digest-locked recovery bundle.

After compaction, the bundle is injected through SessionStart or UserPromptSubmit; if those deliveries arrive late, the first tool call is cancelled and receives the bundle instead.
