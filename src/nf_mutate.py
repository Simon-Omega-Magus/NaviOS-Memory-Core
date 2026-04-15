#!/usr/bin/env python3
import os
import sys
import yaml
import hashlib
import datetime
import subprocess
import tempfile
import shutil
from pathlib import Path

BRAIN_MATTER_ROOT = Path(os.environ.get("NAVIOS_CORE_ROOT", ".")) / "Brain-Matter"
UNPACKER_SCRIPT = Path(__file__).parent / "wmf_unpacker.py"

def get_file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

import uuid

def get_nfid(path, bm_dir_base):
    # Try xattr first
    try:
        import xattr
        val = xattr.getxattr(path, 'user.nfid')
        return val.decode('utf-8')
    except Exception:
        pass
    
    # Try to find existing metadata in bm_dir_base
    meta_name = f".metadata-{path.name}.yaml"
    for d in bm_dir_base.glob("nf-*"):
        if (d / meta_name).exists():
            return d.name
            
    # Generate new UUID if not found
    return f"nf-{uuid.uuid4()}"

def mutate_target(filepath, faerie_name=None, new_links=None, is_recursive=False, is_lite=False):
    path = Path(filepath).resolve()
    if not path.exists():
        print(f"Error: {path} does not exist.")
        return

    is_dir = path.is_dir()
    
    # Use the centralized Brain-Matter directory base
    bm_dir_base = BRAIN_MATTER_ROOT
    bm_dir_base.mkdir(parents=True, exist_ok=True)
    
    node_id = get_nfid(path, bm_dir_base)
    
    bm_dir = bm_dir_base / node_id
    bm_dir.mkdir(parents=True, exist_ok=True)

    metadata_file = bm_dir / f".metadata-{path.name}.yaml"
    
    # 1. The Backup Phase (Dark Matter)
    timestamp = datetime.datetime.now().strftime('%m%d%Y-%I%M%p')
    bu_filename = f".BU-{path.name}-{timestamp}.zip"
    bu_path = bm_dir / bu_filename
    
    print(f"[{path.name}] 1. Generating Backup...")
    if is_dir:
        # For directories, backup the directory itself recursively, and the vault contents
        zip_cmd = ["zip", "-r", str(bu_path), str(path)]
    else:
        zip_cmd = ["zip", "-j", str(bu_path), str(path)]
        
    for item in bm_dir.iterdir():
        if item.is_file() and not item.name.startswith(".BU-"):
            zip_cmd.append(str(item))
            
    subprocess.run(zip_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  -> Saved to {bu_path}")

    # 2. Metadata Update Phase
    print(f"[{path.name}] 2. Updating Metadata...")
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = yaml.safe_load(f) or {}
    else:
        metadata = {'nfid': node_id, 'original_path': str(path), 'type': 'CN' if is_dir else 'NF'}

    if not is_dir:
        metadata['content_hash'] = get_file_hash(path)
        
    metadata['last_updated'] = datetime.datetime.now().isoformat()
    metadata['has_l0_abstract'] = True
    
    # Track the model and confidence level
    metadata['model'] = 'gemini-3.1-flash-lite-preview' if is_lite else 'gemini-3-flash-preview'
    metadata['confidence'] = 0.4 if is_lite else 0.8

    # Determine L0 abstract filename based on target type
    if is_dir:
        if is_recursive:
            l0_filename = f".flash-a-r-{path.name}.md"
        else:
            l0_filename = f".flash-a-d-{path.name}.md"
    else:
        l0_filename = f".flash-a-f-{path.name}.md"
        
    metadata['l0_filepath'] = str(bm_dir / l0_filename)

    # 3. Subjective Holographic Links
    if faerie_name and new_links:
        link_key = f"links_{faerie_name.lower()}"
        if link_key not in metadata:
            metadata[link_key] = []
        for link in new_links:
            if link not in metadata[link_key]:
                metadata[link_key].append(link)
        print(f"  -> Added {len(new_links)} subjective links for {faerie_name}.")

    with open(metadata_file, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False)

    # 4. Myelin-Wisp Saturation Phase
    print(f"[{path.name}] 3. Spawning Myelin-Wisp...")
    
    if is_dir:
        if is_recursive:
            wisp_name = "myelin-r-wisp.md"
            prompt_text = f"Distill the recursive directory tree: {path}"
        else:
            wisp_name = "myelin-d-wisp.md"
            prompt_text = f"Distill the flat directory: {path}"
    else:
        wisp_name = "myelin-f-wisp.md"
        prompt_text = f"Distill the Neuron-File: {path}"

    wisp_home = tempfile.mkdtemp(prefix="wisp_home_")
    
    # Copy essential configuration and auth files so the CLI can authenticate
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
            
            # Aggressively extract the JSON block in case the LLM added conversational text
            start_idx = wisp_response_str.find('{')
            end_idx = wisp_response_str.rfind('}')
            if start_idx != -1 and end_idx != -1:
                wisp_response_str = wisp_response_str[start_idx:end_idx+1]
                wisp_json = json.loads(wisp_response_str)
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
                            f".flash-a-{prefix}-{path.name}.md": f"# L0 Abstract\n\n{l0_match.group(1).strip()}",
                            f".flash-s-{prefix}-{path.name}.md": f"# L1 Summary\n\n{l1_match.group(1).strip()}",
                            f".flash-ls-{prefix}-{path.name}.md": f"# L2 Lesser-Synthesis\n\n{l2_match.group(1).strip()}"
                        }
                    }
                else:
                    raise json.JSONDecodeError("No JSON object could be decoded and Fallback Regex failed.", wisp_response_str, 0)
                
            wisp_json["directory"] = str(bm_dir) 
            
            unpacker_process = subprocess.Popen([str(UNPACKER_SCRIPT)], stdin=subprocess.PIPE)
            unpacker_process.communicate(input=json.dumps(wisp_json).encode())
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
    parser.add_argument("--recursive", action="store_true", help="If target is a directory, process it as a CA (recursive) instead of CN (flat).")
    parser.add_argument("--lite", action="store_true", help="Use the faster/cheaper gemini-3.1-flash-lite model and tag the output with a lower confidence score.")
    
    args = parser.parse_args()
    mutate_target(args.filepath, args.faerie, args.links, args.recursive, args.lite)
add_argument("--recursive", action="store_true", help="If target is a directory, process it as a CA (recursive) instead of CN (flat).")
    parser.add_argument("--lite", action="store_true", help="Use the faster/cheaper gemini-3.1-flash-lite model and tag the output with a lower confidence score.")
    
    args = parser.parse_args()
    mutate_target(args.filepath, args.faerie, args.links, args.recursive, args.lite)
