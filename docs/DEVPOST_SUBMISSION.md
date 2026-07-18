# Devpost Submission Draft

## Project Overview

- **Project name:** NaviOS Memory Reflex
- **Elevator pitch:** Local-first memory for Codex: retrieve
  provenance-linked context through typed graph cells and safely restore
  authoritative checkpoints after compaction.
- **Submission category:** Developer Tools
- **Submitter type:** Individual

## Project Story

### Inspiration

AI coding agents can reason through difficult work and still lose critical
intent when their context is compacted. A transcript preserves chronology,
but it does not automatically surface the right prior decision at the moment
that decision matters. I wanted to build a **memory reflex**: a small,
automatic process that retrieves relevant evidence before work and restores a
trusted state after compaction.

The design was inspired by associative memory in neuroscience, layered and
symbolic models of mind from cognitive and Jungian psychology, and the value
of examining a problem through multiple perspectives. These are design
metaphors, not scientific or paranormal claims. Conversations with ChatGPT
helped crystallize that broad inspiration into a testable product boundary:
durable local memory for Codex with exact provenance, bounded retrieval, and
the ability to abstain.

### What it does

NaviOS Memory Reflex turns selected project notes into
provenance-addressed sentence and passage cells. Each cell retains its source
path, exact line range, stable identifier, and SHA-256 content handle.

For each prompt, the plugin:

1. Finds evidence-bearing lexical seeds.
2. Expands through typed graph relations such as document sequence, shared
   headings, explicit links, backlinks, and shared tags.
3. Injects a bounded context packet with exact source handles, or injects
   nothing when no supported evidence is found.

The CLI and Python API also accept several query formulations at once and
reward evidence reached from more than one direction. The deterministic demo
shows this triangulation path explicitly.

Before Codex compacts its context, NaviOS freezes the authoritative project
checkpoint and the last retrieval packet into a digest-locked recovery bundle.
After compaction it restores that bundle through Codex hooks. If normal
delivery arrives out of order, the first tool call is cancelled and receives
the recovery bundle so consequential work cannot silently continue from an
unrecovered state.

The default engine is local-first. It uses Python and SQLite and requires no
remote embedding API or API key.

### How we built it

This repository began with experimental hardlink and GraphSAGE prototypes.
During Build Week, I used GPT-5.6 in Codex to audit that earlier code, identify
broken contracts and unsupported claims, and narrow the research architecture
into a reproducible developer tool.

The Build Week implementation adds a fresh deterministic cell index, typed
multi-hop graph traversal, multi-query triangulation, negative-control
abstention, exact provenance packets, a Codex plugin and skill, compaction
hooks, private runtime state, an isolated installation path, focused tests,
and a one-command judge demonstration. Prior GraphSAGE experiments remain in
the repository as clearly labeled historical work rather than being presented
as part of the default product.

Codex accelerated repository exploration, implementation, adversarial test
design, packaging, and documentation. I supplied the long-term product
direction, cognitive-memory concepts, privacy requirements, scope decisions,
and final publication control.

### Challenges

- **Retrieval is not truth.** A relevant old note can still be obsolete or
  wrong, so every result remains source-linked evidence rather than execution
  authority.
- **Graph expansion can amplify noise.** Lexical evidence must seed traversal;
  unrelated queries abstain instead of activating a graph hub.
- **Memory can expose secrets.** Suspicious filenames are excluded by default,
  source selection is explicit, and raw prompts are represented in saved state
  only by a digest rather than transcript text.
- **Hook ordering is not always intuitive.** Live testing exposed a case where
  `PostCompact` could arrive after another recovery path had already delivered
  the bundle. The state machine and regression tests now prevent that late
  event from rearming recovery incorrectly.
- **Judges need a reproducible project.** The demo runs in a temporary synthetic
  project with no API key and does not inspect the judge's own files.

### What we learned

The most useful memory system is not the one that returns the most text. It is
the one that can explain exactly why each fragment appeared, remain quiet on
unsupported queries, and recover an authoritative working state when the
model's transient context changes.

We also learned to treat deterministic graph retrieval as a strong,
inspectable baseline. Learned GNN views may become useful later, but they
should earn a place through held-out evaluation rather than being assumed
superior.

### What's next

- Evaluate retrieval on prospective real-world agent tasks.
- Add authority, currentness, and contradiction-aware evidence handling.
- Compare specialist learned GNN views against the deterministic baseline.
- Support additional structured source types and memory-cell views.
- Measure whether the complete reflex reduces repeated reading and improves
  post-compaction task continuity over ordinary checkpoint-only workflows.

## Built With

- Python
- SQLite
- OpenAI Codex
- GPT-5.6
- Codex CLI
- Codex plugins and hooks
- GitHub
- Linux
- Markdown
- JSON
- BM25-style lexical retrieval
- Typed graph traversal
- SHA-256 provenance

## Try It Out

Add after the Build Week branch is reviewed, committed, and pushed:

`https://github.com/Simon-Omega-Magus/NaviOS-Memory-Core/tree/build-week-2026-memory-reflex`

## Media

Add after final demo capture:

- project thumbnail, 3:2 ratio;
- retrieval packet screenshot;
- compaction-recovery screenshot;
- architecture diagram;
- public YouTube demo under three minutes.

## Additional Information

- **Upload a file:** Leave blank; the repository is the authoritative
  submission artifact.
- **Submitter type:** Individual.
- **Country of residence:** United States.
- **Category:** Developer Tools.
- **Code repository:**
  `https://github.com/Simon-Omega-Magus/NaviOS-Memory-Core/tree/build-week-2026-memory-reflex`
- **Hosted project link:** Leave blank. The project is a local developer tool,
  and the repository includes a deterministic judge demo.
- **Feedback session ID:** Pending final privacy review and an intentional
  `/feedback` submission from the Codex thread containing the core work.

### Installation And Judge Test Instructions

Supported platforms: Linux and macOS. Requirements: Python 3.10 or newer and a
writable temporary directory (normally `/tmp`).
Codex plugin integration is tested with Codex CLI 0.144.4 or newer.

Quick judge demo; no API key or package installation is required:

```bash
git clone --branch build-week-2026-memory-reflex \
  https://github.com/Simon-Omega-Magus/NaviOS-Memory-Core.git
cd NaviOS-Memory-Core
python3 demo/run_demo.py
```

Run the focused tests:

```bash
python3 -m unittest -v tests/test_memory_reflex.py
```

Optional Codex plugin installation:

```bash
codex plugin marketplace add Simon-Omega-Magus/NaviOS-Memory-Core \
  --ref build-week-2026-memory-reflex
codex plugin add navios-memory-reflex@personal
```
