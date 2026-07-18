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
5. A Codex plugin and concise operational skill.
6. Prompt-hook ambient retrieval that persists prompt identity only as a
   digest alongside bounded retrieved evidence.
7. Digest-locked `PreCompact`/`PostCompact` recovery.
8. `SessionStart`, `UserPromptSubmit`, and fail-safe `PreToolUse` delivery paths.
9. A fix and regression test for late `PostCompact` delivery observed in a live Codex session.
10. A synthetic judge project, one-command deterministic demo, and focused test suite.

## Release Verification

The July 18 release candidate was independently reviewed with a read-only
GPT-5.4 reviewer and then reverified after addressing its substantive findings.
The final checks include:

- 18 focused retrieval, exclusion, context-budget, and hook-lifecycle tests;
- regression coverage for stronger same-depth graph paths, ambiguous basename
  links, symlink escapes, long private prompts, working-directory changes, and
  a tool event between `PreCompact` and `PostCompact`;
- successful Codex plugin and skill validation;
- successful installation from an isolated wheel in a fresh virtual
  environment;
- successful marketplace and plugin installation in an isolated Codex home;
- deterministic demo output with 14 cells, 38 typed edges, exact provenance,
  retrieval abstention support, and a fail-safe denied tool event.

## Human Decisions

Simon Omega Magus provided the long-term memory-system direction, required local-first privacy, approved the narrow contest scope, authorized the Build Week branch and GitHub publication workflow, and retains final control over the video and Devpost submission.

## Codex Contributions

Codex with GPT-5.6 audited the old branch, identified broken contracts and unsupported claims, designed the bounded product surface, implemented the release, wrote tests, exercised plugin installation in an isolated Codex home, and prepared the judge-facing documentation.

The Devpost form receives the `/feedback` session ID for the thread where the core functionality was built.
