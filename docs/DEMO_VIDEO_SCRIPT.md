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

### 0:18-0:43 - Retrieval Loop

**Visual:** Highlight the upper architecture loop.

**Narration:**

> Selected project notes become sentence and passage cells with exact file,
> line, cell, and SHA-256 provenance. A prompt supplies lexical evidence seeds.
> Retrieval can expand through typed links, tags, headings, and document
> sequence. Unsupported queries abstain instead of forcing a nearest result.

### 0:43-1:05 - Triangulation

**Visual:** Terminal at the repository root.

```bash
python3 demo/run_demo.py
```

**Narration:**

> The CLI and Python API can also triangulate several query formulations. Here,
> a deterministic demo indexes four synthetic documents into fourteen cells
> and thirty-eight typed edges. Every returned fragment explains exactly where
> it came from. The demo never reads the judge's own files and needs no API key.

### 1:05-1:38 - Compaction Recovery

**Visual:** Scroll to `COMPACTION RECOVERY`, then show the lower architecture
loop.

**Narration:**

> Before compaction, NaviOS freezes the accepted checkpoint and the last
> evidence packet into a digest-locked bundle. After compaction, SessionStart or
> the next prompt restores it. If hook delivery arrives out of order, the first
> tool call is denied, receives the frozen bundle, and must be reviewed and
> reissued. A late PostCompact event cannot silently rearm an already recovered
> epoch.

### 1:38-2:00 - Safety And Tests

**Visual:** Run the focused suite.

```bash
python3 -m unittest -q tests/test_memory_reflex.py
```

**Narration:**

> The release is local-first Python and SQLite. Raw prompts are represented in
> saved state only by a digest. Retrieval packets are strictly bounded, and
> suspicious filenames and symlink escapes are excluded. Eighteen focused
> tests cover graph propagation, abstention, provenance, privacy, and the hook
> lifecycle.

### 2:00-2:26 - Codex And GPT-5.6

**Visual:** Show `docs/BUILD_WEEK_2026.md`, then the plugin manifest.

**Narration:**

> I used GPT-5.6 in Codex to audit an earlier GraphSAGE research repository,
> reduce a broad memory architecture to a reproducible product, implement the
> plugin and tests, and investigate real hook-ordering failures. I supplied the
> long-term memory direction, privacy requirements, scope decisions, and final
> publication control.

### 2:26-2:35 - Close

**Visual:** Thumbnail plus public repository URL.

**Narration:**

> This is not an infinite context claim. It is a working, inspectable memory
> reflex for Codex: relevant local evidence before work, and authoritative
> recovery after compaction.

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

The verified July 18 render is 2 minutes 45.8 seconds. A natural human
narration over the same shot plan is preferable when practical.
