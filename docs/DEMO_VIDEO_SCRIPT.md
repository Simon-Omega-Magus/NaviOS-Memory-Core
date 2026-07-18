# Build Week Demo Video Script

Target runtime: 2 minutes 45 seconds. Hard limit: under 3 minutes.

## Recording Setup

- Record at 1920x1080 or 1600x900.
- Use a terminal font large enough to read at normal YouTube playback size.
- Start from a clean clone of `build-week-2026-memory-reflex`.
- Keep narration natural; do not read command output line by line.
- Show the repository URL and branch at the end.

## Script And Shots

### 0:00-0:18 - Problem

**Visual:** Project thumbnail, then architecture visual.

**Narration:**

> Coding agents can solve difficult problems and still lose critical intent
> when their context is compacted. A transcript preserves chronology, but it
> does not automatically surface the right decision when that decision matters.
> NaviOS Memory Reflex adds a small, local memory layer to Codex.

### 0:18-0:43 - Staged Graph Retrieval

**Visual:** Highlight the upper architecture loop.

**Narration:**

> Ordinary project notes are non-destructively indexed as sentence and passage
> cells with exact provenance. Several query angles produce a body-free survey
> of up to two hundred candidates each. Typed graph links expose nearby
> evidence, and only selected complete cells are hydrated after their live
> source revision is verified.

### 0:43-1:05 - Demo And Measurement

**Visual:** Terminal at the repository root.

```bash
python3 demo/run_demo.py
```

**Narration:**

> The deterministic demo indexes four synthetic documents into fourteen cells
> and thirty-eight typed edges. A separate two-hundred-forty-document benchmark
> surfaces all four required memories, including one graph-only result, abstains
> on the negative control, and uses about ninety-two percent less body context
> with selective hydration.

### 1:05-1:27 - Cultivation And Human Will

**Visual:** Scroll to `PROPOSAL-FIRST MEMORY CULTIVATION`, then
`HUMAN-WILL COHERENCE QUEUE`.

**Narration:**

> Durable lessons are added as append-only, provenance-bound proposals instead
> of rewriting accepted notes. The agent guidance rejects automatic age decay,
> and the queue binds each agent-supplied claim label to one exact live source
> revision with no execution effect. Trusted prompt capture and semantic conflict
> detection remain future work.

### 1:27-1:52 - Compaction Recovery

**Visual:** Scroll to `COMPACTION RECOVERY`, then show the lower architecture
loop.

**Narration:**

> Before compaction, NaviOS freezes the accepted checkpoint and last evidence
> packet into a digest-locked bundle. Session Start or the next prompt restores
> it. If hook delivery arrives out of order, the first tool call is denied,
> receives the bundle, and must be reviewed and reissued.

### 1:52-2:17 - Safety And Tests

**Visual:** Run the focused suite.

```bash
python3 -m unittest -q \
  tests/test_memory_reflex.py tests/test_staged_benchmark.py
```

**Narration:**

> The release is local-first Python and SQLite. Raw prompts are represented in
> saved state only by a digest. Source changes, symlinks, hardlink policy,
> suspicious filenames, context limits, queue tampering, and hook ordering all
> fail closed. Forty-five focused tests pass without an API key.

### 2:17-2:41 - Codex And GPT-5.6

**Visual:** Show `docs/BUILD_WEEK_2026.md`, then the plugin manifest.

**Narration:**

> I used GPT-5.6 in Codex to audit an earlier Graph Sage research repository,
> reduce a broad cognitive-memory architecture to a reproducible product,
> implement and review the plugin, and investigate real hook-ordering failures.
> I supplied the long-term direction, privacy requirements, scope decisions,
> and final publication control.

### 2:41-2:50 - Close

**Visual:** Thumbnail plus public repository URL.

**Narration:**

> This is not an infinite-context claim. It is a working, inspectable memory
> reflex: relevant local evidence before work and authoritative recovery after
> compaction.

## Final On-Screen URL

```text
github.com/Simon-Omega-Magus/NaviOS-Memory-Core
branch: build-week-2026-memory-reflex
```

## Upload Checklist

- Public YouTube visibility.
- Runtime below 3:00.
- Audio clearly mentions Codex and GPT-5.6.
- Description links directly to the Build Week branch.
- No private terminal tabs, home paths, tokens, passwords, or unrelated files
  appear in frame.

## Synthetic Fallback Render

Linux systems with `ffmpeg`, `ffprobe`, and `espeak-ng` can render the included
fallback narration and slides with:

```bash
media/render-demo-video.sh /tmp/navios-memory-reflex-demo.mp4
```

The verified v0.2 fallback is 2 minutes 46.4 seconds. It is a mechanically
generated backup; natural narration over the same shot plan is preferable for
the final submission.
