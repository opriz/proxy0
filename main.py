#!/usr/bin/env python3
"""
proxy0 - Unified entry point for Vultr and Aliyun proxy management

Usage:
  python3 main.py vultr create              # Create Vultr server
  python3 main.py vultr destroy             # Destroy Vultr server
  python3 main.py vultr rebuild             # Rebuild Vultr server
  python3 main.py vultr config              # Show Vultr config
  python3 main.py vultr status              # Show Vultr status
  python3 main.py vultr check               # Check Vultr connectivity
  python3 main.py vultr regions             # List Vultr regions

  python3 main.py aliyun list               # List Aliyun instances
  python3 main.py aliyun deploy <ip>        # Deploy to Aliyun instance
  python3 main.py aliyun config             # Show Aliyun config
  python3 main.py aliyun status             # Show Aliyun status
  python3 main.py aliyun check              # Check Aliyun connectivity
  python3 main.py aliyun destroy            # Destroy Aliyun server
  python3 main.py aliyun rebuild            # Rebuild Aliyun server

  python3 main.py status                    # Auto-detect and show status
  python3 main.py config                    # Auto-detect and show config
  python3 main.py check                     # Auto-detect and check connectivity
"""

import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vultr
import cloudinit
import client_config as cc
from config import (
    INSTANCE_LABEL, REGION, PLAN, OS_ID,
    XRAY_PORT, XRAY_SNI, SSH_KEY_ID
)


# Import Aliyun functions from proxy_aliyun
from proxy_aliyun import (
    _list_instances as aliyun_list_instances,
    _delete_instance as aliyun_delete_instance,
    _load_state as aliyun_load_state,
    _save_state as aliyun_save_state,
    _clear_state as aliyun_clear_state,
    _generate_script as aliyun_generate_script,
    _ssh_run as aliyun_ssh_run,
    _scp_upload as aliyun_scp_upload,
    _fetch_proxy_info as aliyun_fetch_proxy_info,
    STATE_FILE as ALIYUN_STATE_FILE
)


# State file for Vultr
VULTR_STATE_FILE = ".proxy_state.json"


def load_vultr_state():
    import json
    if os.path.exists(VULTR_STATE_FILE):
        with open(VULTR_STATE_FILE) as f:
            return json.load(f)
    return {}


def save_vultr_state(state):
    import json
    with open(VULTR_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def clear_vultr_state():
    if os.path.exists(VULTR_STATE_FILE):
        os.remove(VULTR_STATE_FILE)


def cmd_vultr_create():
    """Create a new Vultr instance."""
    state = load_vultr_state()
    if state.get("instance_id"):
        print(f"A Vultr instance is already running: {state['instance_id']} / {state.get('ip')}")
        print("To recreate it, run: python3 main.py vultr rebuild")
        return

    print(f"Creating Vultr instance (region: {REGION}, plan: {PLAN})...")
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
    print("Waiting for instance to be ready (about 2-3 minutes)...")

    import time
    inst = vultr.wait_for_active(instance_id)
    ip = inst["main_ip"]
    print(f"Instance ready! IP: {ip}")

    print("Waiting for xray to initialize (about 60 seconds)...")
    time.sleep(60)

    print("Reading server config...")
    proxy_info = fetch_vultr_proxy_info(ip)

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
    save_vultr_state(state)

    print("\n" + "="*60)
    print_config(state, "Vultr")


def cmd_vultr_destroy():
    """Destroy the Vultr instance."""
    state = load_vultr_state()
    if not state.get("instance_id"):
        instances = vultr.list_instances(label=INSTANCE_LABEL)
        if not instances:
            print("No Vultr instance found")
            return
        for inst in instances:
            print(f"Deleting instance: {inst['id']} / {inst.get('main_ip')}")
            vultr.delete_instance(inst["id"])
        clear_vultr_state()
        print("All instances destroyed")
        return

    instance_id = state["instance_id"]
    print(f"Destroying Vultr instance: {instance_id} / {state.get('ip')}")
    vultr.delete_instance(instance_id)
    clear_vultr_state()
    print("Instance destroyed")


def cmd_vultr_rebuild():
    """Rebuild the Vultr instance."""
    import time
    print("Rebuilding Vultr instance...")
    cmd_vultr_destroy()
    time.sleep(5)
    cmd_vultr_create()


def cmd_vultr_config():
    """Show Vultr config."""
    state = load_vultr_state()
    if not state.get("ip"):
        print("No Vultr instance. Run: python3 main.py vultr create")
        return
    if not state.get("public_key"):
        print("public_key missing, trying to re-read...")
        proxy_info = fetch_vultr_proxy_info(state["ip"])
        state.update(proxy_info)
        save_vultr_state(state)
    print_config(state, "Vultr")


def cmd_vultr_status():
    """Show Vultr status."""
    state = load_vultr_state()
    if not state.get("instance_id"):
        print("No Vultr instance tracked")
        return

    print(f"Provider    : Vultr")
    print(f"Instance ID : {state['instance_id']}")
    print(f"IP          : {state.get('ip')}")
    print(f"Region      : {state.get('region')}")
    print(f"Port        : {state.get('port')}")
    print(f"UUID        : {state.get('uuid')}")

    try:
        inst = vultr.get_instance(state["instance_id"])
        print(f"API Status  : {inst.get('status')} / {inst.get('power_status')}")
    except Exception as e:
        print(f"API query failed: {e}")


def cmd_vultr_check():
    """Check Vultr connectivity."""
    state = load_vultr_state()
    ip = state.get("ip")
    if not ip:
        print("No Vultr instance")
        return

    print(f"Checking Vultr {ip}...")
    check_connectivity(ip, state.get("port", XRAY_PORT))


def cmd_vultr_regions():
    """List Vultr regions."""
    print("Available Vultr regions:")
    regions = vultr.list_regions()
    for r in sorted(regions, key=lambda x: x["id"]):
        print(f"  {r['id']:8s} {r['city']}, {r['country']}")


def fetch_vultr_proxy_info(ip: str):
    """Fetch proxy info from Vultr instance."""
    import subprocess
    import json
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
             f"root@{ip}", "cat /root/proxy_info.json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"SSH failed: {e}")
    return {}


# Aliyun commands
def cmd_aliyun_list():
    """List Aliyun instances."""
    print("Aliyun SWAS instances:")
    instances = aliyun_list_instances()
    if not instances:
        print("  No instances found")
        return
    for inst in instances:
        print(f"  ID: {inst.get('InstanceId')}")
        print(f"  Name: {inst.get('InstanceName')}")
        print(f"  IP: {inst.get('PublicIpAddress', {}).get('Ip', 'N/A')}")
        print(f"  Status: {inst.get('Status')}")
        print("-" * 40)


def cmd_aliyun_deploy():
    """Deploy to Aliyun instance."""
    import time
    from config import ALIYUN_PW

    if len(sys.argv) < 4:
        instances = aliyun_list_instances()
        if instances:
            print("Found instances:")
            for idx, inst in enumerate(instances, 1):
                ip = inst.get('PublicIpAddress', {}).get('Ip', 'N/A')
                print(f"  {idx}. {inst.get('InstanceName')} - {ip}")
            print("\nUsage: python3 main.py aliyun deploy <ip>")
        else:
            print("No instances. Create one at: https://swasnext.console.aliyun.com/buy")
        return

    ip = sys.argv[3]
    print(f"Deploying to Aliyun {ip}...")

    if not ALIYUN_PW:
        print("Error: ALIYUN_PW not set in .env")
        return

    client_uuid, script = aliyun_generate_script(XRAY_PORT, XRAY_SNI)

    temp_script = "/tmp/deploy_xray.sh"
    with open(temp_script, "w") as f:
        f.write(script)

    print("Uploading script...")
    result = aliyun_scp_upload(ip, temp_script, "/tmp/deploy_xray.sh")
    if result.returncode != 0:
        print(f"SCP failed: {result.stderr}")
        return

    print("Running deployment (2-3 minutes)...")
    result = aliyun_ssh_run(ip, "bash /tmp/deploy_xray.sh", timeout=300)
    if result.returncode != 0:
        print(f"Deployment failed: {result.stderr}")
        return

    print("Waiting for xray...")
    time.sleep(10)

    proxy_info = aliyun_fetch_proxy_info(ip)
    if not proxy_info:
        time.sleep(30)
        proxy_info = aliyun_fetch_proxy_info(ip)

    state = {
        "instance_id": "manual",
        "ip": ip,
        "uuid": proxy_info.get("uuid", client_uuid),
        "public_key": proxy_info.get("public_key", ""),
        "short_id": proxy_info.get("short_id", ""),
        "port": XRAY_PORT,
        "sni": XRAY_SNI,
        "region": "cn-hongkong",
    }
    aliyun_save_state(state)

    print("\n" + "="*60)
    print_config(state, "Aliyun")


def cmd_aliyun_config():
    """Show Aliyun config."""
    state = aliyun_load_state()
    if not state.get("ip"):
        print("No Aliyun instance. Run: python3 main.py aliyun deploy <ip>")
        return
    if not state.get("public_key"):
        proxy_info = aliyun_fetch_proxy_info(state["ip"])
        state.update(proxy_info)
        aliyun_save_state(state)
    print_config(state, "Aliyun")


def cmd_aliyun_status():
    """Show Aliyun status."""
    state = aliyun_load_state()
    if not state.get("ip"):
        print("No Aliyun instance tracked")
        return

    print(f"Provider    : Aliyun")
    print(f"IP          : {state['ip']}")
    print(f"Region      : {state.get('region', 'cn-hongkong')}")
    print(f"Port        : {state.get('port')}")
    print(f"UUID        : {state.get('uuid')}")


def cmd_aliyun_check():
    """Check Aliyun connectivity."""
    state = aliyun_load_state()
    ip = state.get("ip")
    if not ip:
        print("No Aliyun instance")
        return

    print(f"Checking Aliyun {ip}...")
    check_connectivity(ip, state.get("port", XRAY_PORT))


def cmd_aliyun_destroy():
    """Destroy Aliyun instance."""
    state = aliyun_load_state()

    if not state.get("instance_id") or state.get("instance_id") == "manual":
        instances = aliyun_list_instances()
        if not instances:
            print("No Aliyun instances")
            aliyun_clear_state()
            return

        print("Found instances:")
        for idx, inst in enumerate(instances, 1):
            ip = inst.get('PublicIpAddress', {}).get('Ip', 'N/A')
            print(f"  {idx}. {inst.get('InstanceName')} - {ip}")

        try:
            choice = int(input("Select to delete (0 to cancel): ").strip())
            if 1 <= choice <= len(instances):
                inst = instances[choice - 1]
                confirm = input(f"Delete {inst.get('InstanceId')}? (yes/no): ")
                if confirm.lower() == "yes":
                    aliyun_delete_instance(inst["InstanceId"])
                    print(f"Deleted: {inst['InstanceId']}")
        except (ValueError, EOFError):
            pass

        aliyun_clear_state()
        return

    instance_id = state["instance_id"]
    print(f"Destroying Aliyun instance: {instance_id}")
    try:
        aliyun_delete_instance(instance_id)
    except Exception as e:
        print(f"Error: {e}")
    aliyun_clear_state()
    print("Instance destroyed")


def cmd_aliyun_rebuild():
    """Rebuild Aliyun instance."""
    import time
    print("Rebuilding Aliyun instance...")
    cmd_aliyun_destroy()
    time.sleep(5)
    print("\nCreate new instance at: https://swasnext.console.aliyun.com/buy")
    print("Then run: python3 main.py aliyun deploy <ip>")


# Auto-detect commands
def cmd_auto_status():
    """Auto-detect provider and show status."""
    vultr_state = load_vultr_state()
    aliyun_state = aliyun_load_state()

    if vultr_state.get("ip") and aliyun_state.get("ip"):
        print("Both Vultr and Aliyun instances are configured:")
        print("\n--- Vultr ---")
        print(f"IP: {vultr_state['ip']} | Region: {vultr_state.get('region')}")
        print("\n--- Aliyun ---")
        print(f"IP: {aliyun_state['ip']} | Region: {aliyun_state.get('region', 'cn-hongkong')}")
        print("\nUse 'python3 main.py vultr status' or 'python3 main.py aliyun status' for details")
    elif vultr_state.get("ip"):
        cmd_vultr_status()
    elif aliyun_state.get("ip"):
        cmd_aliyun_status()
    else:
        print("No instances configured.")
        print("Create Vultr: python3 main.py vultr create")
        print("Create Aliyun: python3 main.py aliyun deploy <ip>")


def cmd_auto_config():
    """Auto-detect provider and show config."""
    vultr_state = load_vultr_state()
    aliyun_state = aliyun_load_state()

    if vultr_state.get("ip") and aliyun_state.get("ip"):
        print("Both providers configured. Use specific commands:")
        print("  python3 main.py vultr config")
        print("  python3 main.py aliyun config")
    elif vultr_state.get("ip"):
        cmd_vultr_config()
    elif aliyun_state.get("ip"):
        cmd_aliyun_config()
    else:
        print("No instances configured")


def cmd_auto_check():
    """Auto-detect provider and check connectivity."""
    vultr_state = load_vultr_state()
    aliyun_state = aliyun_load_state()

    if vultr_state.get("ip"):
        print("=== Vultr ===")
        check_connectivity(vultr_state["ip"], vultr_state.get("port", XRAY_PORT))
        print()

    if aliyun_state.get("ip"):
        print("=== Aliyun ===")
        check_connectivity(aliyun_state["ip"], aliyun_state.get("port", XRAY_PORT))

    if not vultr_state.get("ip") and not aliyun_state.get("ip"):
        print("No instances configured")


# Helper functions
def print_config(state: dict, provider: str):
    """Print client configuration."""
    ip = state["ip"]
    uuid = state["uuid"]
    port = state["port"]
    public_key = state.get("public_key", "")
    short_id = state.get("short_id", "")
    sni = state["sni"]

    if not public_key:
        print("Warning: public_key empty. Run: python3 main.py <provider> config")
        return

    link = cc.vless_link(ip, uuid, port, public_key, short_id, sni)
    print(f"[{provider} - Shadowrocket / v2rayN link]")
    print(link)
    print()

    clash_yaml = cc.generate_clash_config(ip, uuid, port, public_key, short_id, sni)
    clash_file = f"clash_config_{provider.lower()}.yaml"
    with open(clash_file, "w") as f:
        f.write(clash_yaml)
    print(f"[{provider} - Clash config] saved to: {clash_file}")


def check_connectivity(ip: str, port: int):
    """Check TCP and ping connectivity."""
    import socket
    import subprocess

    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.close()
        print(f"  TCP {ip}:{port} ✓")
    except Exception as e:
        print(f"  TCP {ip}:{port} ✗ ({e})")

    result = subprocess.run(["ping", "-c", "3", "-W", "2000", ip],
                           capture_output=True, text=True)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "avg" in line or "round-trip" in line:
                print(f"  {line.strip()}")
        print("  Ping ✓")
    else:
        print("  Ping ✗")


def print_usage():
    """Print usage information."""
    print(__doc__)


# Command routing
VULTR_COMMANDS = {
    "create": cmd_vultr_create,
    "destroy": cmd_vultr_destroy,
    "rebuild": cmd_vultr_rebuild,
    "config": cmd_vultr_config,
    "status": cmd_vultr_status,
    "check": cmd_vultr_check,
    "regions": cmd_vultr_regions,
}

ALIYUN_COMMANDS = {
    "list": cmd_aliyun_list,
    "deploy": cmd_aliyun_deploy,
    "config": cmd_aliyun_config,
    "status": cmd_aliyun_status,
    "check": cmd_aliyun_check,
    "destroy": cmd_aliyun_destroy,
    "rebuild": cmd_aliyun_rebuild,
}

AUTO_COMMANDS = {
    "status": cmd_auto_status,
    "config": cmd_auto_config,
    "check": cmd_auto_check,
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    provider = sys.argv[1].lower()

    if provider in ("vultr", "v"):
        if len(sys.argv) < 3:
            print("Vultr commands: create, destroy, rebuild, config, status, check, regions")
            sys.exit(1)
        cmd = sys.argv[2].lower()
        if cmd in VULTR_COMMANDS:
            VULTR_COMMANDS[cmd]()
        else:
            print(f"Unknown Vultr command: {cmd}")
            print("Available: create, destroy, rebuild, config, status, check, regions")

    elif provider in ("aliyun", "ali", "a"):
        if len(sys.argv) < 3:
            print("Aliyun commands: list, deploy, config, status, check, destroy, rebuild")
            sys.exit(1)
        cmd = sys.argv[2].lower()
        if cmd in ALIYUN_COMMANDS:
            ALIYUN_COMMANDS[cmd]()
        else:
            print(f"Unknown Aliyun command: {cmd}")
            print("Available: list, deploy, config, status, check, destroy, rebuild")

    elif provider in ("status", "config", "check"):
        # Auto-detect commands without provider prefix
        AUTO_COMMANDS[provider]()

    elif provider in ("-h", "--help", "help"):
        print_usage()

    else:
        print(f"Unknown provider: {provider}")
        print("Use: vultr, aliyun, or auto-detect commands (status, config, check)")
        print_usage()
        sys.exit(1)
