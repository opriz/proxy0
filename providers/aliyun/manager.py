"""Aliyun SWAS lifecycle commands."""
import json
import subprocess
import sys
import time

from core import connectivity
from core.config import (
    ALIYUN_PW, ALIYUN_REGION, XRAY_PORT, XRAY_SNI,
    PROJECT_ROOT, state_path,
)
from providers.aliyun import api, deploy_script

PROVIDER_NAME = "Aliyun"
_REGION_SHORT = {"ap-southeast-1": "sg", "cn-hongkong": "hk"}.get(ALIYUN_REGION, ALIYUN_REGION)
STATE_FILE = state_path(f".proxy_state_aliyun_{_REGION_SHORT}.json")


def _load() -> dict:
    return connectivity.load_state(STATE_FILE)


def _save(state):
    connectivity.save_state(STATE_FILE, state)


def _clear():
    connectivity.clear_state(STATE_FILE)


def _ssh_run(ip: str, cmd: str, timeout: int = 30):
    return subprocess.run(
        ["sshpass", "-p", ALIYUN_PW, "ssh",
         "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
         f"root@{ip}", cmd],
        capture_output=True, text=True, timeout=timeout,
    )


def _scp_upload(ip: str, local: str, remote: str, timeout: int = 60):
    return subprocess.run(
        ["sshpass", "-p", ALIYUN_PW, "scp",
         "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
         local, f"root@{ip}:{remote}"],
        capture_output=True, text=True, timeout=timeout,
    )


def _fetch_proxy_info(ip: str) -> dict:
    try:
        result = _ssh_run(ip, "cat /root/proxy_info.json")
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"  SSH failed: {e}")
    return {}


def _ip_of(inst):
    ip = inst.get("PublicIpAddress", "N/A")
    if isinstance(ip, dict):
        return ip.get("Ip", "N/A")
    return ip


def cmd_list():
    print(f"Aliyun SWAS instances (region={ALIYUN_REGION}):")
    instances = api.list_instances()
    if not instances:
        print("  No instances found")
        return
    for inst in instances:
        print(f"  ID: {inst.get('InstanceId')}")
        print(f"  Name: {inst.get('InstanceName')}")
        print(f"  IP: {_ip_of(inst)}")
        print(f"  Status: {inst.get('Status')}")
        print("-" * 40)


def cmd_deploy():
    if len(sys.argv) < 4:
        instances = api.list_instances()
        if instances:
            print("Found instances:")
            for idx, inst in enumerate(instances, 1):
                print(f"  {idx}. {inst.get('InstanceName')} - {_ip_of(inst)}")
            print("\nUsage: python3 main.py aliyun deploy <ip>")
        else:
            print("No instances. Create one at: https://swasnext.console.aliyun.com/buy")
        return

    ip = sys.argv[3]
    print(f"Deploying to Aliyun {ip}...")

    if not ALIYUN_PW:
        print("Error: ALIYUN_PW not set in .env")
        return

    client_uuid, script = deploy_script.generate_script(XRAY_PORT, XRAY_SNI)

    temp_script = "/tmp/deploy_xray.sh"
    with open(temp_script, "w") as f:
        f.write(script)

    print("Uploading script...")
    result = _scp_upload(ip, temp_script, "/tmp/deploy_xray.sh")
    if result.returncode != 0:
        print(f"SCP failed: {result.stderr}")
        return

    print("Running deployment (~2-3 min)...")
    result = _ssh_run(ip, "bash /tmp/deploy_xray.sh", timeout=300)
    if result.returncode != 0:
        print(f"Deployment failed: {result.stderr}")
        return

    print("Waiting for xray...")
    time.sleep(10)
    proxy_info = _fetch_proxy_info(ip)
    if not proxy_info:
        time.sleep(30)
        proxy_info = _fetch_proxy_info(ip)

    state = {
        "instance_id": "manual",
        "ip": ip,
        "uuid": proxy_info.get("uuid", client_uuid),
        "public_key": proxy_info.get("public_key", ""),
        "short_id": proxy_info.get("short_id", ""),
        "port": XRAY_PORT,
        "sni": XRAY_SNI,
        "region": ALIYUN_REGION,
    }
    _save(state)
    print("\n" + "=" * 60)
    connectivity.print_config(state, PROVIDER_NAME, PROJECT_ROOT)


def cmd_config():
    state = _load()
    if not state.get("ip"):
        print("No Aliyun instance. Run: python3 main.py aliyun deploy <ip>")
        return
    if not state.get("public_key"):
        state.update(_fetch_proxy_info(state["ip"]))
        _save(state)
    connectivity.print_config(state, PROVIDER_NAME, PROJECT_ROOT)


def cmd_status():
    state = _load()
    if not state.get("ip"):
        print("No Aliyun instance tracked")
        return
    print(f"Provider    : Aliyun")
    print(f"IP          : {state['ip']}")
    print(f"Region      : {state.get('region', ALIYUN_REGION)}")
    print(f"Port        : {state.get('port')}")
    print(f"UUID        : {state.get('uuid')}")


def cmd_check():
    state = _load()
    ip = state.get("ip")
    if not ip:
        print("No Aliyun instance")
        return
    print(f"Checking Aliyun {ip}...")
    connectivity.check_connectivity(ip, state.get("port", XRAY_PORT))


def cmd_destroy():
    state = _load()
    if not state.get("instance_id") or state.get("instance_id") == "manual":
        instances = api.list_instances()
        if not instances:
            print("No Aliyun instances")
            _clear()
            return
        print("Found instances:")
        for idx, inst in enumerate(instances, 1):
            print(f"  {idx}. {inst.get('InstanceName')} - {_ip_of(inst)}")
        try:
            choice = int(input("Select to delete (0 to cancel): ").strip())
            if 1 <= choice <= len(instances):
                inst = instances[choice - 1]
                confirm = input(f"Delete {inst.get('InstanceId')}? (yes/no): ")
                if confirm.lower() == "yes":
                    api.delete_instance(inst["InstanceId"])
                    print(f"Deleted: {inst['InstanceId']}")
        except (ValueError, EOFError):
            pass
        _clear()
        return

    instance_id = state["instance_id"]
    print(f"Destroying: {instance_id}")
    try:
        api.delete_instance(instance_id)
    except Exception as e:
        print(f"Error: {e}")
    _clear()


def cmd_rebuild():
    print("Rebuilding Aliyun instance...")
    cmd_destroy()
    time.sleep(5)
    print("\nCreate new instance at: https://swasnext.console.aliyun.com/buy")
    print("Then run: python3 main.py aliyun deploy <ip>")


COMMANDS = {
    "list": cmd_list,
    "deploy": cmd_deploy,
    "config": cmd_config,
    "status": cmd_status,
    "check": cmd_check,
    "destroy": cmd_destroy,
    "rebuild": cmd_rebuild,
}
