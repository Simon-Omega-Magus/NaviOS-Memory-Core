---
tags: [memory, design]
---
# Accepted Decisions

The default release uses deterministic BM25-style lexical ranking plus typed adjacency because it is dependency-light, explainable, and easy for judges to reproduce.

GraphSAGE remains an experimental optional lineage until held-out evaluation proves incremental utility beyond the deterministic baseline.

Every returned cell includes a relative path, exact line range, stable cell identifier, and SHA-256 content handle.
