import requests
import time
from config import VULTR_API_KEY

BASE_URL = "https://api.vultr.com/v2"

def _headers():
    return {
        "Authorization": f"Bearer {VULTR_API_KEY}",
        "Content-Type": "application/json",
    }

def _get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()

def _post(path, data):
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=data)
    if not r.ok:
        raise RuntimeError(f"POST {path} {r.status_code}: {r.text}")
    return r.json()

def _delete(path):
    r = requests.delete(f"{BASE_URL}{path}", headers=_headers())
    r.raise_for_status()

def list_instances(label=None):
    data = _get("/instances")
    instances = data.get("instances", [])
    if label:
        instances = [i for i in instances if i.get("label") == label]
    return instances

def get_instance(instance_id):
    data = _get(f"/instances/{instance_id}")
    return data["instance"]

def create_instance(region, plan, os_id, label, user_data, hostname=None, ssh_key_ids=None):
    payload = {
        "region": region,
        "plan": plan,
        "os_id": os_id,
        "label": label,
        "hostname": hostname or label,
        "user_data": user_data,
        "backups": "disabled",
    }
    if ssh_key_ids:
        payload["sshkey_id"] = ssh_key_ids
    data = _post("/instances", payload)
    return data["instance"]

def delete_instance(instance_id):
    _delete(f"/instances/{instance_id}")

def wait_for_active(instance_id, timeout=300, interval=10):
    """Wait until the instance becomes active and has an IP."""
    start = time.time()
    while time.time() - start < timeout:
        inst = get_instance(instance_id)
        status = inst.get("status")
        power = inst.get("power_status")
        ip = inst.get("main_ip", "")
        print(f"  Status: {status} / {power} / IP: {ip}")
        if status == "active" and power == "running" and ip and ip != "0.0.0.0":
            return inst
        time.sleep(interval)
    raise TimeoutError(f"Instance {instance_id} not ready within {timeout}s")

def list_regions():
    data = _get("/regions")
    return data.get("regions", [])

def list_plans(region=None):
    params = {"type": "vc2"}
    if region:
        params["per_page"] = 500
    data = _get("/plans", params=params)
    plans = data.get("plans", [])
    if region:
        plans = [p for p in plans if region in p.get("locations", [])]
    return plans
