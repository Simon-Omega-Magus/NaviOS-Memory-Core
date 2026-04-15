import sys
import json
import os
import time

def parse_simple_yaml(yaml_str):
    data = {}
    for line in yaml_str.splitlines():
        line = line.strip()
        if not line or line == '---' or line.startswith('#'):
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data

def main():
    raw_input = sys.stdin.read()
    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        sys.exit(1)

    metadata_content = data.get(".metadata", "")
    if not metadata_content:
        print("Error: No .metadata found in JSON.")
        sys.exit(1)

    try:
        yaml_data = parse_simple_yaml(metadata_content)
        target_dir = yaml_data.get('filepath', '')
        filename = yaml_data.get('filename', '')
        
        if os.path.isfile(target_dir):
            base_path = target_dir
        else:
            base_path = os.path.join(target_dir, filename) if filename else target_dir

    except Exception as e:
        print(f"Error parsing metadata: {e}")
        sys.exit(1)

    print(f"Unpacking to base path: {base_path}")
    current_time = time.time()
    
    for key, content in data.items():
        if key == ".metadata":
            out_path = f"{os.path.dirname(base_path)}/.metadata.{os.path.basename(base_path)}.yaml"
        else:
            out_path = f"{base_path}{key}"

        with open(out_path, 'w') as f:
            f.write(content)
        
        os.utime(out_path, (current_time, current_time))
        print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()