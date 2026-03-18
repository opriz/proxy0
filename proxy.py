#!/usr/bin/env python3
"""
proxy.py - Vultr 代理服务器管理工具

用法:
  python proxy.py create              # 创建新服务器
  python proxy.py destroy             # 销毁当前服务器
  python proxy.py rebuild             # 销毁并重建（IP 被封时使用）
  python proxy.py config              # 显示客户端配置
  python proxy.py status              # 查看当前服务器状态
  python proxy.py check               # 检测 IP 是否可用
  python proxy.py regions             # 列出可用地区
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


# ─── 状态文件操作 ────────────────────────────────────────────────────────────

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


# ─── 核心操作 ────────────────────────────────────────────────────────────────

def cmd_create():
    state = load_state()
    if state.get("instance_id"):
        print(f"已有实例运行中: {state['instance_id']} / {state.get('ip')}")
        print("如需重建请运行: python proxy.py rebuild")
        return

    print(f"正在创建实例 (地区: {REGION}, 套餐: {PLAN})...")
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
    print(f"实例已创建: {instance_id}")
    print("等待实例就绪（约 2-3 分钟）...")

    inst = vultr.wait_for_active(instance_id)
    ip = inst["main_ip"]
    print(f"实例就绪! IP: {ip}")

    # 等待 xray 安装完成（cloud-init 需要时间）
    print("等待 xray 初始化（约 60 秒）...")
    time.sleep(60)

    # 从服务端读取 proxy_info.json
    print("读取服务端配置...")
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
        # 尝试从 Vultr 查找
        instances = vultr.list_instances(label=INSTANCE_LABEL)
        if not instances:
            print("没有找到运行中的实例")
            return
        for inst in instances:
            print(f"删除实例: {inst['id']} / {inst.get('main_ip')}")
            vultr.delete_instance(inst["id"])
        clear_state()
        print("已销毁所有实例")
        return

    instance_id = state["instance_id"]
    print(f"正在销毁实例: {instance_id} / {state.get('ip')}")
    vultr.delete_instance(instance_id)
    clear_state()
    print("实例已销毁")


def cmd_rebuild():
    print("开始重建（销毁旧实例 → 创建新实例）...")
    cmd_destroy()
    time.sleep(5)
    cmd_create()


def cmd_config():
    state = load_state()
    if not state.get("ip"):
        print("没有运行中的实例，请先运行: python proxy.py create")
        return
    if not state.get("public_key"):
        print("缺少 public_key，尝试从服务端重新读取...")
        proxy_info = fetch_proxy_info(state["ip"])
        state.update(proxy_info)
        save_state(state)
    print_config(state)


def cmd_status():
    state = load_state()
    if not state.get("instance_id"):
        print("没有本地状态，尝试从 Vultr API 查询...")
        instances = vultr.list_instances(label=INSTANCE_LABEL)
        if not instances:
            print("没有找到运行中的实例")
        for inst in instances:
            print(f"  ID: {inst['id']}")
            print(f"  IP: {inst.get('main_ip')}")
            print(f"  状态: {inst.get('status')} / {inst.get('power_status')}")
        return

    print(f"实例 ID : {state['instance_id']}")
    print(f"IP      : {state.get('ip')}")
    print(f"地区    : {state.get('region')}")
    print(f"端口    : {state.get('port')}")
    print(f"UUID    : {state.get('uuid')}")

    # 从 API 获取实时状态
    try:
        inst = vultr.get_instance(state["instance_id"])
        print(f"API状态 : {inst.get('status')} / {inst.get('power_status')}")
    except Exception as e:
        print(f"API查询失败: {e}")


def cmd_check():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("没有运行中的实例")
        return

    print(f"检测 IP: {ip}")

    # 方法1: TCP 连通性
    port = state.get("port", XRAY_PORT)
    import socket
    try:
        sock = socket.create_connection((ip, port), timeout=5)
        sock.close()
        print(f"  TCP {ip}:{port} ✓ 可连接")
    except Exception as e:
        print(f"  TCP {ip}:{port} ✗ 不可连接 ({e})")

    # 方法2: ping
    result = subprocess.run(
        ["ping", "-c", "3", "-W", "2000", ip],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        # 提取延迟
        for line in result.stdout.splitlines():
            if "avg" in line or "round-trip" in line:
                print(f"  Ping: {line.strip()}")
        print(f"  Ping ✓")
    else:
        print(f"  Ping ✗ IP 可能被封锁，建议运行: python proxy.py rebuild")


def cmd_regions():
    print("获取可用地区列表...")
    regions = vultr.list_regions()
    for r in sorted(regions, key=lambda x: x["id"]):
        print(f"  {r['id']:8s} {r['city']}, {r['country']}")


# ─── 辅助函数 ────────────────────────────────────────────────────────────────

def fetch_proxy_info(ip: str) -> dict:
    """通过 SSH 从服务端读取 /root/proxy_info.json"""
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
            print(f"  SSH 读取失败: {result.stderr.strip()}")
    except Exception as e:
        print(f"  SSH 连接失败: {e}")
    return {}


def print_config(state: dict):
    ip = state["ip"]
    uuid = state["uuid"]
    port = state["port"]
    public_key = state.get("public_key", "")
    short_id = state.get("short_id", "")
    sni = state["sni"]

    if not public_key:
        print("警告: public_key 为空，配置可能不完整")
        print("请等待服务器初始化完成后重新运行: python proxy.py config")
        return

    # VLESS 链接
    link = cc.vless_link(ip, uuid, port, public_key, short_id, sni)
    print("【Shadowrocket / v2rayN 导入链接】")
    print(link)
    print()

    # Clash 配置
    clash_yaml = cc.generate_clash_config(ip, uuid, port, public_key, short_id, sni)
    clash_file = "clash_config.yaml"
    with open(clash_file, "w") as f:
        f.write(clash_yaml)
    print(f"【Clash Meta 配置文件】已保存到: {clash_file}")
    print()
    print(clash_yaml)


# ─── 入口 ────────────────────────────────────────────────────────────────────

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
