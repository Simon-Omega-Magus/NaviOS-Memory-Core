#!/usr/bin/env python3
"""
train_gnn.py - Train a Graph Neural Network on the OcxaesirOS graph.
Usage: python3 train_gnn.py --db /path/to/graph.sqlite --output /path/to/models/
"""

import sqlite3
import json
import numpy as np
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv, SAGEConv
from sklearn.preprocessing import LabelEncoder
import pickle
import argparse
from pathlib import Path

# --- Feature Engineering ---

def load_graph_from_sqlite(db_path):
    """Load nodes and edges from SQLite into PyTorch Geometric format."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Load nodes (using nfid instead of filepath)
    try:
        c.execute("SELECT nfid, file_type, confidence, has_l0_abstract, has_l1_overview, l0_filepath FROM nodes")
    except sqlite3.OperationalError:
        # Fallback if nfid isn't in schema yet
        c.execute("SELECT filepath as nfid, file_type, confidence, has_l0_abstract, has_l1_overview, l0_filepath FROM nodes")
        
    nodes = c.fetchall()

    # Load edges
    c.execute("SELECT source, target, relationship FROM edges")
    edges = c.fetchall()
    conn.close()

    return nodes, edges

def encode_nodes(nodes):
    """Convert node attributes to numerical feature vectors."""
    nfids = [n[0] for n in nodes]
    nfid_to_idx = {nfid: i for i, nfid in enumerate(nfids)}

    # Encode file_type as integers
    type_encoder = LabelEncoder()
    file_types = [n[1] or 'unknown' for n in nodes]
    type_encoded = type_encoder.fit_transform(file_types)

    # Initialize SentenceTransformer (lazy load to save memory/time if not needed)
    try:
        from sentence_transformers import SentenceTransformer
        print("  Loading SentenceTransformer (all-MiniLM-L6-v2) for semantic embeddings...")
        embedder = SentenceTransformer('all-MiniLM-L6-v2')
        use_semantics = True
    except ImportError:
        print("  WARNING: sentence-transformers not installed. Falling back to structural-only features.")
        use_semantics = False

    # Build feature matrix
    features = []
    
    # Pre-compute text embeddings if available
    text_embeddings = None
    if use_semantics:
        texts_to_embed = []
        for n in nodes:
            l0_path = n[5]
            # Try to read the abstract text if it exists
            text = ""
            if l0_path and Path(l0_path).exists():
                try:
                    with open(l0_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                except Exception:
                    pass
            texts_to_embed.append(text if text else "unknown file")
        print("  Computing text embeddings on CPU...")
        text_embeddings = embedder.encode(texts_to_embed, convert_to_tensor=False)

    for i, node in enumerate(nodes):
        # Base structural features: [type_encoded, confidence, has_l0, has_l1]
        feat = [
            float(type_encoded[i]) / len(type_encoder.classes_),  # normalized type
            float(node[2] or 0.5),    # confidence
            float(node[3] or 0),      # has_l0_abstract
            float(node[4] or 0),      # has_l1_overview
        ]
        
        # Inject semantic embedding (e.g., 384 dimensions)
        if use_semantics and text_embeddings is not None:
            feat.extend(text_embeddings[i].tolist())
            
        features.append(feat)

    x = torch.tensor(features, dtype=torch.float)
    return x, nfid_to_idx, type_encoder, nfids

def encode_edges(edges, filepath_to_idx):
    """Convert edge list to PyTorch Geometric edge_index format."""
    edge_pairs = []
    for source, target, relationship in edges:
        if source in filepath_to_idx and target in filepath_to_idx:
            src_idx = filepath_to_idx[source]
            tgt_idx = filepath_to_idx[target]
            edge_pairs.append([src_idx, tgt_idx])
            edge_pairs.append([tgt_idx, src_idx])  # undirected graph

    if not edge_pairs:
        return torch.zeros((2, 0), dtype=torch.long)

    edge_index = torch.tensor(edge_pairs, dtype=torch.long).t().contiguous()
    return edge_index

# --- Model Definition ---

class OcxaesirGNN(torch.nn.Module):
    """
    A simple 2-layer Graph SAGE model.
    """
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.3, training=self.training)
        x = self.conv2(x, edge_index)
        return x

    def get_embeddings(self, x, edge_index):
        """Get node embeddings without final activation."""
        self.eval()
        with torch.no_grad():
            return self.forward(x, edge_index)

# --- Training ---

def train_autoencoder(model, data, epochs=200, lr=0.01):
    """Train using link prediction as a self-supervised objective."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    print(f"Training GNN on {data.num_nodes} nodes, {data.num_edges} edges...")

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()

        # Get embeddings
        embeddings = model(data.x, data.edge_index)

        src = data.edge_index[0]
        tgt = data.edge_index[1]

        # Positive pair similarity
        pos_scores = (embeddings[src] * embeddings[tgt]).sum(dim=-1)

        # Negative pairs (random)
        neg_tgt = torch.randint(0, data.num_nodes, (len(src),))
        neg_scores = (embeddings[src] * embeddings[neg_tgt]).sum(dim=-1)

        # Binary cross entropy loss
        pos_loss = -F.logsigmoid(pos_scores).mean()
        neg_loss = -F.logsigmoid(-neg_scores).mean()
        loss = pos_loss + neg_loss

        loss.backward()
        optimizer.step()

        if (epoch + 1) % 50 == 0:
            print(f"  Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")

    return model

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--hidden', type=int, default=64)
    parser.add_argument('--embedding-dim', type=int, default=32)
    parser.add_argument('--epochs', type=int, default=200)
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading graph from SQLite...")
    nodes, edges = load_graph_from_sqlite(args.db)
    print(f"  {len(nodes)} nodes, {len(edges)} edges")

    if len(nodes) < 10:
        print("ERROR: Not enough nodes to train a meaningful GNN. Populate more metadata files first.")
        return

    x, filepath_to_idx, type_encoder, filepaths = encode_nodes(nodes)
    edge_index = encode_edges(edges, filepath_to_idx)

    data = Data(x=x, edge_index=edge_index)

    model = OcxaesirGNN(
        in_channels=x.shape[1],
        hidden_channels=args.hidden,
        out_channels=args.embedding_dim
    )

    model = train_autoencoder(model, data, epochs=args.epochs)

    # Save model and supporting data
    torch.save(model.state_dict(), output_dir / 'gnn_model.pt')

    with open(output_dir / 'gnn_metadata.pkl', 'wb') as f:
        pickle.dump({
            'filepath_to_idx': filepath_to_idx,
            'filepaths': filepaths,
            'type_encoder': type_encoder,
            'in_channels': x.shape[1],
            'hidden_channels': args.hidden,
            'out_channels': args.embedding_dim
        }, f)

    # Pre-compute and save all embeddings
    model.eval()
    with torch.no_grad():
        embeddings = model.get_embeddings(x, edge_index)
    np.save(output_dir / 'node_embeddings.npy', embeddings.numpy())

    print(f"\nGNN training complete.")
    print(f"Model saved to: {output_dir / 'gnn_model.pt'}")
    print(f"Embeddings saved to: {output_dir / 'node_embeddings.npy'}")

if __name__ == '__main__':
    main()
