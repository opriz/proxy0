"""Shared connectivity / state-file / output helpers."""
import json
import os
import socket
import subprocess

from core import client_config as cc


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_state(path: str, state: dict):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def clear_state(path: str):
    if os.path.exists(path):
        os.remove(path)


def check_connectivity(ip: str, port: int):
    """TCP probe + ping, prints results."""
    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.close()
        print(f"  TCP {ip}:{port} ✓")
    except Exception as e:
        print(f"  TCP {ip}:{port} ✗ ({e})")

    result = subprocess.run(
        ["ping", "-c", "3", "-W", "2000", ip],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "avg" in line or "round-trip" in line:
                print(f"  {line.strip()}")
        print("  Ping ✓")
    else:
        print("  Ping ✗ (IP may be blocked — consider rebuild)")


def print_config(state: dict, provider: str, output_dir: str):
    """Print VLESS link and write Clash Meta YAML to output_dir."""
    ip = state["ip"]
    uuid = state["uuid"]
    port = state["port"]
    public_key = state.get("public_key", "")
    short_id = state.get("short_id", "")
    sni = state["sni"]

    if not public_key:
        print(f"Warning: public_key missing. Run: python3 main.py {provider.lower()} config")
        return

    link = cc.vless_link(ip, uuid, port, public_key, short_id, sni)
    print(f"[{provider} — VLESS link (Shadowrocket / v2rayN)]")
    print(link)
    print()

    clash_yaml = cc.generate_clash_config(ip, uuid, port, public_key, short_id, sni)
    clash_file = os.path.join(output_dir, f"clash_config_{provider.lower()}.yaml")
    with open(clash_file, "w") as f:
        f.write(clash_yaml)
    print(f"[{provider} — Clash Meta config] saved to: {clash_file}")
