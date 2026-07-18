# OpenAI Build Week 2026 Development Record

This record distinguishes the pre-existing research repository from the implementation added during the July 13-21, 2026 submission period.

## Prior Work

The public Git history records four April 2026 milestones:

- `master`: initial memory-substrate prototype
- `v2-simplified`: dependency and setup cleanup
- `v3-hardlink-core`: hardlink-backed file identity and metadata experiments
- `v4-mind-weaver`: fuzzy ontology and GraphSAGE experiments

That code is retained under `legacy/gnn-v4/` on the Build Week branch. It is historical context, not the runnable submission path.

## Build Week Extension

Work after July 13 was carried out with Codex and GPT-5.6 in the primary project thread. The extension includes:

1. A fresh cell index with exact path, line, cell, and SHA-256 provenance.
2. Dependency-light BM25-style lexical retrieval.
3. Typed multi-hop graph expansion with explicit hub control through lexical seeding.
4. Multiple-query triangulation and negative-control abstention.
5. Non-destructive assimilation of ordinary notes into replaceable cells and a
   typed relationship overlay.
6. Body-free Top-200-per-query surveys followed by exact-revision selective
   hydration with no partial cells.
7. Append-only, deduplicated, provenance-bound proposal-cell cultivation.
8. Human-will guidance with no automatic age decay and an append-only question
   primitive that binds agent-supplied claim labels to distinct exact source
   revisions without granting execution capability.
9. A Codex plugin and concise operational skill, including read-only
   fork-assisted candidate digestion guidance.
10. Prompt-hook ambient retrieval that persists prompt identity only as a
   digest alongside bounded retrieved evidence.
11. Digest-locked `PreCompact`/`PostCompact` recovery.
12. `SessionStart`, `UserPromptSubmit`, and fail-safe `PreToolUse` delivery paths.
13. Fixes and regression tests for late `PostCompact` delivery and stale-source
    injection observed through the automatic direct-query path.
14. A deterministic 240-document scale benchmark that measures candidate
    recall, multi-hop reach, abstention, and staged context reduction.
15. A synthetic judge project, one-command deterministic demo, and focused test suite.

## Release Verification

The July 18 release candidate was independently reviewed twice with read-only
GPT-5.4 reviewers and then reverified after addressing their substantive findings.
The final checks include:

- 45 focused retrieval, staged-loading, cultivation, will-coherence, exclusion,
  context-budget, and hook-lifecycle tests;
- regression coverage for stronger same-depth graph paths, ambiguous basename
  links, source/output symlink escapes, hardlink policy, exact CRLF byte hashes,
  stale direct-query sources, long private prompts, working-directory changes,
  will-queue tampering, and a tool event between `PreCompact` and `PostCompact`;
- successful Codex plugin and skill validation;
- successful installation from an isolated wheel in a fresh virtual
  environment;
- successful marketplace and plugin installation in an isolated Codex home;
- deterministic demo output with 14 initial cells, 38 typed edges, exact
  provenance, staged hydration, proposal cultivation, one open will-coherence
  question, retrieval abstention support, and a fail-safe denied tool event;
- deterministic 240-document benchmark output with all four required memories
  in the survey union, one graph-only hit, negative-control abstention, and about
  92% less rendered body context than eager hydration of that union. Selection
  remains oracle-assisted and is not represented as autonomous relevance proof.

## Human Decisions

Simon Omega Magus provided the long-term memory-system direction, required local-first privacy, approved the narrow contest scope, authorized the Build Week branch and GitHub publication workflow, and retains final control over the video and Devpost submission.

## Codex Contributions

Codex with GPT-5.6 audited the old branch, identified broken contracts and unsupported claims, designed the bounded product surface, implemented the release, wrote tests, exercised plugin installation in an isolated Codex home, and prepared the judge-facing documentation.

The Devpost form receives the `/feedback` session ID for the thread where the core functionality was built.
