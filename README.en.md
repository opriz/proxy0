# proxy0

One-click VLESS+Reality proxy server deployment supporting **Vultr** and **Aliyun** dual platforms, with fast destroy-and-rebuild for IP rotation when the server gets blocked.

中文版本：[README.md](README.md)

---

## How It Works

The local script calls the cloud provider API to create a VPS. xray is automatically installed and configured via `user_data` (cloud-init) on first boot. Once the instance is ready, the script reads the generated Reality public key and related fields over SSH and produces the client config. When the IP gets blocked, one command destroys and rebuilds the instance — a new IP in about 4 minutes.

---

## Prerequisites

- Python 3.8+
- A Vultr account **or** Aliyun account
- Client: Clash Meta (recommended: [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)) or Shadowrocket / v2rayN

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Vultr (optional)
VULTR_API_KEY=your_vultr_api_key
VULTR_SSH_KEY_ID=your_ssh_key_id
VULTR_REGION=icn

# Aliyun (optional)
ALIYUN_ACCESS_KEY=your_aliyun_ak
ALIYUN_ACCESS_SECRET=your_aliyun_sk
ALIYUN_PW=your_root_password
```

**Getting the Vultr SSH Key ID:**
Upload your local public key in the Vultr console under Account → SSH Keys, then copy the displayed ID into `.env`.

**Aliyun Password:**
Reset the server password in Aliyun SWAS console and fill it in `ALIYUN_PW`.

---

## Vultr Guide

### Create Server

```bash
python3 proxy.py create
```

### Commands

| Command | Description |
|---------|-------------|
| `python3 proxy.py create` | Create a server and print the client config |
| `python3 proxy.py destroy` | Destroy the current server (stops billing) |
| `python3 proxy.py rebuild` | Destroy and recreate — use when the IP is blocked |
| `python3 proxy.py config` | Re-print the client config |
| `python3 proxy.py status` | Show the current server status |
| `python3 proxy.py check` | Probe the IP (TCP connect + ping) |
| `python3 proxy.py regions` | List all available regions |

### Recommended Regions

| Code | Region | Latency (from China) |
|------|--------|----------------------|
| `nrt` | Tokyo | ~50ms |
| `itm` | Osaka | ~55ms |
| `icn` | Seoul | ~60ms |
| `sgp` | Singapore | ~80ms |
| `lax` | Los Angeles | ~150ms |

---

## Aliyun Guide

### Buy a Server

1. Visit https://swasnext.console.aliyun.com/buy
2. Select: **Hong Kong (China)** region
3. Image: **Alibaba Cloud Linux** or **Debian 12**
4. Plan: Entry-level (~$4.5/month) or Speed (unlimited traffic ~$6/month)
5. Save the **public IP** and reset **root password** in console

### Deploy Proxy

```bash
# Method 1: Deploy to specific IP
python3 proxy_aliyun.py deploy 8.x.x.x

# Method 2: List instances and select
python3 proxy_aliyun.py deploy
```

### Commands

| Command | Description |
|---------|-------------|
| `python3 proxy_aliyun.py list` | List all instances |
| `python3 proxy_aliyun.py deploy <ip>` | Deploy xray to specified instance |
| `python3 proxy_aliyun.py config` | Show client config |
| `python3 proxy_aliyun.py status` | Show current server status |
| `python3 proxy_aliyun.py check` | Check IP connectivity |
| `python3 proxy_aliyun.py destroy` | Destroy current server |
| `python3 proxy_aliyun.py rebuild` | Destroy and rebuild |

### Aliyun Features

- **Low latency**: ~30-50ms to Hong Kong (faster than Vultr Korea)
- **High bandwidth**: 200Mbps peak (Speed plan)
- **IP change limit**: 3 free IP changes per month

---

## Defaults

- Plan: Lowest tier (~$5/month)
- Protocol: **VLESS + XTLS-Reality**
- Port: **443**
- SNI target: `www.microsoft.com`
- Rules: Anthropic domains always go through proxy

Edit `config.py` to change any of these.

---

## File Layout

```
proxy0/
├── proxy.py              # Vultr main entry
├── proxy_aliyun.py       # Aliyun main entry
├── vultr.py              # Vultr API v2 wrapper
├── cloudinit.py          # generates the server-side cloud-init script
├── client_config.py      # builds the VLESS link and Clash YAML
├── config.py             # reads config from .env / environment
├── requirements.txt
├── .env.example          # environment variable template
└── .gitignore
```

Generated at runtime (in `.gitignore`):

- `.proxy_state.json` — Vultr instance state
- `.proxy_state_aliyun.json` — Aliyun instance state
- `clash_config.yaml` — Vultr Clash config
- `clash_config_aliyun.yaml` — Aliyun Clash config

---

## Security Notes

- `.env` and all state files are in `.gitignore` and never committed
- The server disables SSH password login after deployment; only key-based auth is allowed
- xray only listens on port 443
- Reality needs no certificates and produces traffic that looks like real HTTPS

---

## Platform Comparison

| Feature | Vultr | Aliyun |
|---------|-------|--------|
| Price | $5/month | $4.5-6/month |
| Latency | 50-150ms | 30-50ms |
| Bandwidth | 1Gbps | 200Mbps |
| Traffic | Unlimited | 500GB-Unlimited |
| IP Changes | Unlimited | 3/month |
| Stability | High | High |
| Block Risk | Low | Medium |

**Recommendation**: Users in China should prefer **Aliyun Hong Kong** for lower latency; choose **Vultr** if you need frequent IP changes.
