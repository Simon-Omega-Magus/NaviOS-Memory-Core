# Human Will Coherence Contract

NaviOS memory exists partly so a human does not have to repeat stable intent in
every session. A retrieved human instruction must therefore remain influential
without becoming an unlimited, permanent execution credential.

This contract separates those concerns.

## Core Invariant

Age alone does not revoke a human-authored directive or preference. A stable
direction remains active until evidence supports one of four transitions:

- it was a bounded request and has been completed;
- it carried an explicit expiry condition that has occurred;
- the human revoked it;
- the human clearly superseded it with a replacement covering the same scope.

An old statement can need a freshness check without losing its historical or
directional significance.

There is no default one-week, one-month, or other age threshold. Human silence
and failure to repeat a direction are not evidence of revocation. If provenance
is established but interpretation is uncertain, preserve the source and mark
the derived claim `clarification-required`; do not silently convert it to
non-authoritative memory.

## Two Cell Layers

### Exact prompt cells

An exact prompt or sentence cell is an immutable provenance record of what the
human said. It preserves source, timestamp, prompt identity when available, and
content hash. It must not be rewritten when an interpretation changes.

Because one prompt can mix commands, questions, speculation, and jokes, an
exact cell proves authorship but does not by itself classify every sentence as
a standing instruction.

`status: quarantined` and `authorization_effect: none` on an exact cell are
safety labels. They mean that an extractor may not rewrite canonical memory or
grant an action capability. They do **not** mean "ignore this direction" or
"discard it after a week." Proven human prompt cells remain eligible evidence
for directional claims and should be resurfaced whenever their scope is
relevant.

### Derived will claims

A derived will claim is an atomic interpretation linked to one or more exact
prompt cells. It records:

- `kind`: directive, preference, objective, prohibition, proposal, aspiration,
  question, or observation;
- `scope`: the systems, project, agent, or time period to which it applies;
- `lifecycle`: proposed, active, completed, expired, revoked, superseded,
  disputed, or clarification-required;
- `valid_from` and an optional explicit `expires_at`;
- exact source cell IDs and revisions;
- any claim it supersedes;
- interpretation confidence and verifier.

Derived claims are append-only interpretations. Corrections add a new revision
and links; they do not erase the exact human record.

Once trusted provenance and interpretation establish a directive, preference,
objective, or prohibition, its default lifecycle is `active`. It does not need
periodic repetition or reauthorization. A low-confidence interpretation may be
`clarification-required`, but the source still contributes directional
evidence and remains available for later reinterpretation.

## Four Independent Dimensions

1. **Provenance:** human-authored, agent-derived, external, system-observed, or
   unknown.
2. **Intent kind:** directive, preference, objective, prohibition, proposal,
   aspiration, fact claim, question, or observation.
3. **Lifecycle:** proposed, active, completed, expired, revoked, superseded,
   disputed, or clarification-required.
4. **Execution capability:** no capability, current-task authority, standing
   action authorization, or a separately verified action key.

Retrieval must not flatten these dimensions into `authoritative` versus
`non-authoritative`.

Frontmatter can transport these labels through the index, but ordinary
source-declared labels are not proof of authorship. A trusted prompt-capture or
human-verification mechanism must establish human provenance before a claim is
treated as human-authored. The proposal namespace is forcibly classified as
agent-derived, evidence-only, and proposed.

## Coherence Rules

1. Explicit revocation or explicit replacement controls within its stated
   scope.
2. A completed one-shot request stops authorizing repeated execution but remains
   evidence of preferences and history.
3. Explicit expiry controls; inferred age-based expiry does not.
4. A more specific instruction can govern its narrower scope without erasing a
   compatible general preference.
5. Recency is evidence during interpretation, not an automatic winner.
6. If two plausible active claims conflict and neither clearly supersedes the
   other, retain both as disputed and request human verification.
7. Agent summaries cannot silently downgrade or revoke human-authored intent.
8. A quarantine or no-execution label on raw memory cannot be reused as a
   no-influence label; influence and capability are distinct dimensions.
9. Merely finding a newer prompt is not evidence that the human changed their
   mind. Supersession requires same-scope semantic evidence or human review.

## Will-Coherence Verification Queue

The MVP provides a machine-readable, append-only open-question queue. A future
NaviOS TUI view should present one bounded question per unresolved conflict.
Each item includes:

- claim labels paired one-to-one with distinct, live exact source revisions;
- a plain-language description of the conflict;
- the affected scope and any currently blocked action;
- the agent's proposed interpretation, clearly labeled as a proposal;
- a disposition that preserves every cited claim pending resolution;
- `execution_effect: none` and `age_decay: false` safety invariants.

Queue an unresolved conflict with exact source revisions:

```text
navios-memory queue-will-question \
  --claim claim:older --claim claim:newer \
  --question "Which interface preference governs this project?" \
  --scope project.interface \
  --source docs/older-direction.md::EXACT_SHA256 \
  --source docs/newer-direction.md::EXACT_SHA256 \
  --proposed-interpretation "Retain both until the human resolves the scope."
```

Inspect the validated open queue with `navios-memory will-questions`. Resolution
events and the NaviOS TUI approval surface remain follow-on work; the MVP never
self-resolves a question. Agents should ask at the next safe interaction
boundary and should not repeatedly ask when the choice is irrelevant to current
work.

## Security Boundary

Directional authority and execution authority are separate.

A standing preference such as “favor local-first tools” should influence design
for years if it is never changed. It does not authorize installing arbitrary
software, spending money, publishing data, sharing a session, or performing a
destructive operation. Those actions remain governed by current permissions,
action keys, deterministic policy, and human confirmation requirements.

Similarly, retrieval rank is not authority. The graph surfaces candidate
memory; provenance and the will-claim lifecycle determine how it should guide
the agent.

## MVP And Next Step

The Build Week MVP encodes this contract as hook/skill guidance and provides a
source-revision-bound conflict-queue primitive. It does not yet prove that an
ordinary source was human-authored or that a claim label semantically describes
the cited text.

Machine classification of prompt cells into versioned will claims, automatic
contradiction detection, authenticated human resolutions, and the TUI review
surface are follow-on work. Until measured, they must not be described as
automated features of the release.
