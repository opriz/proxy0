# proxy0

One-click VLESS+Reality proxy server on Vultr, with fast destroy-and-rebuild for IP rotation when the server gets blocked.

中文版本：[README.md](README.md)

---

## How It Works

The local script calls the Vultr API to create a VPS. xray is automatically installed and configured via `user_data` (cloud-init) on first boot. Once the instance is ready, the script reads the generated Reality public key and related fields over SSH and produces the client config. When the IP gets blocked, one command destroys and rebuilds the instance — a new IP in about 4 minutes.

---

## Prerequisites

- Python 3.8+
- A Vultr account and API key
- A local SSH keypair (`~/.ssh/id_ed25519` or `id_rsa`) uploaded to Vultr
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
VULTR_API_KEY=your_vultr_api_key
VULTR_SSH_KEY_ID=your_ssh_key_id   # from Vultr console: Account → SSH Keys
VULTR_REGION=icn                   # defaults to Seoul; see region list below
```

**Getting the SSH Key ID:**
Upload your local public key in the Vultr console under Account → SSH Keys, then copy the displayed ID into `.env`.

### 3. Create the server

```bash
python3 proxy.py create
```

When it finishes, the script prints an import link for Shadowrocket / v2rayN and saves a Clash config to `clash_config.yaml`.

---

## Commands

| Command | Description |
|---------|-------------|
| `python3 proxy.py create` | Create a server and print the client config |
| `python3 proxy.py destroy` | Destroy the current server (stops billing) |
| `python3 proxy.py rebuild` | Destroy and recreate — use when the IP is blocked |
| `python3 proxy.py config` | Re-print the client config (VLESS link + Clash YAML) |
| `python3 proxy.py status` | Show the current server status |
| `python3 proxy.py check` | Probe the IP (TCP connect + ping) |
| `python3 proxy.py regions` | List all available regions |

---

## Recommended Regions

| Code | Region | Latency (from China) |
|------|--------|----------------------|
| `nrt` | Tokyo | ~50ms |
| `itm` | Osaka | ~55ms |
| `icn` | Seoul | ~60ms |
| `sgp` | Singapore | ~80ms |
| `lax` | Los Angeles | ~150ms |

To switch regions, change `VULTR_REGION` in `.env` and run `python3 proxy.py rebuild`. The full list is available via `python3 proxy.py regions`.

---

## Defaults

- Plan: `vc2-1c-1gb` (about $5/month)
- OS: Debian 12 x64
- Protocol: VLESS + XTLS-Reality
- Port: 443
- SNI target: `www.microsoft.com`

Edit `config.py` to change any of these.

---

## File Layout

```
proxy0/
├── proxy.py          # main entry, all commands
├── vultr.py          # Vultr API v2 wrapper
├── cloudinit.py      # generates the server-side cloud-init script
├── client_config.py  # builds the VLESS link and Clash YAML
├── config.py         # reads config from .env / environment
├── requirements.txt
├── .env.example      # environment variable template
└── .gitignore
```

Generated at runtime:

- `.proxy_state.json` — current instance state (ID, IP, UUID, Reality public key, ...)
- `clash_config.yaml` — Clash Meta config

---

## Security Notes

- `.env` and `.proxy_state.json` are in `.gitignore` and never committed
- The server disables SSH password login; only key-based auth is allowed
- xray only listens on port 443
- Reality needs no certificates and produces traffic that looks like real HTTPS
