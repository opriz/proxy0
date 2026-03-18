import yaml
import base64
import json


def vless_link(ip: str, uuid: str, port: int, public_key: str,
               short_id: str, sni: str, remark: str = "proxy0") -> str:
    """生成 VLESS Reality 分享链接"""
    params = (
        f"type=tcp"
        f"&security=reality"
        f"&pbk={public_key}"
        f"&fp=chrome"
        f"&sni={sni}"
        f"&sid={short_id}"
        f"&flow=xtls-rprx-vision"
    )
    return f"vless://{uuid}@{ip}:{port}?{params}#{remark}"


def clash_proxy(ip: str, uuid: str, port: int, public_key: str,
                short_id: str, sni: str, name: str = "proxy0") -> dict:
    """生成 Clash Meta 代理配置"""
    return {
        "name": name,
        "type": "vless",
        "server": ip,
        "port": port,
        "uuid": uuid,
        "network": "tcp",
        "tls": True,
        "udp": True,
        "flow": "xtls-rprx-vision",
        "reality-opts": {
            "public-key": public_key,
            "short-id": short_id,
        },
        "servername": sni,
        "client-fingerprint": "chrome",
    }


def generate_clash_config(ip: str, uuid: str, port: int, public_key: str,
                           short_id: str, sni: str) -> str:
    """生成完整的 Clash Meta 配置文件内容"""
    proxy = clash_proxy(ip, uuid, port, public_key, short_id, sni)
    config = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "external-controller": "127.0.0.1:9090",
        "proxies": [proxy],
        "proxy-groups": [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": ["proxy0", "DIRECT"],
            }
        ],
        "rules": [
            "GEOIP,CN,DIRECT",
            "MATCH,Proxy",
        ],
    }
    return yaml.dump(config, allow_unicode=True, sort_keys=False)
