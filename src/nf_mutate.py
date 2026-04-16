#!/usr/bin/env python3
import os
import sys
import yaml
import hashlib
import datetime
import subprocess
import tempfile
import shutil
import uuid
from pathlib import Path

BRAIN_MATTER_ROOT = Path(os.environ.get("NAVIOS_CORE_ROOT", ".")) / "Brain-Matter"
UNPACKER_SCRIPT = Path(__file__).parent / "wmf_unpacker.py"

def get_file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_or_create_nc(path, bm_dir_base, is_recursive=False):
    """
    Returns (node_id, bm_dir).
    If the file is already hardlinked into the Brain-Matter vault, we find it by inode.
    If not, we generate a new UUID and hardlink it.
    """
    stat_info = os.stat(path)
    inode = stat_info.st_ino
    
    # 1. Search for existing Neural-Cluster by inode
    if stat_info.st_nlink > 1:
        for d in bm_dir_base.iterdir():
            if d.is_dir() and d.name.startswith(('nf-', 'cn-', 'ca-')):
                target_link = d / path.name
                if target_link.exists() and target_link.stat().st_ino == inode:
                    return d.name, d
                    
    # 2. Not found or not linked. Create new UUID.
    if path.is_dir():
        prefix = "ca" if is_recursive else "cn"
    else:
        prefix = "nf"
    node_id = f"{prefix}-{uuid.uuid4()}"
    bm_dir = bm_dir_base / node_id
    bm_dir.mkdir(parents=True, exist_ok=True)
    
    # Hardlink the file into the vault (for Neuron-Files only, directories can't be hardlinked safely across all OSes)
    if path.is_file():
        target_link = bm_dir / path.name
        if target_link.exists():
            target_link.unlink()
        try:
            os.link(path, target_link)
        except Exception as e:
            print(f"Warning: Failed to create hardlink for {path.name}. Fallback to copying. Error: {e}")
            shutil.copy2(path, target_link)
            
    return node_id, bm_dir

def mutate_target(filepath, faerie_name=None, new_links=None, is_recursive=False, is_lite=False, backup_only=False):
    path = Path(filepath).resolve()
    if not path.exists():
        print(f"Error: {path} does not exist.")
        return

    is_dir = path.is_dir()
    
    # Use the centralized Brain-Matter directory base
    bm_dir_base = BRAIN_MATTER_ROOT
    bm_dir_base.mkdir(parents=True, exist_ok=True)
    
    node_id, bm_dir = get_or_create_nc(path, bm_dir_base, is_recursive)
    metadata_file = bm_dir / f".metadata-{path.name}.yaml"
    
    # 1. The Backup Phase (Dark Matter)
    timestamp = datetime.datetime.now().strftime('%m%d%Y-%I%M%p')
    bu_filename = f".BU-{path.name}-{timestamp}.zip"
    bu_path = bm_dir / bu_filename
    
    print(f"[{path.name}] 1. Generating Neural-Cluster Backup...")
    if is_dir:
        zip_cmd = ["zip", "-r", str(bu_path), str(path)]
    else:
        # Zip the existing contents of the bm_dir before we mutate
        zip_cmd = ["zip", "-j", str(bu_path)]
        
    for item in bm_dir.iterdir():
        if item.is_file() and not item.name.startswith(".BU-") and item.name != path.name:
            zip_cmd.append(str(item))
            
    if len(zip_cmd) > 3 or is_dir:
        subprocess.run(zip_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  -> Saved to {bu_path}")

    if backup_only:
        print(f"[{path.name}] Backup complete. Exiting.")
        return

    # 2. Metadata Update Phase
    print(f"[{path.name}] 2. Updating Metadata...")
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f) or {}
    else:
        metadata = {'nfid': node_id, 'original_path': str(path), 'type': 'CA' if is_recursive else ('CN' if is_dir else 'NF')}

    if not is_dir:
        metadata['content_hash'] = get_file_hash(path)
        
    metadata['last_updated'] = datetime.datetime.now().isoformat()
    metadata['has_l0_abstract'] = True
    if 'date_created' not in metadata:
        metadata['date_created'] = metadata.get('created_at', metadata['last_updated'])
    metadata['edit_count'] = metadata.get('edit_count', 0) + 1
    
    metadata['model'] = 'gemini-3.1-flash-lite-preview' if is_lite else 'gemini-3-flash-preview'
    metadata['confidence'] = 0.4 if is_lite else 0.8

    if is_dir:
        l0_filename = f".flash-0-r-{path.name}.md" if is_recursive else f".flash-0-d-{path.name}.md"
    else:
        l0_filename = f".flash-0-f-{path.name}.md"
        
    metadata['l0_filepath'] = str(bm_dir / l0_filename)

    # 3. Subjective Holographic Links (Legacy / Manual)
    if faerie_name and new_links:
        link_key = f"links_{faerie_name.lower()}"
        if link_key not in metadata:
            metadata[link_key] = []
        for link in new_links:
            if link not in metadata[link_key]:
                metadata[link_key].append(link)
        print(f"  -> Added {len(new_links)} subjective links for {faerie_name}.")

    with open(metadata_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(metadata, f, default_flow_style=False)

    # 4. Purge Stale White-Matter (L0, L1, L2) before Wisp regeneration
    for item in bm_dir.iterdir():
        if item.is_file() and item.name.startswith(".flash-"):
            item.unlink()

    # 5. Myelin-Wisp Saturation Phase
    print(f"[{path.name}] 3. Spawning Myelin-Wisp...")
    
    if is_dir:
        wisp_name = "myelin-r-wisp.md" if is_recursive else "myelin-d-wisp.md"
        prompt_text = f"Distill the directory: {path}"
    else:
        wisp_name = "myelin-f-wisp.md"
        prompt_text = f"Distill the Neuron-File: {path}"

    wisp_home = tempfile.mkdtemp(prefix="wisp_home_")
    
    # Copy configuration
    base_gemini = os.path.expanduser("~/.gemini")
    target_gemini = os.path.join(wisp_home, ".gemini")
    if os.path.exists(base_gemini):
        shutil.copytree(base_gemini, target_gemini, dirs_exist_ok=True, ignore=shutil.ignore_patterns("tmp", "logs", "chats"))

    env = os.environ.copy()
    env["GEMINI_CLI_HOME"] = wisp_home

    wisp_path = Path(__file__).parent.parent / "prompts" / wisp_name
    model_arg = "gemini-3.1-flash-lite-preview" if is_lite else "gemini-3-flash-preview"
    wisp_cmd = [
        "gemini", "-p", f"@{wisp_path} {prompt_text}",
        "-m", model_arg,
        "--output-format", "json"
    ]
    
    try:
        wisp_process = subprocess.Popen(wisp_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout, stderr = wisp_process.communicate()
        
        if wisp_process.returncode != 0:
            print(f"  -> Wisp Error: {stderr.decode()}")
            return
            
        import json
        try:
            cli_json = json.loads(stdout.decode())
            wisp_response_str = cli_json.get("response", "")
            wisp_response_str = wisp_response_str.strip()
            
            start_idx = wisp_response_str.find('{')
            end_idx = wisp_response_str.rfind('}')
            if start_idx != -1 and end_idx != -1:
                wisp_response_str = wisp_response_str[start_idx:end_idx+1]
                wisp_json = json.loads(wisp_response_str, strict=False)
            else:
                # FALLBACK: If LLM completely ignored the JSON schema and output raw markdown
                import re
                l0_match = re.search(r'(?i)(?:#+|L0|Abstract).*?\n(.*?)(?=\n(?:#+|L1|Summary))', wisp_response_str, re.DOTALL)
                l1_match = re.search(r'(?i)(?:#+|L1|Summary).*?\n(.*?)(?=\n(?:#+|L2|Lesser))', wisp_response_str, re.DOTALL)
                l2_match = re.search(r'(?i)(?:#+|L2|Lesser).*?\n(.*)', wisp_response_str, re.DOTALL)
                
                if l0_match and l1_match and l2_match:
                    prefix = "d" if is_dir and not is_recursive else "r" if is_recursive else "f"
                    wisp_json = {
                        "directory": ".",
                        "files": {
                            f".flash-0-{prefix}-{path.name}.md": f"# L0 Abstract\n\n{l0_match.group(1).strip()}",
                            f".flash-1-{prefix}-{path.name}.md": f"# L1 Summary\n\n{l1_match.group(1).strip()}",
                            f".flash-2-{prefix}-{path.name}.md": f"# L2 Lesser-Synthesis\n\n{l2_match.group(1).strip()}"
                        }
                    }
                else:
                    raise json.JSONDecodeError("No JSON object could be decoded and Fallback Regex failed.", wisp_response_str, 0)
                
            if ".metadata" in wisp_json:
                import yaml as wisp_yaml
                try:
                    wisp_meta = wisp_yaml.safe_load(wisp_json[".metadata"])
                    if isinstance(wisp_meta, dict) and "ontology_types" in wisp_meta:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            meta_data = wisp_yaml.safe_load(f) or {}
                        existing_types = meta_data.get("ontology_types", [])
                        if not isinstance(existing_types, list):
                            existing_types = []
                        new_types = wisp_meta["ontology_types"]
                        if isinstance(new_types, list):
                            # Merge and deduplicate
                            meta_data["ontology_types"] = list(set(existing_types + new_types))
                            with open(metadata_file, 'w', encoding='utf-8') as f:
                                f.write("---\n")
                                wisp_yaml.dump(meta_data, f, default_flow_style=False)
                except Exception as e:
                    print(f"  -> Failed to parse Wisp synapses: {e}")
                del wisp_json[".metadata"]
                
            if "files" in wisp_json and isinstance(wisp_json["files"], dict):
                for flash_filename, content in wisp_json["files"].items():
                    out_path = bm_dir / flash_filename
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(content)
            else:
                # Fallback if Wisp outputted flat JSON
                for k, v in wisp_json.items():
                    if k.startswith(".flash-"):
                        out_path = bm_dir / k
                        with open(out_path, "w", encoding="utf-8") as f:
                            f.write(v)

            print(f"[{path.name}] Mutation Complete! BMFs saturated.")
        except json.JSONDecodeError as e:
            print(f"  -> Wisp failed to return valid JSON. Error: {e}")
            print(stdout.decode())

    except Exception as e:
        print(f"  -> Pipeline failure: {e}")
    finally:
        shutil.rmtree(wisp_home, ignore_errors=True)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Mutate a Node, backup its state, and regenerate its BMFs.")
    parser.add_argument("filepath", help="The target NF or Directory to mutate.")
    parser.add_argument("--faerie", help="The name of the Faerie adding subjective links.")
    parser.add_argument("--links", nargs="+", help="A list of subjective filepaths or concepts to link.", default=[])
    parser.add_argument("--recursive", action="store_true", help="Process directory as CA (recursive).")
    parser.add_argument("--lite", action="store_true", help="Use faster/cheaper lite model.")
    parser.add_argument("--backup-only", action="store_true", help="Only perform the NC backup, do not mutate White-Matter.")
    
    args = parser.parse_args()
    mutate_target(args.filepath, args.faerie, args.links, args.recursive, args.lite, args.backup_only)
