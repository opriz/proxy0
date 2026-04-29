"""Vultr lifecycle commands: create / destroy / rebuild / config / status / check."""
import json
import subprocess
import time

from core import connectivity
from core.config import (
    INSTANCE_LABEL, VULTR_REGION, VULTR_PLAN, VULTR_OS_ID,
    VULTR_SSH_KEY_ID, XRAY_PORT, XRAY_SNI, PROJECT_ROOT, state_path,
)
from providers.vultr import api, cloudinit

PROVIDER_NAME = "Vultr"
STATE_FILE = state_path(".proxy_state_vultr.json")


# Backwards-compatible state path: older versions used .proxy_state.json
def _load() -> dict:
    s = connectivity.load_state(STATE_FILE)
    if s:
        return s
    legacy = state_path(".proxy_state.json")
    return connectivity.load_state(legacy)


def _save(state):
    connectivity.save_state(STATE_FILE, state)


def _clear():
    connectivity.clear_state(STATE_FILE)
    connectivity.clear_state(state_path(".proxy_state.json"))


def _fetch_proxy_info(ip: str) -> dict:
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
             f"root@{ip}", "cat /root/proxy_info.json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"  SSH read failed: {result.stderr.strip()}")
    except Exception as e:
        print(f"  SSH connection failed: {e}")
    return {}


def cmd_create():
    state = _load()
    if state.get("instance_id"):
        print(f"Instance already running: {state['instance_id']} / {state.get('ip')}")
        print("To recreate: python3 main.py vultr rebuild")
        return

    print(f"Creating Vultr instance (region={VULTR_REGION}, plan={VULTR_PLAN})...")
    user_data = cloudinit.generate_user_data(XRAY_PORT, XRAY_SNI)
    client_uuid = cloudinit.get_client_uuid_from_script(user_data)

    inst = api.create_instance(
        region=VULTR_REGION, plan=VULTR_PLAN, os_id=VULTR_OS_ID,
        label=INSTANCE_LABEL, user_data=user_data,
        ssh_key_ids=[VULTR_SSH_KEY_ID] if VULTR_SSH_KEY_ID else None,
    )
    instance_id = inst["id"]
    print(f"Instance created: {instance_id}. Waiting for active state (~2-3 min)...")

    inst = api.wait_for_active(instance_id)
    ip = inst["main_ip"]
    print(f"Instance ready! IP: {ip}")

    print("Waiting 60s for xray to initialize...")
    time.sleep(60)

    proxy_info = _fetch_proxy_info(ip)

    state = {
        "instance_id": instance_id,
        "ip": ip,
        "uuid": proxy_info.get("uuid", client_uuid),
        "public_key": proxy_info.get("public_key", ""),
        "short_id": proxy_info.get("short_id", ""),
        "port": XRAY_PORT,
        "sni": XRAY_SNI,
        "region": VULTR_REGION,
    }
    _save(state)
    print("\n" + "=" * 60)
    connectivity.print_config(state, PROVIDER_NAME, PROJECT_ROOT)


def cmd_destroy():
    state = _load()
    if not state.get("instance_id"):
        instances = api.list_instances(label=INSTANCE_LABEL)
        if not instances:
            print("No Vultr instance found")
            return
        for inst in instances:
            print(f"Deleting: {inst['id']} / {inst.get('main_ip')}")
            api.delete_instance(inst["id"])
        _clear()
        print("All instances destroyed")
        return

    instance_id = state["instance_id"]
    print(f"Destroying: {instance_id} / {state.get('ip')}")
    api.delete_instance(instance_id)
    _clear()
    print("Instance destroyed")


def cmd_rebuild():
    print("Rebuilding Vultr instance...")
    cmd_destroy()
    time.sleep(5)
    cmd_create()


def cmd_config():
    state = _load()
    if not state.get("ip"):
        print("No Vultr instance. Run: python3 main.py vultr create")
        return
    if not state.get("public_key"):
        print("public_key missing, re-reading from server...")
        state.update(_fetch_proxy_info(state["ip"]))
        _save(state)
    connectivity.print_config(state, PROVIDER_NAME, PROJECT_ROOT)


def cmd_status():
    state = _load()
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
        inst = api.get_instance(state["instance_id"])
        print(f"API Status  : {inst.get('status')} / {inst.get('power_status')}")
    except Exception as e:
        print(f"API query failed: {e}")


def cmd_check():
    state = _load()
    ip = state.get("ip")
    if not ip:
        print("No Vultr instance")
        return
    print(f"Checking Vultr {ip}...")
    connectivity.check_connectivity(ip, state.get("port", XRAY_PORT))


def cmd_regions():
    print("Available Vultr regions:")
    for r in sorted(api.list_regions(), key=lambda x: x["id"]):
        print(f"  {r['id']:8s} {r['city']}, {r['country']}")


COMMANDS = {
    "create": cmd_create,
    "destroy": cmd_destroy,
    "rebuild": cmd_rebuild,
    "config": cmd_config,
    "status": cmd_status,
    "check": cmd_check,
    "regions": cmd_regions,
}
