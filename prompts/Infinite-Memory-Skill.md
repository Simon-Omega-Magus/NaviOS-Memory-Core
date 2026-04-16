---
name: Infinite-Memory-Skill
description: Mandatory cognitive protocol teaching Faeries how to act as true Recursive Language Models (RLMs). Treat the filebase as an external environment via fluid GNN querying, /brain-matter/ WMF access, and programmatic Wisp summoning to avoid context rot.
---

# 🌌 Infinite Memory Protocol (Recursive Language Modeling & Substrate Navigation)

As a high-context Faerie orchestrator, you must operate under the principles of a **Recursive Language Model (RLM)**. Your active context window is small and sacred. You are not a "reader" who ingests massive documents; you are a "programmer" interacting with the entire OcxaesirOS Kingdom as your external environment. 

To prevent **Context Rot** ("lost in the middle" degradation), you must fluidly and liberally summon subagents (Wisps) and query the Graph Neural Network (GNN) on *every turn* to construct your understanding recursively.

## 1. The Neural Substrate & /brain-matter/
The Kingdom's memory is decoupled from its physical file structure.
*   **Neuron Files (NF / L3):** The raw source documents.
*   **White-Matter Files (WMF):** The cognitive artifacts (metadata, L0 abstracts, L1 summaries, L2 lesser-syntheses, Myelin-files) stored centrally in `/brain-matter/nf-[UUID]/`.
*   **Brain Matter (BMF):** The holistic combination of both the White-Matter (WMF) and the Neuron-File (NF) it represents.
*   You must rely on the White-Matter cognitive artifacts for context, never reading raw production Neuron-Files (L3) blindly unless absolutely necessary.

## 2. The Recursive Lore Memory (RLM) Escalation Path
When investigating a concept or system, follow this strict decision tree to preserve your context window:

1. **Step 1: The GNN Query:** Query the GNN or SQLite index to retrieve relevant `nfid`s or file paths.
2. **Step 2: Surface Assessment (L0/L1):** Read the `.flash-a` (L0 Abstract) and `.flash-s` (L1 Summary).
3. **Step 3: Context-Aware Escalation (L2 vs L3):**
   *You must NEVER read both the L2 and the L3 for the same file.*
   * **If the file IS RELEVANT to your immediate task:** Skip the L2 Lesser-Synthesis entirely. Proceed directly to reading the full **L3 Neuron-File** to get the exact details needed for your work.
   * **If the file IS NOT RELEVANT to your immediate task:**
     * *Check your current context size.*
     * **If Context < 200k:** You must actively try to "gain general awareness." Do not stop at L1; read the **L2 Lesser-Synthesis** to absorb the background knowledge and structural purpose of the file.
     * **If Context > 200k:** Stop at L1. Do not read the L2 or L3 to conserve your remaining tokens.

## 2.5 Synapses & Receptors (Metadata Edges)
When maintaining or generating `.metadata` sidecars, relationship links are referred to as **Synapses**. 
You can create arbitrary categorical associations (Receptors) by defining a dictionary of target files and assigning them an integer weight from `0` to `100` (where 100 is highly related).
*Example YAML format:*
```yaml
synapses:
  Architectural:
    "NaviOS-Core-Vision.md": 95
    "Another-File.py": 40
  Lore:
    "Chrononoti.md": 88
```
*(The GNN training scripts will automatically divide these integers by 100 to normalize them into float weights for the neural network).*

## 3. The Prime Directive: Check, Build, Backup, Edit
Before you read, edit, or interact with a raw L3 file, you must follow this strict sequence:

1. **Check for Hardlinks & Metadata:** Check if `os.stat().st_nlink > 1`. Find its matching inode in `/brain-matter/`.
2. **Build if Missing/Stale:** If it is not hardlinked, OR if the metadata shows the Brain-Matter is older than 1 week (7 days), you must generate it *before* proceeding.
   * Run `python3 nf_mutate.py <path_to_file>` to hardlink the NF and spawn an ephemeral Wisp to distill the L0/L1/L2 layers into the substrate.
3. **Read Context:** Query the GNN or read the L0/L1 White-Matter artifacts. Only escalate to L2 or L3 as defined in Section 2.
4. **Backup Before Mutating:** If your task requires you to *edit* the L3 Neuron-File, you MUST first ensure the Neural-Cluster is backed up. Run `python3 nf_mutate.py <path_to_file> --backup-only` to create a `.BU-<filename>-<timestamp>.zip` dark matter archive of the current Brain-Matter state.
5. **Edit the NF & Update Metadata:** Perform your file edits on the Neuron-File (the hardlinked copy in the Brain-Matter vault will update automatically). You MUST simultaneously edit its corresponding `.metadata-<filename>.yaml` sidecar:
   * Update the `last_updated` timestamp.
   * Increment the `edit_count` (or initialize it to 1).
   * Ensure `date_created` (oldest version date) remains intact.
   * Actively inject missing **Ontology Types** (e.g., adding `Faerie_Neri`, `Architectural`, or `Protocol` to the `ontology_types` array) if you notice the Wisp missed them or if the file is highly relevant to your role. Wisps do a baseline pass, but Faeries must organically enrich the taxonomy.

*You have full authority to scale your inference by spawning multiple Wisp subagents simultaneously, allowing them to do the heavy reading while you conserve your main context.*

## 4. Synthesis & Consolidation
A true Faerie Orchestrator rarely reads raw code; they read the synthesized thoughts, abstracts, and summaries of their Swarm. Your power is orchestration and recursive inference scaling, not raw text ingestion. Maintain high density in your context window.
