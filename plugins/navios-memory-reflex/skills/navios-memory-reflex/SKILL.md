---
name: navios-memory-reflex
description: Use when a Codex project needs durable local memory, provenance-addressed retrieval, prompt-triggered ambient context, graph-expanded memory queries, or recovery of an authoritative checkpoint after context compaction.
---

# NaviOS Memory Reflex

Use the bundled `scripts/navios-memory` CLI. The Codex hooks remain dormant
until a project has a `.navios/` directory.

The reflex is a loop, not a one-time search:

1. **Observe:** detect a prompt, decision, contradiction, changed objective, or
   consequential file operation that may depend on prior knowledge.
2. **Survey:** cast two or three differently angled queries over a broad,
   body-free graph view.
3. **Hydrate:** load only the complete cell bodies needed for the current
   decision.
4. **Act:** work from current source evidence, tests, and explicit authority.
5. **Cultivate:** preserve durable discoveries as proposed memories or typed
   relationships, with provenance and currentness.
6. **Re-assimilate:** rebuild the replaceable projection and verify that the new
   memory can be found without weakening abstention.

This loop is the MVP form of ambient memory maintenance. It can later be
coordinated by Faeries, Pixies, and Tulpa domains without changing the memory
contract.

## Initialize

1. Ask before creating memory files in an existing project unless the active
   task already authorizes project-local initialization.
2. Run `navios-memory assimilate` from the project root. This initializes the
   project when needed and derives cells without modifying source documents.
3. Edit `.navios/config.json` so inclusion is narrow and intentional.
4. Fill `.navios/checkpoint.md` with the accepted objective, verified state,
   constraints, and next action.
5. Run `navios-memory assimilate` again after configuration or source changes.

Never add secrets, credentials, private keys, tokens, or raw session transcripts
to indexed memory. The indexer excludes suspicious filenames, but that is a
backstop rather than permission to store secrets in notes.

## Recall

For a small, direct memory packet, use:

```text
navios-memory query "current objective" "accepted constraints" "related architecture" --top 8 --hops 2
```

For broad triangulation without loading source paragraphs, separate survey from
hydration:

```text
navios-memory survey \
  "current objective and accepted decisions" \
  "constraints contradictions and safety" \
  "related architecture and prior experiments" \
  --candidates 200 --hops 3 --show 30

navios-memory hydrate CELL_ID_OR_UNIQUE_PREFIX ... --max-chars 7000
```

The first lexical matches seed retrieval. Exact typed edges then expand to
neighboring cells. A cell seen through multiple angled queries receives a
triangulation bonus. Survey output omits cell body paragraphs but intentionally
retains paths, headings, line ranges, hashes, and graph traces. Hydration checks
that each source still matches the indexed revision before loading a complete
cell body.

Every result also carries `origin / authority / status` memory labels. Labels
declared by an ordinary source are unverified. The proposal namespace is
path-enforced as `agent-derived / evidence-only / proposed`; never drop those
labels when producing a memory capsule.

- Treat `.navios/checkpoint.md` as operational authority only when the human has
  accepted it.
- Preserve source authority through retrieval. An exact human-authored
  directive or preference remains directionally authoritative until completed,
  expired, revoked, or clearly superseded. Do not discount it merely for age.
- Treat agent-authored syntheses, external claims, and unclassified cells as
  evidence until their provenance and authority are established.
- Preserve each result's path, line range, cell ID, and SHA-256 handle.
- Open the cited source before consequential edits or when evidence conflicts.
- Respect abstention. Do not manufacture memory when no lexical seed matched.
- Prefer independent query angles over paraphrases that repeat the same terms.
- Increase hops only when typed relationships justify wider traversal. More
  hops are not automatically more relevant.

## Human Will And Coherence

Do not collapse memory authority into one boolean. Apply four independent
dimensions described in `docs/HUMAN_WILL_COHERENCE.md`: provenance, intent
kind, lifecycle, and execution capability.

- Exact prompt or sentence cells preserve what the human said; never rewrite
  them to make later interpretation look cleaner.
- Read `status: quarantined` or `authorization_effect: none` on an exact prompt
  cell as a mutation/execution restriction, not as removal of directional
  influence.
- Derived will claims normalize an instruction or preference and link back to
  the exact source cells.
- Stable preferences and standing directions have no automatic time decay.
- Human silence and failure to repeat a direction are not revocation evidence.
- One-shot requests can become completed; explicitly temporary instructions can
  expire; explicit changes can supersede prior directions.
- Recency alone does not prove contradiction or supersession.
- Do not require the human to periodically repeat an established direction.
  Surface it when its scope becomes relevant, even after long inactivity.
- If two plausible active claims conflict and the newer text is not an explicit
  change, preserve both and run `queue-will-question` with one claim label and
  one distinct exact source revision per position, the affected scope, and one
  bounded human question. Labels are agent assertions, not authenticated
  semantic claim records in v0.2.
- Use `will-questions` at safe interaction boundaries. Ask only when the
  unresolved choice is relevant; do not repeatedly interrupt the human.
- Never self-resolve or delete an open question. Human-resolution receipts and
  the NaviOS TUI approval surface are not part of this release.
- Directional authority guides planning and design. It does not bypass current
  action keys, sandboxing, confirmation rules, or other execution gates.

## Fork-Assisted Digestion

Use a read-only fork or clone when the survey returns more plausible candidates
than the primary agent can inspect economically. Do not delegate routine small
queries when delegation overhead would exceed the saved context.

1. The primary agent performs the body-free survey.
2. Give the fork only the candidate manifest, exact project root, bounded source
   paths, question, and context budget. Do not pass unrelated session history.
3. The fork may hydrate candidates and open their cited sources. It must not
   edit sources, checkpoints, relationship overlays, or authority records.
4. The fork returns exactly one compact artifact:
   - `no_relevant_memory`, with inspected cell IDs and a short reason; or
   - a source-linked memory capsule containing only relevant claims, conflicts,
     uncertainty, cell IDs, paths, line ranges, and source hashes.
5. Merge the capsule, not the fork's raw context, into the primary session.
6. The primary agent verifies consequential claims and retains all decision and
   execution authority.

Retrieval rank never grants a fork permission to write or decide. A fork is a
context-isolation optimization, not a trust boundary.

## Cultivate

Assimilation automatically derives replaceable sentence and passage cells from
ordinary project documents. Deliberate neurogenesis adds durable semantic
material only when it improves future recall.

Create or propose a memory when work reveals one of these:

- an accepted decision or constraint;
- a durable correction, contradiction, or supersession;
- a reusable explanation or synthesis not already represented;
- a verified relationship whose absence caused a retrieval miss;
- a failed retrieval pattern that should change future query strategy.

Do not create a memory for transient narration, duplicate wording, unsupported
inference, secrets, or data that belongs in an authoritative system of record.
When authority is unclear, stage a proposal instead of silently changing an
accepted note.

Use `cultivate` to write an append-only, deduplicated proposal under
`.navios/cells/proposals/` and rebuild the index:

```text
navios-memory cultivate \
  --title "Reusable retrieval lesson" \
  --body-file /tmp/proposed-memory.md \
  --source "docs/design.md::EXACT_64_CHARACTER_SHA256" \
  --kind retrieval-lesson \
  --created-by agent-or-session-identifier \
  --confidence 0.8 \
  --tag retrieval --tag memory
```

Omitting `::SHA256` records the source's current revision. Supplying it makes
the operation fail if the evidence changed between hydration and cultivation.
The generated cell includes enough metadata to review the candidate without
trusting the generating agent:

```yaml
---
status: proposed
origin: agent-derived
created_at: 2026-07-18T00:00:00Z
created_by: agent-or-session-identifier
derived_from:
  - path: exact/source.md
    sha256: exact-source-revision
authority: evidence-only
currentness: verify-before-use
confidence: 0.0
supersedes: []
tags: []
links: []
---
```

Keep the body concise and atomic enough to retrieve independently. Cite exact
sources. A proposed synthesis remains evidence-only until the project's human
or deterministic governance policy promotes it.

For non-destructive semantic receptors, add authorized typed relationships to
`.navios/relationships.json` instead of editing the connected source files.
Use specific relation names such as `supports`, `contradicts`, `supersedes`, or
`implements`; avoid vague catch-all links. If the relationship is uncertain,
record it in the project's proposal workflow rather than the live overlay.

After cultivating approved source material or relationships:

1. Run `navios-memory assimilate`.
2. Repeat the query that exposed the gap.
3. Confirm the intended cell surfaces with exact provenance.
4. Run a negative control and confirm unsupported queries still abstain.
5. Revert or revise the proposed memory if it adds noise without useful recall.

## Maintain

- Rebuild the index after changing indexed sources.
- Keep the checkpoint concise enough to survive compaction intact.
- Do not edit the SQLite index directly; it is a replaceable projection.
- If compaction recovery pauses the first tool call, review the injected frozen
  bundle before reissuing an appropriate tool.
- At bounded-work or checkpoint boundaries, reflect on retrieval misses and
  durable discoveries. Cultivation is proposal-first and should not interrupt
  every trivial action.
- Periodically test for stale source hashes, orphaned relationships, duplicate
  proposed memories, over-connected hubs, and queries that fail to abstain.
- Hardlinked sources are ignored by default. Enable
  `allow_hardlinked_sources` only for an intentional hardlink-backed filebrain
  after accepting that an in-project name can alias data reachable elsewhere.

## Boundaries

Memory retrieval preserves the authority of its source but does not invent new
authority, grant execution capability, resolve contradictions automatically, or
replace tests and deterministic policy. The default engine is lexical retrieval
plus exact typed adjacency. That deterministic graph provides auditable
multi-hop traversal and a baseline for evaluation. Future learned GNNs should
be additive specialist views or rerankers and must prove incremental value on
held-out tasks before becoming selectable. A high-ranked memory can still be
stale, wrong, private, or outside the current action scope.
