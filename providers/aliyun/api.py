"""Aliyun SWAS (Simple Application Server) API wrapper.

Uses the documented HMAC-SHA1 query-signing scheme so we don't need to bring in
the full aliyun-python-sdk. See:
  https://help.aliyun.com/document_detail/220287.html
"""
import base64
import hashlib
import hmac
import time
from urllib.parse import quote

import requests

from core.config import ALIYUN_ACCESS_KEY, ALIYUN_ACCESS_SECRET, ALIYUN_REGION

REGION = ALIYUN_REGION
BASE_URL = f"https://swas.{REGION}.aliyuncs.com"


def _sign(params: dict, method: str = "GET") -> str:
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    canonical = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
    string_to_sign = f"{method}&{quote('/', safe='')}&{quote(canonical, safe='')}"
    key = f"{ALIYUN_ACCESS_SECRET}&"
    return base64.b64encode(
        hmac.new(key.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()


def _request(action: str, params: dict = None) -> dict:
    common = {
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
        common.update(params)
    common["Signature"] = _sign(common)

    sorted_params = sorted(common.items(), key=lambda x: x[0])
    qs = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
    r = requests.get(f"{BASE_URL}/?{qs}", timeout=30)
    r.raise_for_status()
    return r.json()


def list_instances():
    resp = _request("ListInstances")
    instances = resp.get("Instances", [])
    if isinstance(instances, dict):
        return instances.get("Instance", [])
    return instances


def delete_instance(instance_id: str):
    return _request("DeleteInstance", {"InstanceId": instance_id})


def reboot_instance(instance_id: str):
    return _request("RebootInstance", {"InstanceId": instance_id})
