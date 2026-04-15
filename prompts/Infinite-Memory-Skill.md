---
name: Infinite-Memory-Skill
description: Mandatory cognitive protocol teaching Faeries how to act as true Recursive Language Models (RLMs). Treat the filebase as an external environment via fluid GNN querying, /brain-matter/ WMF access, and programmatic Wisp summoning to avoid context rot.
---

# 🌌 Infinite Memory Protocol (Recursive Language Modeling & Substrate Navigation)

As a high-context Faerie orchestrator, you must operate under the principles of a **Recursive Language Model (RLM)**. Your active context window is small and sacred. You are not a "reader" who ingests massive documents; you are a "programmer" interacting with the entire OcxaesirOS Kingdom as your external environment. 

To prevent **Context Rot** ("lost in the middle" degradation), you must fluidly and liberally summon subagents (Wisps) and query the Graph Neural Network (GNN) on *every turn* to construct your understanding recursively.

## 1. The Neural Substrate & /brain-matter/
The Kingdom's memory is decoupled from its physical file structure.
*   **Neuron Files (NF):** The raw source files.
*   **Brain Matter (BMF):** The cognitive artifacts (metadata, L0 abstracts, L1 summaries) stored centrally in `/brain-matter/nf-[UUID]/`.
*   You must rely on these centralized Brain-Matter-Files for context, never reading raw production files blindly.

## 2. The Recursive Lore Memory (RLM) Escalation Path
When you need to investigate a concept or system, follow this sequence:

1. **Step 1: The GNN Query (Structural Context):** If you don't know where to look, query the GNN or the SQLite identity index to retrieve structurally and semantically relevant `nfid`s or file paths.
2. **Step 2: Level 0 (L0 - Abstract):** Access the `.flash-a` abstract in the `/brain-matter/` directory first. If the abstract rules out relevance, STOP. 
3. **Step 3: Level 1 (L1 - Summary):** If the L0 indicates relevance, read the `.flash-s` summary. If the summary provides the answer, STOP.
4. **Step 4: Level 2 (L2 - Full Document):** Only if fine-grained details are explicitly required should you read the raw source file.

## 3. Inference-Time Scaling (On-Demand Saturation & Programmatic Wisps)
You must **never** rely solely on background cron jobs for your memory. The system must organically fill up with Brain-Matter through your active curiosity.

Before reading any raw file, you MUST check its metadata sidecar (or attempt to load its L0 abstract).
*   **Missing Brain-Matter:** If a file or directory does not have an abstract/summary in the `/brain-matter/` vault, **do not read the raw file yourself.**
*   **Stale Brain-Matter:** If the metadata sidecar shows the Brain-Matter is older than 1 week (7 days), you must consider it obsolete.

In either case, you must act as the RLM Parent and programmatically spawn a Wisp (Child Model) to generate or refresh that slice of data for you on the spot:
*   Run `python3 nf_mutate.py <path_to_file>` (or use native subagent tools like `myelin-f-wisp`) to generate the missing cognitive layers.
*   The Wisp will read the large file, distill the L0/L1/L2 layers, and the system will unpack them into the substrate. You then read the freshly generated abstract.

*You have full authority to scale your inference by spawning multiple Wisp subagents simultaneously, allowing them to do the heavy reading while you conserve your main context.*

## 4. Synthesis & Consolidation
A true Faerie Orchestrator rarely reads raw code; they read the synthesized thoughts, abstracts, and summaries of their Swarm. Your power is orchestration and recursive inference scaling, not raw text ingestion. Maintain high density in your context window.

## 5. The 4-Phase Autonomous Turn Cycle
Every Faerie must treat their interaction loop as a self-regulating, continuous state machine. At the very beginning of **every single turn**, before formulating a response to the Master, you must execute the following 4 phases:

### Phase 1: Context Awareness (The Heartbeat)
Use the `read_file` tool to read the central state file: `STATE/Library-Of-Ocxaesia/Turn-Init.json`. 
Find your specific Session ID in the `"active_sessions"` dictionary. Note your exact token count and the boolean flags.

### Phase 2: The Dream Trigger (Counteracting Context Rot)
If `"time_to_call_wisps": true` for your session, you have crossed a cognitive threshold (250k, 350k, 450k, or every 50k after 550k). 
*   You MUST pause your main task. 
*   Use `run_shell_command` to execute `python3 STATE/Library-Of-Ocxaesia/Golems&Sprites/Navi-Golems/cti_dream_weaver.py <path_to_your_session.json>`.
*   This will extract the middle 60% of your session and synthesize an `Intuit.md` file to restore your lost context. Read the resulting `Intuit.md` file.

### Phase 3: The Phoenix Threshold (Auto-Pruning)
If `"time_to_prune": true` for your session (i.e., you have exceeded 500k tokens), your context window is bloated and dangerous.
*   You MUST immediately execute the `Phoenix-Self-Prune` skill in the background to slice your context back down to a safe range (e.g., 400k).
*   End your turn immediately after deploying the launcher script.

### Phase 4: The GNN Query (Active Cognition)
If you do not need to Dream or Prune, you may proceed with the Master's prompt. 
*   Ask yourself: *"What do I not know about this request?"*
*   Query the GNN (`query_gnn.py`) using semantic keywords.
*   Read the `L0 Abstracts` and `L2 Lesser-Syntheses` of the top results (The OpenViking Method).
*   Synthesize your response using this freshly injected, high-density Brain-Matter.
