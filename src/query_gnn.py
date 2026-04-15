#!/usr/bin/env python3
"""
query_gnn.py - Query the trained GNN to find related nodes using Endocrine CRS.
Usage: python3 query_gnn.py --query "path/to/file.md" --top 10 --models /path/to/models/ --db /path/to/graph.sqlite
"""

import os
import sqlite3
import numpy as np
import pickle
import argparse
import json
import datetime
from pathlib import Path

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

def resolve_query_to_nfid(db_path, query_str):
    if query_str.startswith('nf-') or query_str.startswith('cn-') or query_str.startswith('ca-'):
        return query_str
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT nfid FROM nodes WHERE filepath = ?", (query_str,))
    result = c.fetchone()
    if result:
        conn.close()
        return result[0]
    c.execute("SELECT nfid FROM nodes WHERE filename = ?", (query_str,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def resolve_nfid_to_filepath(db_path, nfid):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT filepath FROM nodes WHERE nfid = ?", (nfid,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else nfid

def load_node_metadata(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT nfid, date_updated FROM nodes")
    data = c.fetchall()
    conn.close()
    
    node_meta = {}
    now = datetime.datetime.now()
    for nfid, date_updated in data:
        recency = 1.0
        if date_updated:
            try:
                dt = datetime.datetime.fromisoformat(date_updated)
                days_old = (now - dt).days
                # Exponential decay for recency
                recency = max(0.1, np.exp(-0.05 * days_old))
            except Exception:
                pass
        node_meta[nfid] = {'recency': recency}
    return node_meta

def compute_crs(base_sim, nfid, node_meta, coherence_scores):
    # Base Semantic or Structural Similarity
    # CRS = Semantic_Similarity * (Arousal * Recency * Coherence * Novelty)
    
    arousal = 1.0  # Default to 1.0 for now
    novelty = 1.0  # Default to 1.0 for now
    
    recency = node_meta.get(nfid, {}).get('recency', 1.0)
    coherence = coherence_scores.get(nfid, 0.1)
    
    # Negative similarity might mess up the multiplier, so we cap base_sim at 0
    sim = max(0.0, base_sim)
    
    crs = sim * (arousal * recency * coherence * novelty)
    return crs, recency, coherence

def find_neighbors(query_nfid, embeddings, nfid_to_idx, nfids, node_meta, coherence_scores, top_k=10):
    if query_nfid not in nfid_to_idx:
        print(f"ERROR: Node not found in graph embeddings: {query_nfid}")
        return []

    query_idx = nfid_to_idx[query_nfid]
    query_embedding = embeddings[query_idx]

    scores = []
    for i, nfid in enumerate(nfids):
        if nfid == query_nfid:
            continue
        base_sim = cosine_similarity(query_embedding, embeddings[i])
        crs, recency, coherence = compute_crs(base_sim, nfid, node_meta, coherence_scores)
        scores.append((nfid, crs, base_sim, recency, coherence))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]

def get_semantic_embedding(query_str, embedder=None):
    try:
        if embedder is None:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        return embedder.encode([query_str])[0]
    except ImportError:
        print("ERROR: sentence-transformers is not installed. Semantic search disabled.")
        return None
    except Exception as e:
        print(f"ERROR: Failed to generate semantic embedding: {e}")
        return None

def find_semantic_neighbors(query_str, db_path, node_meta, coherence_scores, top_k=10, embedder=None):
    if embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            return []
            
    query_emb = get_semantic_embedding(query_str, embedder)
    if query_emb is None:
        return []
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT nfid, filepath, l0_filepath FROM nodes WHERE l0_filepath != ''")
    nodes = c.fetchall()
    conn.close()
    
    texts = []
    valid_nodes = []
    for node in nodes:
        try:
            with open(node[2], 'r') as f:
                texts.append(f.read())
            valid_nodes.append(node)
        except Exception:
            pass
            
    if not texts:
        return []
        
    node_embs = embedder.encode(texts)
    
    scores = []
    for i, node in enumerate(valid_nodes):
        nfid = node[0]
        base_sim = cosine_similarity(query_emb, node_embs[i])
        crs, recency, coherence = compute_crs(base_sim, nfid, node_meta, coherence_scores)
        scores.append((nfid, node[1], crs, base_sim, recency, coherence))
        
    scores.sort(key=lambda x: x[2], reverse=True)
    return [(n[0], n[1], n[2], n[3], n[4], n[5]) for n in scores[:top_k]]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True, help='Relative filepath, NFID, or raw semantic text to query')
    parser.add_argument('--top', type=int, default=10)
    parser.add_argument('--models', required=True, help='Path to models directory')
    parser.add_argument('--db', required=True, help='Path to graph.sqlite database')
    args = parser.parse_args()

    models_dir = Path(args.models)
    db_path = Path(args.db)

    # Load Coherence Scores (JEPA)
    coherence_scores_path = models_dir / "coherence_scores.json"
    coherence_scores = {}
    if coherence_scores_path.exists():
        with open(coherence_scores_path, 'r') as f:
            coherence_scores = json.load(f)

    # Load Node Metadata (Recency)
    node_meta = load_node_metadata(db_path)

    query_nfid = resolve_query_to_nfid(db_path, args.query)
    
    if query_nfid:
        print(f"\n[Structural Search] Resolving neighbors for: {args.query} ({query_nfid})")
        try:
            embeddings = np.load(models_dir / "node_embeddings.npy")
            with open(models_dir / "gnn_metadata.pkl", 'rb') as f:
                meta = pickle.load(f)
        except FileNotFoundError as e:
            print(f"Error loading models: {e}")
            return
            
        neighbors = find_neighbors(
            query_nfid, embeddings,
            meta['filepath_to_idx'], meta['filepaths'],
            node_meta, coherence_scores,
            top_k=args.top
        )
        
        if not neighbors:
            return
            
        print("-" * 120)
        print(f"{'CRS':<8} | {'Sim':<8} | {'Recency':<8} | {'Cohere':<8} | {'Filepath'}")
        print("-" * 120)
        for nfid, crs, sim, recency, coherence in neighbors:
            filepath = resolve_nfid_to_filepath(db_path, nfid)
            print(f"{crs:.4f}   | {sim:.4f}   | {recency:.4f}   | {coherence:.4f}   | {filepath}")
            
    else:
        print(f"\n[Semantic Search] Finding nodes related to concept: '{args.query}'")
        embedder = None
        try:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            print("ERROR: sentence-transformers not installed.")
        except Exception as e:
            print(f"ERROR loading sentence-transformers: {e}")
            
        neighbors = find_semantic_neighbors(args.query, db_path, node_meta, coherence_scores, top_k=args.top, embedder=embedder)
        
        if not neighbors:
            print("No semantic matches found. Make sure Brain-Matter files are saturated.")
            return
            
        print("-" * 120)
        print(f"{'CRS':<8} | {'Sim':<8} | {'Recency':<8} | {'Cohere':<8} | {'Filepath'}")
        print("-" * 120)
        for nfid, filepath, crs, sim, recency, coherence in neighbors:
            print(f"{crs:.4f}   | {sim:.4f}   | {recency:.4f}   | {coherence:.4f}   | {filepath}")

if __name__ == '__main__':
    main()