---
name: proxy0
description: Manage VLESS+Reality proxy servers on Vultr and Aliyun. Use when the user wants to create, destroy, rebuild, or check proxy servers, or when the IP is blocked and needs rotation.
---

## Project Location
`/Users/zhujian/github/proxy0/`

## Supported Platforms

### Vultr (Global VPS)
- **Cost**: ~$5/month
- **IP Changes**: Unlimited
- **Latency**: 50-150ms
- **Best for**: Frequent IP rotation

### Aliyun SWAS (Hong Kong)
- **Cost**: ~30-40 RMB/month
- **IP Changes**: 3/month (free)
- **Latency**: 30-50ms
- **Best for**: Lower latency from China

---

## Vultr Commands

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

## Aliyun Commands

```bash
cd /Users/zhujian/github/proxy0

# First, buy a server at https://swasnext.console.aliyun.com/buy (Hong Kong region)
# Then deploy xray to it:

python3 proxy_aliyun.py deploy <ip>    # Deploy xray to existing instance
python3 proxy_aliyun.py list           # List all instances
python3 proxy_aliyun.py config         # Print VLESS link and Clash YAML
python3 proxy_aliyun.py status         # Show current instance info
python3 proxy_aliyun.py check          # Test IP connectivity
python3 proxy_aliyun.py destroy        # Destroy server
python3 proxy_aliyun.py rebuild        # Destroy + recreate
```

---

## Config

Edit `/Users/zhujian/github/proxy0/.env`:

### Vultr Settings
- `VULTR_REGION` — server region (default: `nrt` Tokyo). Options: `itm` Osaka, `icn` Seoul, `sgp` Singapore, `lax` LA
- `VULTR_API_KEY` — Vultr API key
- `VULTR_SSH_KEY_ID` — SSH key ID on Vultr

### Aliyun Settings
- `ALIYUN_ACCESS_KEY` — Aliyun Access Key
- `ALIYUN_ACCESS_SECRET` — Aliyun Access Secret
- `ALIYUN_PW` — Root password for Aliyun instances

---

## Common Tasks

**IP blocked → get new IP:**
```bash
# Vultr
python3 proxy.py rebuild

# Aliyun (limit: 3/month)
python3 proxy_aliyun.py rebuild
```

**Switch region (Vultr):**
1. Edit `.env`: set `VULTR_REGION=sgp`
2. Run `python3 proxy.py rebuild`

**Get client config again:**
```bash
# Vultr
python3 proxy.py config

# Aliyun
python3 proxy_aliyun.py config

# Outputs: vless://... link for Shadowrocket/v2rayN
# Saves: clash_config.yaml (Vultr) or clash_config_aliyun.yaml (Aliyun)
```

---

## Notes

- Protocol: VLESS + XTLS-Reality on port 443
- SNI masquerade target: `www.microsoft.com`
- Anthropic domains (claude.ai, anthropic.com) always route through proxy
- SSH password login disabled after deployment; only SSH key auth works
- State files (gitignored):
  - `.proxy_state.json` — Vultr instance state
  - `.proxy_state_aliyun.json` — Aliyun instance state
- Client requires Clash Meta (e.g., Clash Verge Rev) — standard Clash does NOT support VLESS
