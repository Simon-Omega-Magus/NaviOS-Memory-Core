#!/usr/bin/env python3
"""
build_graph.py - Full rebuild of OcxaesirOS Holographic Graph from Substrate metadata files.
Usage: python3 build_graph.py --root /path/to/OcxaesirOS --output /path/to/output/dir
"""

import os
import json
import sqlite3
import yaml
import argparse
from datetime import datetime
from pathlib import Path

def find_metadata_files(root_path):
    """Find all .metadata-*.yaml files recursively within the Brain-Matter vault."""
    metadata_files = []
    brain_matter_dir = os.path.join(root_path, "STATE", "Brain-Matter")
    if not os.path.exists(brain_matter_dir):
        print(f"Warning: Brain-Matter directory not found at {brain_matter_dir}")
        return metadata_files
        
    for dirpath, _, filenames in os.walk(brain_matter_dir):
        for filename in filenames:
            if filename.startswith('.metadata-') and filename.endswith('.yaml'):
                metadata_files.append(os.path.join(dirpath, filename))
    return metadata_files

def load_metadata(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 2:
                data = yaml.safe_load(parts[1])
            else:
                data = yaml.safe_load(content)
        else:
            data = yaml.safe_load(content)
        return data if data else {}
    except Exception as e:
        print(f"  WARNING: Could not parse {filepath}: {e}")
        return None

def metadata_to_node(data, relative_filepath, nfid):
    return {
        'nfid': nfid,
        'filepath': relative_filepath,
        'filename': data.get('filename', os.path.basename(relative_filepath)),
        'inode': data.get('inode'),
        'file_type': data.get('type', 'unknown'),
        'domains': json.dumps(data.get('domain', [])),
        'tags': json.dumps(data.get('tags', [])),
        'confidence': data.get('confidence', 0.7),
        'confidence_last_verified': data.get('confidence_last_verified', ''),
        'date_created': data.get('created_at', data.get('date_created', '')),
        'date_updated': data.get('last_updated', data.get('date_updated', '')),
        'generated_by': data.get('generated_by', 'unknown'),
        'has_l0_abstract': 1 if data.get('has_l0_abstract') else 0,
        'has_l1_overview': 1 if data.get('has_l1_overview') else 0,
        'l0_filepath': data.get('l0_filepath', ''),
        'status': data.get('status', 'active'),
        'metadata_json': json.dumps(data)
    }

def setup_database(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            nfid TEXT PRIMARY KEY,
            filepath TEXT,
            filename TEXT,
            inode INTEGER,
            file_type TEXT,
            domains TEXT,
            tags TEXT,
            confidence REAL,
            confidence_last_verified TEXT,
            date_created TEXT,
            date_updated TEXT,
            generated_by TEXT,
            has_l0_abstract INTEGER,
            has_l1_overview INTEGER,
            l0_filepath TEXT,
            status TEXT,
            metadata_json TEXT
        );
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            target TEXT,
            relationship TEXT,
            weight REAL,
            date_added TEXT,
            UNIQUE(source, target, relationship)
        );
        CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(file_type);
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
        CREATE INDEX IF NOT EXISTS idx_edges_relationship ON edges(relationship);
    """)
    conn.commit()
    return conn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    db_path = output / 'navios-graph.sqlite'
    jsonl_path = output / 'navios-edges.jsonl'
    date_str = datetime.now().strftime('%Y-%m-%d')

    print(f"Scanning for Brain-Matter metadata files in: {root}/Brain-Matter")
    metadata_files = find_metadata_files(root)
    print(f"Found {len(metadata_files)} metadata files")

    # Wipe existing DB for clean rebuild of the Holographic Graph
    if db_path.exists():
        db_path.unlink()

    conn = setup_database(db_path)
    c = conn.cursor()
    
    filepath_to_nfid = {}
    parsed_data = []

    print("Pass 1: Constructing Nodes and Identity Map...")
    for mf in metadata_files:
        data = load_metadata(mf)
        if not data:
            continue
            
        nfid = data.get('nfid')
        if not nfid:
            continue

        rel_path = data.get('original_path', '')
        if rel_path.startswith(str(root)):
            try:
                rel_path = str(Path(rel_path).relative_to(root))
            except ValueError:
                pass

        filepath_to_nfid[rel_path] = nfid
        filepath_to_nfid[os.path.basename(rel_path)] = nfid
        
        node = metadata_to_node(data, rel_path, nfid)
        c.execute("""
            INSERT OR REPLACE INTO nodes VALUES 
            (:nfid, :filepath, :filename, :inode, :file_type, :domains, :tags,
             :confidence, :confidence_last_verified, :date_created, :date_updated,
             :generated_by, :has_l0_abstract, :has_l1_overview, :l0_filepath,
             :status, :metadata_json)
        """, node)
        
        parsed_data.append((nfid, data, rel_path))

    all_edges = []
    nodes_by_domain = {}
    
    def resolve_target(tgt):
        if tgt.startswith('nf-'): return tgt
        return filepath_to_nfid.get(tgt, tgt)

    print("Pass 2: Weaving Holographic Edges...")
    for nfid, data, rel_path in parsed_data:
        
        # Domain clustering
        for domain in data.get('domain', []):
            if domain and domain != "unknown":
                nodes_by_domain.setdefault(domain, []).append(nfid)

        # Subjective & Explicit Links
        for key, value in data.items():
            if key == 'links' or key.startswith('links_'):
                rel_type = key if key.startswith('links_') else 'explicit_link'
                if isinstance(value, list):
                    for link in value:
                        tgt_nfid = resolve_target(link)
                        all_edges.append({
                            'source': nfid, 'target': tgt_nfid,
                            'relationship': rel_type, 'weight': 1.0, 'date_added': date_str
                        })

        # Hard link siblings
        for sibling in data.get('hard_link_siblings', []):
            tgt_nfid = resolve_target(sibling)
            all_edges.append({
                'source': nfid, 'target': tgt_nfid,
                'relationship': 'hard_link_sibling', 'weight': 1.0, 'date_added': date_str
            })

        # Fileset memberships
        for fileset in data.get('fileset_memberships', []):
            if fileset:
                all_edges.append({
                    'source': nfid, 'target': fileset,
                    'relationship': 'fileset_member', 'weight': 1.0, 'date_added': date_str
                })

    # Add domain sibling edges
    for domain, nfids in nodes_by_domain.items():
        if len(nfids) < 2: continue
        for i, nfid1 in enumerate(nfids):
            for nfid2 in nfids[i+1:]:
                all_edges.append({
                    'source': nfid1, 'target': nfid2,
                    'relationship': 'domain_sibling',
                    'weight': 0.5, 'date_added': date_str
                })

    print(f"Inserting {len(all_edges)} edges...")
    for edge in all_edges:
        c.execute("""
            INSERT OR IGNORE INTO edges (source, target, relationship, weight, date_added)
            VALUES (:source, :target, :relationship, :weight, :date_added)
        """, edge)

    conn.commit()
    conn.close()

    print(f"Writing {jsonl_path}")
    with open(jsonl_path, 'w') as f:
        for edge in all_edges:
            f.write(json.dumps(edge) + '\n')

    print(f"Done. {len(parsed_data)} nodes, {len(all_edges)} edges.")
    print(f"Database: {db_path}")

if __name__ == '__main__':
    main()