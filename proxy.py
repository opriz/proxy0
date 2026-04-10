#!/usr/bin/env python3
"""
proxy.py - Vultr proxy server management tool

Usage:
  python proxy.py create              # create a new server
  python proxy.py destroy             # destroy the current server
  python proxy.py rebuild             # destroy and recreate (use when IP is blocked)
  python proxy.py config              # print the client config
  python proxy.py status              # show the current server status
  python proxy.py check               # probe IP connectivity
  python proxy.py regions             # list available regions
"""

import sys
import json
import os
import time
import subprocess

import requests

import vultr
import cloudinit
import client_config as cc
from config import (
    INSTANCE_LABEL, REGION, PLAN, OS_ID,
    XRAY_PORT, XRAY_SNI, STATE_FILE, SSH_KEY_ID
)


# ─── State file helpers ──────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


# ─── Core commands ───────────────────────────────────────────────────────────

def cmd_create():
    state = load_state()
    if state.get("instance_id"):
        print(f"An instance is already running: {state['instance_id']} / {state.get('ip')}")
        print("To recreate it, run: python proxy.py rebuild")
        return

    print(f"Creating instance (region: {REGION}, plan: {PLAN})...")
    user_data = cloudinit.generate_user_data(XRAY_PORT, XRAY_SNI)
    client_uuid = cloudinit.get_client_uuid_from_script(user_data)

    inst = vultr.create_instance(
        region=REGION,
        plan=PLAN,
        os_id=OS_ID,
        label=INSTANCE_LABEL,
        user_data=user_data,
        ssh_key_ids=[SSH_KEY_ID] if SSH_KEY_ID else None,
    )
    instance_id = inst["id"]
    print(f"Instance created: {instance_id}")
    print("Waiting for the instance to be ready (about 2-3 minutes)...")

    inst = vultr.wait_for_active(instance_id)
    ip = inst["main_ip"]
    print(f"Instance is ready! IP: {ip}")

    # Wait for xray to finish installing (cloud-init takes a bit)
    print("Waiting for xray to initialize (about 60 seconds)...")
    time.sleep(60)

    # Read proxy_info.json from the server
    print("Reading server-side config...")
    proxy_info = fetch_proxy_info(ip)

    state = {
        "instance_id": instance_id,
        "ip": ip,
        "uuid": proxy_info.get("uuid", client_uuid),
        "public_key": proxy_info.get("public_key", ""),
        "short_id": proxy_info.get("short_id", ""),
        "port": XRAY_PORT,
        "sni": XRAY_SNI,
        "region": REGION,
    }
    save_state(state)

    print("\n" + "="*60)
    print_config(state)


def cmd_destroy():
    state = load_state()
    if not state.get("instance_id"):
        # Try to find it via the Vultr API
        instances = vultr.list_instances(label=INSTANCE_LABEL)
        if not instances:
            print("No running instance found")
            return
        for inst in instances:
            print(f"Deleting instance: {inst['id']} / {inst.get('main_ip')}")
            vultr.delete_instance(inst["id"])
        clear_state()
        print("All instances destroyed")
        return

    instance_id = state["instance_id"]
    print(f"Destroying instance: {instance_id} / {state.get('ip')}")
    vultr.delete_instance(instance_id)
    clear_state()
    print("Instance destroyed")


def cmd_rebuild():
    print("Rebuilding (destroy old instance -> create new instance)...")
    cmd_destroy()
    time.sleep(5)
    cmd_create()


def cmd_config():
    state = load_state()
    if not state.get("ip"):
        print("No running instance. Run: python proxy.py create")
        return
    if not state.get("public_key"):
        print("public_key is missing, trying to re-read it from the server...")
        proxy_info = fetch_proxy_info(state["ip"])
        state.update(proxy_info)
        save_state(state)
    print_config(state)


def cmd_status():
    state = load_state()
    if not state.get("instance_id"):
        print("No local state, querying the Vultr API...")
        instances = vultr.list_instances(label=INSTANCE_LABEL)
        if not instances:
            print("No running instance found")
        for inst in instances:
            print(f"  ID: {inst['id']}")
            print(f"  IP: {inst.get('main_ip')}")
            print(f"  Status: {inst.get('status')} / {inst.get('power_status')}")
        return

    print(f"Instance ID : {state['instance_id']}")
    print(f"IP          : {state.get('ip')}")
    print(f"Region      : {state.get('region')}")
    print(f"Port        : {state.get('port')}")
    print(f"UUID        : {state.get('uuid')}")

    # Fetch live status from the API
    try:
        inst = vultr.get_instance(state["instance_id"])
        print(f"API status  : {inst.get('status')} / {inst.get('power_status')}")
    except Exception as e:
        print(f"API query failed: {e}")


def cmd_check():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("No running instance")
        return

    print(f"Probing IP: {ip}")

    # Method 1: TCP connectivity
    port = state.get("port", XRAY_PORT)
    import socket
    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.close()
        print(f"  TCP {ip}:{port} ✓ reachable")
    except Exception as e:
        print(f"  TCP {ip}:{port} ✗ unreachable ({e})")

    # Method 2: ping
    result = subprocess.run(
        ["ping", "-c", "3", "-W", "2000", ip],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        # Extract latency
        for line in result.stdout.splitlines():
            if "avg" in line or "round-trip" in line:
                print(f"  Ping: {line.strip()}")
        print(f"  Ping ✓")
    else:
        print(f"  Ping ✗ IP may be blocked; consider running: python proxy.py rebuild")


def cmd_regions():
    print("Fetching available regions...")
    regions = vultr.list_regions()
    for r in sorted(regions, key=lambda x: x["id"]):
        print(f"  {r['id']:8s} {r['city']}, {r['country']}")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def fetch_proxy_info(ip: str) -> dict:
    """Read /root/proxy_info.json from the server over SSH."""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10",
                f"root@{ip}",
                "cat /root/proxy_info.json"
            ],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"  SSH read failed: {result.stderr.strip()}")
    except Exception as e:
        print(f"  SSH connection failed: {e}")
    return {}


def print_config(state: dict):
    ip = state["ip"]
    uuid = state["uuid"]
    port = state["port"]
    public_key = state.get("public_key", "")
    short_id = state.get("short_id", "")
    sni = state["sni"]

    if not public_key:
        print("Warning: public_key is empty, the config may be incomplete")
        print("Wait for the server to finish initializing, then run: python proxy.py config")
        return

    # VLESS link
    link = cc.vless_link(ip, uuid, port, public_key, short_id, sni)
    print("[Shadowrocket / v2rayN import link]")
    print(link)
    print()

    # Clash config
    clash_yaml = cc.generate_clash_config(ip, uuid, port, public_key, short_id, sni)
    clash_file = "clash_config.yaml"
    with open(clash_file, "w") as f:
        f.write(clash_yaml)
    print(f"[Clash Meta config] saved to: {clash_file}")
    print()
    print(clash_yaml)


# ─── Entry point ─────────────────────────────────────────────────────────────

COMMANDS = {
    "create": cmd_create,
    "destroy": cmd_destroy,
    "rebuild": cmd_rebuild,
    "config": cmd_config,
    "status": cmd_status,
    "check": cmd_check,
    "regions": cmd_regions,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
