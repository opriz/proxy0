#!/usr/bin/env python3
"""
proxy_aliyun.py - Aliyun SWAS proxy server management tool

Usage:
  python proxy_aliyun.py list                # list all instances
  python proxy_aliyun.py deploy <ip>         # deploy xray to existing instance
  python proxy_aliyun.py config              # print the client config
  python proxy_aliyun.py status              # show the current server status
  python proxy_aliyun.py check               # probe IP connectivity
  python proxy_aliyun.py destroy             # destroy the current server
  python proxy_aliyun.py rebuild             # destroy and recreate (use when IP is blocked)
"""

import sys
import json
import os
import time
import subprocess
import hmac
import hashlib
import base64
from urllib.parse import quote
import socket
import uuid

import requests
import client_config as cc
from config import (
    XRAY_PORT, XRAY_SNI, ALIYUN_ACCESS_KEY, ALIYUN_ACCESS_SECRET, ALIYUN_PW
)

# ─── Aliyun API Client ───────────────────────────────────────────────────────

BASE_URL = "https://swas.cn-hongkong.aliyuncs.com"
REGION = "cn-hongkong"
STATE_FILE = ".proxy_state_aliyun.json"


def _sign(params: dict, method: str = "GET") -> str:
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    canonical = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
    string_to_sign = f"{method}&{quote('/', safe='')}&{quote(canonical, safe='')}"
    key = f"{ALIYUN_ACCESS_SECRET}&"
    signature = base64.b64encode(
        hmac.new(key.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    return signature


def _make_request(action: str, params: dict = None) -> dict:
    common_params = {
        "Action": action,
        "Version": "2020-06-01",
        "RegionId": REGION,
        "AccessKeyId": ALIYUN_ACCESS_KEY,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(int(time.time() * 1000)),
        "Format": "JSON",
    }
    if params:
        common_params.update(params)

    signature = _sign(common_params)
    common_params["Signature"] = signature

    sorted_params = sorted(common_params.items(), key=lambda x: x[0])
    query_string = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
    url = f"{BASE_URL}/?{query_string}"

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def _list_instances():
    resp = _make_request("ListInstances")
    instances = resp.get("Instances", [])
    if isinstance(instances, dict):
        return instances.get("Instance", [])
    return instances


def _delete_instance(instance_id: str):
    return _make_request("DeleteInstance", {"InstanceId": instance_id})


# ─── State Management ────────────────────────────────────────────────────────

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


# ─── Deployment Script ───────────────────────────────────────────────────────

def _generate_script(port: int, sni: str) -> tuple:
    """Generate deployment script for Alibaba Cloud Linux (yum-based)."""
    client_uuid = str(uuid.uuid4())

    script = f"""#!/bin/bash
set -e

yum install -y curl wget unzip jq openssl

bash <(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh) install

KEYS=$(xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep -iE 'privatekey|private key' | awk -F': ' '{{print $2}}' | tr -d ' ')
PUBLIC_KEY=$(echo "$KEYS" | grep -iE 'password|public key' | awk -F': ' '{{print $2}}' | tr -d ' ')
SHORT_ID=$(openssl rand -hex 4)
CLIENT_UUID="{client_uuid}"

cat > /usr/local/etc/xray/config.json << EOF
{{
  "log": {{"loglevel": "warning"}},
  "inbounds": [{{
    "listen": "0.0.0.0",
    "port": {port},
    "protocol": "vless",
    "settings": {{
      "clients": [{{"id": "$CLIENT_UUID", "flow": "xtls-rprx-vision"}}],
      "decryption": "none"
    }},
    "streamSettings": {{
      "network": "tcp",
      "security": "reality",
      "realitySettings": {{
        "show": false,
        "dest": "{sni}:443",
        "xver": 0,
        "serverNames": ["{sni}"],
        "privateKey": "$PRIVATE_KEY",
        "shortIds": ["$SHORT_ID"]
      }}
    }},
    "sniffing": {{"enabled": true, "destOverride": ["http", "tls"]}}
  }}],
  "outbounds": [
    {{"protocol": "freedom", "tag": "direct"}},
    {{"protocol": "blackhole", "tag": "block"}}
  ]
}}
EOF

cat > /root/proxy_info.json << EOF
{{
  "uuid": "$CLIENT_UUID",
  "public_key": "$PUBLIC_KEY",
  "short_id": "$SHORT_ID",
  "port": {port},
  "sni": "{sni}"
}}
EOF

mkdir -p /root/.ssh
chmod 700 /root/.ssh
cat > /root/.ssh/authorized_keys << 'SSHKEY'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFiDB8l5XVSwN94gj5K0INj5inFtYP/uBkh/ZW2+kKNi zhujian@zhujiandeMacBook-Air.local
SSHKEY
chmod 600 /root/.ssh/authorized_keys

sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd

systemctl enable xray
systemctl restart xray

if command -v firewall-cmd &>/dev/null; then
  firewall-cmd --permanent --add-port={port}/tcp
  firewall-cmd --reload
fi

echo "xray setup done"
"""
    return client_uuid, script


# ─── SSH Helpers ─────────────────────────────────────────────────────────────

def _ssh_run(ip: str, cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sshpass", "-p", ALIYUN_PW, "ssh",
         "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=10",
         f"root@{ip}", cmd],
        capture_output=True, text=True, timeout=timeout
    )


def _scp_upload(ip: str, local: str, remote: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sshpass", "-p", ALIYUN_PW, "scp",
         "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=10",
         local, f"root@{ip}:{remote}"],
        capture_output=True, text=True, timeout=timeout
    )


def _fetch_proxy_info(ip: str) -> dict:
    try:
        result = _ssh_run(ip, "cat /root/proxy_info.json")
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"  SSH failed: {e}")
    return {}


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_list():
    """List all instances."""
    print("Listing Aliyun SWAS instances...")
    instances = _list_instances()
    if not instances:
        print("No instances found")
        return
    for inst in instances:
        print(f"  ID: {inst.get('InstanceId')}")
        print(f"  Name: {inst.get('InstanceName')}")
        print(f"  IP: {inst.get('PublicIpAddress', {}).get('Ip', 'N/A')}")
        print(f"  Status: {inst.get('Status')}")
        print("-" * 40)


def cmd_deploy():
    """Deploy xray to an existing instance."""
    if len(sys.argv) < 3:
        # Try to find existing instances
        instances = _list_instances()
        if instances:
            print("Found existing instances:")
            for idx, inst in enumerate(instances, 1):
                ip = inst.get('PublicIpAddress', {}).get('Ip', 'N/A')
                print(f"  {idx}. {inst.get('InstanceName')} - {ip}")
            print("\nUsage: python proxy_aliyun.py deploy <ip>")
        else:
            print("No instances found. Create one at:")
            print("  https://swasnext.console.aliyun.com/buy")
        return

    ip = sys.argv[2]
    print(f"Deploying xray to {ip}...")

    if not ALIYUN_PW:
        print("Error: ALIYUN_PW not set in .env")
        return

    client_uuid, script = _generate_script(XRAY_PORT, XRAY_SNI)

    temp_script = "/tmp/deploy_xray.sh"
    with open(temp_script, "w") as f:
        f.write(script)

    print("Uploading deployment script...")
    result = _scp_upload(ip, temp_script, "/tmp/deploy_xray.sh")
    if result.returncode != 0:
        print(f"SCP failed: {result.stderr}")
        return

    print("Running deployment script (this may take 2-3 minutes)...")
    result = _ssh_run(ip, "bash /tmp/deploy_xray.sh", timeout=300)
    if result.returncode != 0:
        print(f"Deployment failed: {result.stderr}")
        return

    print("Waiting for xray to initialize...")
    time.sleep(10)

    proxy_info = _fetch_proxy_info(ip)
    if not proxy_info:
        print("Retrying in 30 seconds...")
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
        "region": "cn-hongkong",
    }
    _save_state(state)

    print("\n" + "="*60)
    _print_config(state)


def cmd_destroy():
    """Destroy the tracked instance."""
    state = _load_state()

    if not state.get("instance_id") or state.get("instance_id") == "manual":
        # List instances and let user choose
        instances = _list_instances()
        if not instances:
            print("No instances found")
            _clear_state()
            return

        print("Found instances:")
        for idx, inst in enumerate(instances, 1):
            ip = inst.get('PublicIpAddress', {}).get('Ip', 'N/A')
            print(f"  {idx}. {inst.get('InstanceName')} - {ip}")

        try:
            choice = int(input("\nSelect instance to delete (0 to cancel): ").strip())
            if 1 <= choice <= len(instances):
                inst = instances[choice - 1]
                confirm = input(f"Delete {inst.get('InstanceId')}? (yes/no): ")
                if confirm.lower() == "yes":
                    _delete_instance(inst["InstanceId"])
                    print(f"Deleted: {inst['InstanceId']}")
        except (ValueError, EOFError):
            pass

        _clear_state()
        return

    instance_id = state["instance_id"]
    print(f"Destroying instance: {instance_id}")
    try:
        _delete_instance(instance_id)
    except Exception as e:
        print(f"Error: {e}")
    _clear_state()
    print("Instance destroyed")


def cmd_rebuild():
    """Destroy and recreate the instance."""
    print("Rebuilding (destroy -> create new)...")
    cmd_destroy()
    time.sleep(5)
    print("\nCreate new instance at: https://swasnext.console.aliyun.com/buy")
    print("Then run: python proxy_aliyun.py deploy <ip>")


def cmd_config():
    """Print the client config."""
    state = _load_state()
    if not state.get("ip"):
        print("No instance tracked. Run: python proxy_aliyun.py deploy <ip>")
        return

    if not state.get("public_key"):
        proxy_info = _fetch_proxy_info(state["ip"])
        state.update(proxy_info)
        _save_state(state)

    _print_config(state)


def cmd_status():
    """Show instance status."""
    state = _load_state()
    if not state.get("ip"):
        print("No instance tracked. Run: python proxy_aliyun.py deploy <ip>")
        return

    print(f"IP          : {state['ip']}")
    print(f"Region      : {state.get('region', 'cn-hongkong')}")
    print(f"Port        : {state.get('port')}")
    print(f"UUID        : {state.get('uuid')}")


def cmd_check():
    """Check connectivity."""
    state = _load_state()
    ip = state.get("ip")
    if not ip:
        print("No instance tracked")
        return

    port = state.get("port", XRAY_PORT)
    print(f"Checking {ip}:{port}...")

    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.close()
        print(f"  TCP ✓ reachable")
    except Exception as e:
        print(f"  TCP ✗ unreachable ({e})")

    result = subprocess.run(["ping", "-c", "3", "-W", "2000", ip],
                           capture_output=True, text=True)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "avg" in line or "round-trip" in line:
                print(f"  {line.strip()}")
        print("  Ping ✓")
    else:
        print("  Ping ✗")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _print_config(state: dict):
    ip = state["ip"]
    uuid = state["uuid"]
    port = state["port"]
    public_key = state.get("public_key", "")
    short_id = state.get("short_id", "")
    sni = state["sni"]

    if not public_key:
        print("Warning: public_key empty. Wait and run: python proxy_aliyun.py config")
        return

    link = cc.vless_link(ip, uuid, port, public_key, short_id, sni)
    print("[Shadowrocket / v2rayN import link]")
    print(link)
    print()

    clash_yaml = cc.generate_clash_config(ip, uuid, port, public_key, short_id, sni)
    clash_file = "clash_config_aliyun.yaml"
    with open(clash_file, "w") as f:
        f.write(clash_yaml)
    print(f"[Clash Meta config] saved to: {clash_file}")
    print()
    print(clash_yaml)


COMMANDS = {
    "list": cmd_list,
    "deploy": cmd_deploy,
    "config": cmd_config,
    "status": cmd_status,
    "check": cmd_check,
    "destroy": cmd_destroy,
    "rebuild": cmd_rebuild,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    COMMANDS[sys.argv[1]]()
