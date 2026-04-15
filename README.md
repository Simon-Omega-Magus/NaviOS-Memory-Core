# NaviOS-Memory-Core

NaviOS-Memory-Core is a revolutionary memory framework allowing LLM agents (like Gemini, Claude, or local models) to maintain infinite, semantic, and structural context across a massive codebase without ever exceeding token limits. 

It achieves this by converting a standard filesystem into a living **Graph Neural Network (GNN)**, powered by a Multi-Tiered Recursive Language Model (RLM) protocol. Instead of reading massive raw files, the AI agent is taught to query the GNN, read single-sentence Abstracts (L0), escalate to Summaries (L1), Syntheses (L2), and finally the raw file (L3) only if necessary.

## The Paradigm: On-Demand Saturation

You do not need to rely on heavy background cron jobs to saturate your filebase. The `Infinite-Memory-Skill` mandates that your AI acts proactively:
Before reading any raw file, the AI MUST check its metadata sidecar.
*   **Missing Brain-Matter:** If a file or directory does not have an abstract/summary, the AI will not read the raw file.
*   **Stale Brain-Matter:** If the Brain-Matter is older than 1 week (7 days), it is considered obsolete.

In either case, your AI will programmatically spawn a Wisp (Child Model) to generate or refresh that slice of data for you on the spot, creating a living, organically scaling brain.

## Features
- **On-the-Fly UUID Generation:** No need for intrusive initialization scripts. `nf_mutate.py` natively generates UUIDs and manages `.metadata` sidecars as you go.
- **Graph Neural Network Routing:** Transform your messy codebase into an elegant, deeply interconnected GNN using `build_graph.py` and `train_gnn.py`.
- **Semantic & Structural Search:** Your AI can use `query_gnn.py` to seamlessly navigate massive contexts without bloating its active window.

## Setup

1. **Install Requirements:**
   *(Note: Cloning a GitHub repository only downloads the raw code files. You must still install the external Python libraries that the code relies on, like PyTorch and NetworkX).*
   ```bash
   pip install -r requirements.txt
   ```

2. **Add Prompts:**
   Add the prompts in `prompts/` to your local agent configuration.

3. **Saturate:**
   Your AI is now equipped to scan, mutate, and build Brain-Matter on the fly using `src/nf_mutate.py`.

4. **Compile the Graph:**
   Once your Brain-Matter vault is populated, compile the GNN:
   ```bash
   python3 src/build_graph.py
   python3 src/train_gnn.py
   ```

5. **Query:**
   Your agents can now use `python3 src/query_gnn.py "search query"` to pull down the most relevant L0 Abstracts and navigate your codebase flawlessly.