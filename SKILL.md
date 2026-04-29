---
name: proxy0
description: Provision, deploy, rotate, and tear down personal VLESS+Reality (xray) proxy servers across multiple cloud providers (Vultr, Aliyun SWAS). Invoke when the user wants to spin up a proxy, replace a blocked IP, fetch their client config (vless:// link or Clash YAML), check connectivity, or list/destroy existing instances. Also use when the user is setting up the tool for the first time and needs guidance on creating cloud API credentials.
---

# proxy0 — Multi-provider VLESS+Reality proxy manager

A small Python tool that automates the lifecycle of personal proxy VMs:
**create → deploy xray → emit client config → rotate IP → destroy**.
Each cloud provider lives in its own module so adding a new one is mechanical.

## Repo layout

```
proxy0/
├── main.py                      ← unified entry point (dispatches to providers)
├── core/                        ← provider-agnostic shared code
│   ├── config.py                  — loads .env, exposes settings
│   ├── client_config.py           — builds vless:// links + Clash YAML
│   └── connectivity.py            — state files, TCP/ping check, print_config
├── providers/
│   ├── vultr/
│   │   ├── api.py                 — Vultr REST wrapper
│   │   ├── cloudinit.py           — Debian/apt deployment script
│   │   ├── manager.py             — create/destroy/rebuild/config/status/check/regions
│   │   └── SETUP.md               — how to obtain VULTR_API_KEY etc.
│   └── aliyun/
│       ├── api.py                 — Aliyun SWAS HMAC-signed wrapper
│       ├── deploy_script.py       — Alibaba Cloud Linux/yum deployment script
│       ├── manager.py             — list/deploy/destroy/rebuild/config/status/check
│       └── SETUP.md               — how to obtain AccessKey/Secret etc.
├── .env.example                  ← template for credentials
└── requirements.txt
```

## Provider matrix

| Provider | Lifecycle              | Cost          | IP rotation              | Latency from China | Notes |
|----------|------------------------|---------------|--------------------------|--------------------|-------|
| Vultr    | API (create + destroy) | ~$5/month     | Unlimited (rebuild ⇒ new IP) | 50-150ms          | Best when frequent rotation needed |
| Aliyun SWAS | API delete only; create in console | ~30-40 RMB/month | 3 free IP changes/month via console | 30-50ms | Best latency from China; quota-limited rotation |

## Preflight: ALWAYS RUN THIS FIRST

**Before any other command on a fresh setup**, run the preflight checker:

```bash
python3 main.py doctor
```

This inspects the local environment + cloud credentials and reports exactly
what's missing, with a concrete fix for each gap. The agent's job is to read
the output and walk the user through whichever gaps are flagged. The checks
cover the full prerequisite chain:

| Stage | What's verified | If missing → action |
|-------|-----------------|---------------------|
| Toolchain | Python 3.8+, `requests`, `pyyaml`, `ssh`, `sshpass` | `pip3 install -r requirements.txt`; `brew install hudochenkov/sshpass/sshpass` (macOS) or `apt install sshpass` (only required for Aliyun) |
| SSH keypair | `~/.ssh/id_ed25519.pub` (or `id_rsa.pub`) or explicit `SSH_PUBLIC_KEY` env | `ssh-keygen -t ed25519` — accept default path |
| `.env` file | Exists at project root | `cp .env.example .env` then edit |
| Vultr account | Has `VULTR_API_KEY` and key actually works against `/v2/regions` | If user has no Vultr account: walk through https://www.vultr.com/ signup → https://my.vultr.com/settings/#settingsapi → enable API + whitelist IP → paste token |
| Vultr SSH key (optional) | `VULTR_SSH_KEY_ID` set | Upload key at https://my.vultr.com/account/#accountssh; get UUID via `curl -s -H "Authorization: Bearer $VULTR_API_KEY" https://api.vultr.com/v2/ssh-keys \| jq` |
| Aliyun account | Has `ALIYUN_ACCESS_KEY` + `_SECRET` and AK works against `ListInstances` | If user has no account: signup at https://www.alibabacloud.com/ → create **RAM sub-user** at https://ram.console.aliyun.com/users → enable OpenAPI access → generate AccessKey → attach `AliyunSWASFullAccess` policy. **Never use root account's key.** |
| Aliyun root password | `ALIYUN_PW` set | Set when buying the SWAS VM, or reset via console |
| Aliyun instance | At least one SWAS instance exists in `ALIYUN_REGION` | Aliyun create is **manual**. Send user to https://swasnext.console.aliyun.com/buy. **Must be the *overseas* edition of 轻量应用服务器** (Singapore / Hong Kong) — the mainland-China edition cannot reach blocked sites. Cheapest plan (~24-30 RMB/mo) is enough. Pick image **Alibaba Cloud Linux 3**, set the same root password as `ALIYUN_PW`, open TCP 443 in firewall. Then `python3 main.py aliyun deploy <ip>`. |

The script exits 0 when everything is in place, non-zero with a punch-list otherwise.

## Setup flow (when preflight reports gaps)

Match each `[gap_id]` from `doctor` output to one of these playbooks. After
each fix, re-run `python3 main.py doctor` to confirm before moving on.

### Need a Vultr account / API key (`vultr-account`)
1. Ask: "Do you already have a Vultr account?" — if no, point them at https://www.vultr.com/ (often has signup credit)
2. Once signed in: https://my.vultr.com/settings/#settingsapi → click **Enable API** → add their current IP to **Access Control** allowlist
3. Copy the **Personal Access Token** → user pastes into `.env` as `VULTR_API_KEY=...`
4. (Recommended) Upload an SSH public key at https://my.vultr.com/account/#accountssh, then put its UUID into `VULTR_SSH_KEY_ID`
5. Re-run `python3 main.py doctor`; then `python3 main.py vultr create`

Full step-by-step: [providers/vultr/SETUP.md](providers/vultr/SETUP.md)

### Need an Aliyun account / AK/SK (`aliyun-account`)
1. Ask: "Do you already have an Alibaba Cloud / 阿里云 account?" — if no, https://www.alibabacloud.com/ (international) or https://www.aliyun.com/ (China)
2. **Create a RAM sub-user** at https://ram.console.aliyun.com/users — name it e.g. `proxy0-bot`, enable **OpenAPI access**
3. Generate AccessKey + Secret for that sub-user (the secret only shows once — save immediately)
4. Click the user → **Permissions** → **Grant Permission** → attach system policy `AliyunSWASFullAccess`
5. Paste into `.env`: `ALIYUN_ACCESS_KEY=...`, `ALIYUN_ACCESS_SECRET=...`

Full step-by-step: [providers/aliyun/SETUP.md](providers/aliyun/SETUP.md)

### Need an Aliyun SWAS instance (`aliyun-instance`)
The Aliyun SWAS API does NOT support creating instances programmatically with a region-agnostic flow, so this step is unavoidably manual.

**⚠️ CRITICAL: tell the user to buy the *overseas* edition of 轻量应用服务器 (Simple Application Server / SWAS), not the mainland-China edition.**
- Mainland-China SWAS instances cannot reach blocked sites — useless as a proxy.
- Overseas SWAS is cheap: smallest plan is ~24–30 RMB/month (1 vCPU / 1 GB / 30 Mbps), which is plenty for personal proxy traffic.
- Pick **Singapore (`ap-southeast-1`)** for general use or **Hong Kong (`cn-hongkong`)** if the user needs the lowest latency from mainland China (but HK IPs get probed harder).

Steps:
1. https://swasnext.console.aliyun.com/buy
2. Product: **轻量应用服务器 (Simple Application Server)** — make sure the region picker is set to an **overseas** region matching `ALIYUN_REGION`
3. Plan: the cheapest one is sufficient (don't oversell — proxy traffic is the bottleneck on the IP, not on CPU/RAM)
4. Image: **Alibaba Cloud Linux 3** (the deploy script uses `yum`)
5. Set a **root password** — must match `ALIYUN_PW` in `.env`
6. After purchase, in the instance's **Security → Firewall**: open TCP `443`
7. Then: `python3 main.py aliyun deploy <public_ip>`

### Need an SSH keypair (`ssh-key`)
```bash
ssh-keygen -t ed25519        # accept the default path ~/.ssh/id_ed25519
```
The tool auto-detects this on next run; no `.env` edit needed.

### Need `.env` (`env-file`)
```bash
cp .env.example .env
# then edit .env to fill in credentials per the gaps above
```

## After preflight passes — first deploy

- Vultr: `python3 main.py vultr create`  (~3 min, fully automatic)
- Aliyun: `python3 main.py aliyun deploy <ip>`  (instance bought already)

Either prints a `vless://` link (paste into Shadowrocket / v2rayN) and writes
`clash_config_<provider>.yaml` for Clash Meta.

## Command reference

```bash
# Vultr (API-driven full lifecycle)
python3 main.py vultr create        # provision new VM + deploy xray
python3 main.py vultr destroy       # delete VM
python3 main.py vultr rebuild       # destroy + create (new IP)
python3 main.py vultr config        # print vless:// link + write clash YAML
python3 main.py vultr status        # local + API status
python3 main.py vultr check         # TCP probe + ping
python3 main.py vultr regions       # list region slugs

# Aliyun SWAS (API can list/delete; create is manual)
python3 main.py aliyun list         # list SWAS instances visible to the AK
python3 main.py aliyun deploy <ip>  # SCP+SSH the install script onto an existing IP
python3 main.py aliyun config       # print vless:// link + write clash YAML
python3 main.py aliyun status       # local state
python3 main.py aliyun check        # TCP probe + ping
python3 main.py aliyun destroy      # delete via API
python3 main.py aliyun rebuild      # destroy and prompt to recreate in console

# Multi-provider (auto-detect from state files)
python3 main.py status              # print status for every configured provider
python3 main.py config              # print configs for every configured provider
python3 main.py check               # ping every configured provider

# Diagnostics
python3 main.py doctor              # preflight: what's missing + how to fix
```

## Decision tree (what to run when)

The user is most often coming with one of these intents — match and act:

- **"set up a proxy" / first time / "I want a VPN"**
  → **Always start with `python3 main.py doctor`.** Read its output, walk the user through whichever gaps it reports (account signup, API key creation, SSH key generation, .env file, Aliyun instance purchase). Re-run after each fix. Only after `doctor` passes, run `vultr create` or `aliyun deploy <ip>`. If the user has no preference, default to **Vultr** (simpler — fully API-managed, no manual instance purchase).

- **"my proxy stopped working" / "claude.ai blocked"**
  → `python3 main.py check` first. If TCP fails or ping has high loss, the IP is likely blocked.
  - Vultr: `python3 main.py vultr rebuild` (free, ~3 min, new IP)
  - Aliyun: tell the user to use the console's "更换公网 IP" (3/month free), then `python3 main.py aliyun deploy <new-ip>`

- **"give me my client config"**
  → `python3 main.py config` (auto-detects). Outputs vless:// link to paste into Shadowrocket/v2rayN, and writes `clash_config_<provider>.yaml`.

- **"switch to a different region"** (Vultr only)
  → `python3 main.py vultr regions`, edit `.env` `VULTR_REGION=…`, then `python3 main.py vultr rebuild`.

- **"clean up everything"**
  → `python3 main.py vultr destroy` and/or `python3 main.py aliyun destroy`.

- **"what's running"**
  → `python3 main.py status`.

## Protocol details

- VLESS + XTLS-Reality (no certificate management needed)
- Server listens on TCP `XRAY_PORT` (default `443`)
- Reality masquerade target: `XRAY_SNI` (default `www.microsoft.com`)
- Client must support Reality — **Clash Meta**, **Shadowrocket**, **v2rayN**, **Hiddify**. Plain Clash does **not** work.
- Generated Clash YAML routes Anthropic / Claude domains through proxy and `GEOIP,CN` direct.

## State files (gitignored)

- `.proxy_state_vultr.json` — Vultr current instance
- `.proxy_state_aliyun_<region>.json` — Aliyun current instance per region
- `clash_config_vultr.yaml`, `clash_config_aliyun.yaml` — last emitted Clash configs

A legacy `.proxy_state.json` from older versions is read as a Vultr fallback.

## Adding a new provider

1. `mkdir providers/<name>/` with `__init__.py`
2. Write `api.py` (cloud API client), `deploy_script.py` or `cloudinit.py` (server-side install), `manager.py` exposing a `COMMANDS` dict and a module-level `STATE_FILE`
3. Register in `main.py`'s `PROVIDERS` and `PROVIDER_DISPLAY` dicts
4. Add `<NAME>_*` env vars to `core/config.py` and `.env.example`
5. Write `SETUP.md` covering account → credentials → first deploy

## Environment variables (full list)

| Var                  | Purpose                                       |
|----------------------|-----------------------------------------------|
| `SSH_PUBLIC_KEY`     | Injected into server's `authorized_keys`. Unset → auto-detect `~/.ssh/id_ed25519.pub` / `id_rsa.pub`; empty string → skip injection |
| `INSTANCE_LABEL`     | VM label / hostname (default `proxy0`)        |
| `XRAY_PORT`          | Listen port (default `443`)                   |
| `XRAY_SNI`           | Reality masquerade SNI (default `www.microsoft.com`) |
| `VULTR_API_KEY`      | Vultr personal access token                   |
| `VULTR_SSH_KEY_ID`   | UUID of SSH key uploaded to Vultr             |
| `VULTR_REGION`       | Vultr region slug (`icn`, `nrt`, `sgp`, …)    |
| `VULTR_PLAN`         | Vultr plan id (default `vc2-1c-1gb`)          |
| `VULTR_OS_ID`        | Vultr OS id (default `2136` = Debian 12)      |
| `ALIYUN_ACCESS_KEY`  | RAM user AccessKeyId                          |
| `ALIYUN_ACCESS_SECRET` | RAM user AccessKeySecret                    |
| `ALIYUN_PW`          | Root password set when buying the SWAS VM     |
| `ALIYUN_REGION`      | `ap-southeast-1` or `cn-hongkong`             |

## Safety notes for agents

- **Never commit `.env`** or any `.proxy_state_*.json` — they contain credentials and live IPs. The repo's `.gitignore` already excludes them.
- `vultr destroy` / `vultr rebuild` and `aliyun destroy` are irreversible — confirm with the user before running unless they explicitly asked.
- `aliyun rebuild` will delete the instance; the user then has to **buy a new one in the console** (paid). Prefer "更换公网 IP" first.
- The Aliyun SWAS API uses a custom HMAC-SHA1 signing scheme implemented in `providers/aliyun/api.py`; if requests start failing with `IncompleteSignature` the server clock is likely off.
