"""Build client-side share links and Clash Meta config from server params."""
import yaml


def vless_link(ip: str, uuid: str, port: int, public_key: str,
               short_id: str, sni: str, remark: str = "proxy0") -> str:
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
    proxy = clash_proxy(ip, uuid, port, public_key, short_id, sni)
    config = {
        "mixed-port": 7890,
        "allow-lan": True,
        "bind-address": "*",
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "external-controller": "0.0.0.0:9090",
        "geodata-mode": False,
        "geo-auto-update": False,
        "geodata-loader": "standard",
        "dns": {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "redir-host",
            "default-nameserver": ["223.5.5.5", "119.29.29.29"],
            "nameserver": [
                "https://doh.pub/dns-query",
                "https://dns.alidns.com/dns-query",
            ],
            "proxy-server-nameserver": ["223.5.5.5"],
            "nameserver-policy": {
                "geosite:cn,private,apple-cn": ["223.5.5.5", "119.29.29.29"],
                "geosite:geolocation-!cn,gfw,greatfire": [
                    "https://1.1.1.1/dns-query",
                    "https://dns.google/dns-query",
                ],
            },
        },
        "proxies": [proxy],
        "proxy-groups": [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": ["proxy0", "DIRECT"],
            },
            {
                "name": "Final",
                "type": "select",
                "proxies": ["Proxy", "DIRECT"],
            },
        ],
        "rules": [
            # 强制走代理（域名优先）
            "DOMAIN-SUFFIX,anthropic.com,Proxy",
            "DOMAIN-SUFFIX,claude.ai,Proxy",
            "DOMAIN-SUFFIX,claudeusercontent.com,Proxy",
            "DOMAIN-SUFFIX,anthropic.io,Proxy",

            # 广告 / 隐私拦截
            "GEOSITE,category-ads-all,REJECT",

            # 局域网 / 私有
            "GEOSITE,private,DIRECT",
            "GEOIP,lan,DIRECT,no-resolve",
            "GEOIP,private,DIRECT,no-resolve",

            # Tailscale (CGNAT 段 + MagicDNS)
            "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
            "DOMAIN-SUFFIX,ts.net,DIRECT",

            # 国内直连
            "GEOSITE,cn,DIRECT",
            "GEOSITE,apple-cn,DIRECT",
            "GEOSITE,microsoft@cn,DIRECT",
            "GEOSITE,category-games@cn,DIRECT",
            "GEOIP,cn,DIRECT,no-resolve",

            # 国外强制代理
            "GEOSITE,geolocation-!cn,Proxy",
            "GEOSITE,gfw,Proxy",
            "GEOSITE,greatfire,Proxy",

            # 兜底
            "MATCH,Final",
        ],
    }
    return yaml.dump(config, allow_unicode=True, sort_keys=False)
