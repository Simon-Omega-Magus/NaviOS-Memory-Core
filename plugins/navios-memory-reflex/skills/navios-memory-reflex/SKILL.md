---
name: navios-memory-reflex
description: Use when a Codex project needs durable local memory, provenance-addressed retrieval, prompt-triggered ambient context, graph-expanded memory queries, or recovery of an authoritative checkpoint after context compaction.
---

# NaviOS Memory Reflex

Use the bundled `scripts/navios-memory` CLI. The Codex hooks remain dormant until a project has a `.navios/` directory.

## Initialize

1. Ask before creating memory files in an existing project.
2. Run `navios-memory init` from the project root, or invoke the bundled script directly.
3. Edit `.navios/config.json` so inclusion is narrow and intentional.
4. Fill `.navios/checkpoint.md` with the accepted objective, verified state, constraints, and next action.
5. Run `navios-memory index`.

Never add secrets, credentials, private keys, tokens, or raw session transcripts to indexed memory. The indexer excludes suspicious filenames, but that is a backstop rather than permission to store secrets in notes.

## Retrieve

Use two or three differently phrased queries when ambiguity matters:

```text
navios-memory query "current objective" "accepted constraints" "related architecture" --top 8 --hops 2
```

The first lexical matches seed retrieval. Typed edges then expand to neighboring cells. A result seen through multiple queries receives a triangulation bonus.

- Treat `.navios/checkpoint.md` as authority only when the human has accepted it.
- Treat retrieved cells as evidence, not authority.
- Preserve each result's path, line range, cell ID, and SHA-256 handle.
- Open the cited source before consequential edits or when evidence conflicts.
- Respect abstention. Do not manufacture memory when no lexical seed matched.

## Maintain

- Rebuild the index after changing indexed sources.
- Keep the checkpoint concise enough to survive compaction intact.
- Do not edit the SQLite index directly; it is a replaceable projection.
- If compaction recovery pauses the first tool call, review the injected frozen bundle before reissuing an appropriate tool.

## Boundaries

Memory retrieval does not grant execution authority, resolve contradictions automatically, or replace tests and deterministic policy. The default engine is lexical retrieval plus exact typed adjacency. Experimental GraphSAGE work remains separate until it proves incremental value on held-out tasks.
