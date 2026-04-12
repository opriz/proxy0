---
name: proxy0
description: Manage VLESS+Reality proxy servers on Vultr and Aliyun. Use when the user wants to create, destroy, rebuild, or check proxy servers, or when the IP is blocked and needs rotation.
---

## Project Location
`/Users/zhujian/github/proxy0/`

## Unified Entry (Recommended)

Use `main.py` with provider prefix:

```bash
cd /Users/zhujian/github/proxy0

# Vultr
python3 main.py vultr create              # Create server
python3 main.py vultr destroy             # Destroy server
python3 main.py vultr rebuild             # Rebuild (new IP)
python3 main.py vultr config              # Show config
python3 main.py vultr status              # Show status
python3 main.py vultr check               # Check connectivity
python3 main.py vultr regions             # List regions

# Aliyun
python3 main.py aliyun list               # List instances
python3 main.py aliyun deploy <ip>        # Deploy to instance
python3 main.py aliyun config             # Show config
python3 main.py aliyun status             # Show status
python3 main.py aliyun check              # Check connectivity
python3 main.py aliyun destroy            # Destroy server
python3 main.py aliyun rebuild            # Rebuild (new IP)

# Auto-detect (no provider prefix)
python3 main.py status                    # Show all configured servers
python3 main.py config                    # Show all configs
python3 main.py check                     # Check all servers
```

## Supported Platforms

| Platform | Cost | IP Changes | Latency | Best For |
|----------|------|------------|---------|----------|
| **Vultr** | ~$5/month | Unlimited | 50-150ms | Frequent IP rotation |
| **Aliyun SWAS** | ~30-40 RMB/month | 3/month (free) | 30-50ms | Lower latency from China |

## Config

Edit `/Users/zhujian/github/proxy0/.env`:

```env
# Vultr
VULTR_API_KEY=your_key
VULTR_SSH_KEY_ID=your_ssh_key_id
VULTR_REGION=icn

# Aliyun
ALIYUN_ACCESS_KEY=your_key
ALIYUN_ACCESS_SECRET=your_secret
ALIYUN_PW=your_root_password
```

## Common Tasks

**IP blocked → get new IP:**
```bash
# Vultr (unlimited)
python3 main.py vultr rebuild

# Aliyun (3/month)
python3 main.py aliyun rebuild
```

**Switch region (Vultr):**
1. Edit `.env`: set `VULTR_REGION=sgp`
2. Run `python3 main.py vultr rebuild`

**Get client config:**
```bash
python3 main.py vultr config      # Vultr
python3 main.py aliyun config     # Aliyun
python3 main.py config            # Auto-detect

# Outputs: vless://... link
# Saves: clash_config_vultr.yaml or clash_config_aliyun.yaml
```

**Check all servers:**
```bash
python3 main.py check
```

## Aliases

For convenience, add to `~/.zshrc` or `~/.bashrc`:

```bash
alias vultr='python3 ~/github/proxy0/main.py vultr'
alias aliyun='python3 ~/github/proxy0/main.py aliyun'
alias proxy='python3 ~/github/proxy0/main.py'
```

Then use: `vultr status`, `aliyun config`, `proxy check`

## Notes

- Protocol: VLESS + XTLS-Reality on port 443
- SNI masquerade: `www.microsoft.com`
- Anthropic domains (claude.ai, anthropic.com) always route through proxy
- Requires Clash Meta (standard Clash does NOT support VLESS)
- State files (gitignored):
  - `.proxy_state.json` — Vultr
  - `.proxy_state_aliyun.json` — Aliyun
