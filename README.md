# NaviOS Memory Reflex

[![Verify NaviOS Memory Reflex](https://github.com/Simon-Omega-Magus/NaviOS-Memory-Core/actions/workflows/ci.yml/badge.svg?branch=build-week-2026-memory-reflex)](https://github.com/Simon-Omega-Magus/NaviOS-Memory-Core/actions/workflows/ci.yml)

NaviOS Memory Reflex is a local-first memory and compaction-recovery layer for
Codex. It non-destructively assimilates ordinary project notes into
provenance-addressed cells, surveys them through a typed graph, hydrates only
selected bodies, cultivates source-linked memory proposals, and restores a
frozen authoritative checkpoint after context compaction.

This Build Week release deliberately makes a narrower claim than "infinite memory": it provides a runnable, inspectable memory reflex with explicit abstention and exact evidence handles.

![NaviOS Memory Reflex](media/navios-memory-reflex-thumbnail.png)

## What It Demonstrates

- **Prompt memory reflex:** Codex `UserPromptSubmit` hooks retrieve relevant project memory automatically.
- **Zero-setup assimilation:** Ordinary notes become replaceable sentence and passage cells without source edits.
- **Exact provenance:** Every result carries a relative path, line range, cell ID, and SHA-256 content handle.
- **Typed graph expansion:** Lexical seeds expand through sequence, heading, explicit-link, backlink, and shared-tag edges.
- **Query triangulation:** Distinct query formulations reward evidence found from multiple directions.
- **Staged context loading:** Top-200-per-query body-free surveys precede revision-checked selective hydration.
- **Proposal-first neurogenesis:** Agents can append deduplicated, provenance-bound proposed cells without silently rewriting accepted notes.
- **Will-coherence primitive:** Agents can queue a no-execution question whose
  claim labels are bound to distinct exact source revisions.
- **Safe abstention:** Unrelated queries inject nothing instead of forcing a nearest neighbor.
- **Compaction recovery:** A digest-locked checkpoint is frozen before compaction and delivered afterward.
- **Fail-safe tool boundary:** If normal recovery delivery is late, the first tool call is cancelled and receives the frozen bundle.
- **Local processing:** The default index and retrieval engine use Python and SQLite without a remote embedding API.

## Three-Minute Judge Demo

Requirements: Python 3.10 or newer on Linux or macOS and a writable temporary directory (normally `/tmp`). No API key or package installation is needed.

```bash
git clone --branch build-week-2026-memory-reflex \
  https://github.com/Simon-Omega-Magus/NaviOS-Memory-Core.git
cd NaviOS-Memory-Core
python3 demo/run_demo.py
```

The demo copies a small project into a temporary directory, assimilates its
notes, performs a body-free multi-query survey, selectively hydrates three
cells, cultivates one proposal, and simulates the Codex compaction hook
sequence. It shows the intentionally cancelled first tool call plus recovered
checkpoint and never reads or edits the judge's own project files.

Run all focused tests:

```bash
python3 -m unittest -v \
  tests/test_memory_reflex.py tests/test_staged_benchmark.py
```

## Standalone CLI

The bundled CLI can be run directly. One command initializes the local state
and derives a read-only graph from ordinary notes:

```bash
PLUGIN=plugins/navios-memory-reflex
python3 "$PLUGIN/scripts/navios-memory" --root ./my-project assimilate
```

Edit `my-project/.navios/config.json` to select sources and fill in
`my-project/.navios/checkpoint.md`. For a small bounded packet:

```bash
python3 "$PLUGIN/scripts/navios-memory" --root ./my-project index
python3 "$PLUGIN/scripts/navios-memory" --root ./my-project query \
  "current objective" "accepted constraints" "related architecture" \
  --top 8 --hops 2
```

For a broad cast that keeps source paragraphs out until selection:

```bash
python3 "$PLUGIN/scripts/navios-memory" --root ./my-project survey \
  "current objective and decisions" \
  "constraints contradictions and safety" \
  "related architecture and experiments" \
  --candidates 200 --hops 3 --show 30

python3 "$PLUGIN/scripts/navios-memory" --root ./my-project hydrate \
  CELL_ID_OR_UNIQUE_PREFIX ... --max-chars 7000
```

An agent can preserve a verified discovery as an evidence-only proposal. The
optional `::SHA256` revision lock fails closed if the source changed:

```bash
python3 "$PLUGIN/scripts/navios-memory" --root ./my-project cultivate \
  --title "Reusable retrieval lesson" \
  --body-file /tmp/proposed-memory.md \
  --source "docs/design.md::EXACT_64_CHARACTER_SHA256" \
  --kind retrieval-lesson --tag memory --tag retrieval
```

When two plausible human directions conflict, queue one bounded question
without aging out or downgrading either claim:

```bash
python3 "$PLUGIN/scripts/navios-memory" --root ./my-project \
  queue-will-question \
  --claim claim:older --claim claim:newer \
  --question "Which interface preference governs this project?" \
  --scope project.interface \
  --source "docs/older-direction.md::EXACT_64_CHARACTER_SHA256" \
  --source "docs/newer-direction.md::EXACT_64_CHARACTER_SHA256"

python3 "$PLUGIN/scripts/navios-memory" --root ./my-project \
  will-questions --json
```

An optional package install provides the `navios-memory` command:

```bash
python3 -m pip install .
```

## Codex Plugin

This repository is also a valid Codex marketplace. With a current Codex CLI:

```bash
codex plugin marketplace add Simon-Omega-Magus/NaviOS-Memory-Core \
  --ref build-week-2026-memory-reflex
codex plugin add navios-memory-reflex@personal
```

Start a new Codex thread inside a project initialized with
`navios-memory assimilate`. The hooks remain dormant in projects without a
`.navios/` directory. v0.2 uses index schema v2; rebuild older replaceable
indexes with `navios-memory assimilate` after upgrading.

Supported plugin surface:

- Codex CLI 0.144.4 or newer
- Linux and macOS
- Python 3.10 or newer

The standalone CLI is independent of Codex and should work anywhere Python and SQLite are available; Codex hook support is currently tested on Linux.

## How Retrieval Works

```text
selected local files
        |
        v
provenance cells ---- typed edges
        |                  |
        +---- lexical seeds+
                 |
                 v
       body-free graph survey
                 |
                 v
       selective cell hydration
                 |
                 v
       Codex context / proposal cell
```

Documents are split along headings and paragraphs into sentence or passage cells. The SQLite index is a replaceable projection; original files remain authoritative. BM25-style lexical scoring supplies evidence-bearing seeds. Graph traversal can then surface adjacent or explicitly linked context without turning unrelated hubs into unconditional results.

Multiple queries are scored independently and normalized before combination. Cells reached by more than one formulation receive a triangulation bonus. If no query has a lexical seed, retrieval abstains and graph expansion never starts.

## Deterministic Scale Benchmark

Run the reproducible substrate benchmark without an API key or LLM judge:

```bash
python3 benchmarks/run_staged_retrieval_benchmark.py
```

The default 240-document corpus forces three Top-200 candidate casts. The
current deterministic result surfaces all four required memories, reaches one
lexically opaque requirement through a graph hop, abstains on the negative
control, and reduces rendered context by about 92% compared with eagerly
hydrating the complete survey union (200 candidate bodies in this corpus).

The selective step is explicitly oracle-assisted. This benchmark proves broad
candidate recall and the context-saving capacity of staged hydration; it does
not claim that autonomous relevance judgment is solved. The next evaluation
must replace the oracle with an agent or learned specialist and score held-out
tasks prospectively.

## Compaction Recovery

1. `UserPromptSubmit` injects a bounded provenance packet and stores only its redacted packet plus the prompt SHA-256, not the raw prompt.
2. `PreCompact` freezes `.navios/checkpoint.md` and the last packet into a digest-locked bundle.
3. `PostCompact` marks recovery pending.
4. `SessionStart` or `UserPromptSubmit` injects the frozen bundle.
5. If those events arrive out of order, `PreToolUse` cancels one tool call, injects recovery, and requires the agent to review and reissue an appropriate operation.

Session recovery state is stored with private permissions under `~/.local/state/navios-memory-reflex/`, outside the project repository.

## Security Boundaries

- Suspicious filenames containing terms such as `token`, `secret`, `credential`, `.env`, or private-key names are excluded.
- `.naviosignore` and config exclusions should still be reviewed before indexing.
- Filename exclusion is a backstop, not a content-aware secret scanner.
- Source and output symlinks are rejected. Hardlinked sources are ignored by
  default because their external aliases cannot be inferred; projects that use
  intentional hardlink-backed brain matter can set
  `"allow_hardlinked_sources": true` after reviewing that privacy tradeoff.
- Raw transcripts are not copied into project memory.
- The hook and skill encode a no-age-decay human-will contract, but v0.2 does
  not authenticate raw prompt authorship or derive semantic claims
  automatically; see [Human Will Coherence](docs/HUMAN_WILL_COHERENCE.md).
- A raw prompt cell's quarantine or `authorization_effect: none` label limits
  mutation and action capability; it does not erase the prompt's directional
  influence. Derived claims remain active until completion, explicit expiry,
  revocation, or clear same-scope supersession.
- The append-only conflict-queue primitive pairs each claim label with one
  live, exact source revision and sets `execution_effect: none`; semantic claim
  extraction, authorship authentication, and human resolution remain future
  work.
- Memory labels declared by an ordinary source are shown as unverified.
  Proposal-path labels are enforced as `agent-derived / evidence-only /
  proposed` through query, survey, and hydration.
- The system does not resolve contradictions automatically or replace deterministic policy, tests, permissions, and sandboxing.

## Build Week Extension

The repository contains April 2026 experiments with hardlink-backed brain matter and GraphSAGE. Those are preserved in [`legacy/gnn-v4`](legacy/gnn-v4) and are not required by the working demonstration.

The `build-week-2026-memory-reflex` branch adds the post-July-13 implementation evaluated here:

- dependency-light cell index and typed graph
- exact provenance packets and negative-control abstention
- multi-query triangulation
- non-destructive ordinary-file assimilation and typed relationship overlays
- body-free Top-200 surveys and source-current selective hydration
- append-only proposal-cell cultivation and fork-digestion guidance
- a persistent human-will authority contract and machine-readable conflict
  queue that remain separate from execution permissions
- Codex plugin, skill, and compaction hooks
- privacy-preserving hook state
- deterministic judge demo and focused tests

See [Build Week development record](docs/BUILD_WEEK_2026.md) for the distinction between prior work and the submitted extension.

## Judge Media

- [Project thumbnail](media/navios-memory-reflex-thumbnail.png)
- [Architecture visual](media/navios-memory-reflex-architecture.png)
- [Deterministic proof visual](media/navios-memory-reflex-proof.png)
- [Under-three-minute video script](docs/DEMO_VIDEO_SCRIPT.md)
- [YouTube title, description, timestamps, and upload settings](docs/YOUTUBE_UPLOAD.md)

The optional `media/render-demo-video.sh` script produces a complete narrated
fallback video when `ffmpeg`, `ffprobe`, and `espeak-ng` are installed.

## Codex and GPT-5.6 Collaboration

GPT-5.6 in Codex was used to audit the pre-existing repository, reduce an expansive research architecture to a testable product boundary, implement the new plugin and deterministic engine, construct adversarial tests, and reproduce a real hook-ordering failure where `PostCompact` can arrive after recovery delivery. The human retained product direction, privacy constraints, scope approval, contest registration, and final publication decisions.

The required `/feedback` Codex session ID is supplied in the Devpost submission.

## Honest Limitations

- This release is not an infinite context window.
- Retrieval quality still depends on source quality and explicit graph structure.
- It does not yet learn edge weights continuously.
- GraphSAGE remains experimental until it beats the deterministic baseline on held-out prospective tasks.
- The scale benchmark uses oracle-assisted selective hydration and is not an end-to-end agent score.
- Machine classification of will claims, automatic contradiction detection,
  authenticated resolution events, and the TUI review surface remain follow-on
  work; the authority contract and open-question queue are agent-operational.

## License

MIT. See [LICENSE](LICENSE).
