---
name: proxy0
description: Manage a VLESS+Reality proxy server on Vultr. Use when the user wants to create, destroy, rebuild, or check the proxy server, or when the IP is blocked and needs rotation.
---

## Project Location
`/Users/zhujian/github/proxy0/`

## Commands

Run all commands from the project directory:

```bash
cd /Users/zhujian/github/proxy0

python3 proxy.py create    # Create server, outputs VLESS link + clash_config.yaml
python3 proxy.py destroy   # Destroy server (stop billing)
python3 proxy.py rebuild   # Destroy + recreate (use when IP is blocked)
python3 proxy.py config    # Print VLESS link and Clash YAML again
python3 proxy.py status    # Show current instance info
python3 proxy.py check     # Test IP connectivity (TCP + ping)
python3 proxy.py regions   # List available regions
```

## Config

Edit `/Users/zhujian/github/proxy0/.env` to change settings:
- `VULTR_REGION` — server region (default: `nrt` Tokyo). Options: `itm` Osaka, `icn` Seoul, `sgp` Singapore, `lax` LA
- `VULTR_API_KEY` — Vultr API key
- `VULTR_SSH_KEY_ID` — SSH key ID on Vultr

## Common Tasks

**IP blocked → get new IP:**
```bash
python3 proxy.py rebuild
```

**Switch region:**
1. Edit `.env`: set `VULTR_REGION=sgp`
2. Run `python3 proxy.py rebuild`

**Get client config again:**
```bash
python3 proxy.py config
# Outputs: vless://... link for Shadowrocket/v2rayN
# Saves: clash_config.yaml for Clash Meta
```

## Notes
- Server cost: $5/month (Tokyo). Billed by hour, destroy when not needed.
- xray runs as systemd service on port 443, protocol: VLESS + XTLS-Reality
- SSH password login is disabled; only SSH key auth works
- State stored in `.proxy_state.json` (gitignored)
- Client requires Clash Meta (e.g. Clash Verge Rev) — standard Clash does NOT support VLESS
