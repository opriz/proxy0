# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small Python CLI that provisions personal **VLESS+Reality (xray)** proxy VMs across multiple cloud providers (currently Vultr and Aliyun SWAS), then emits client config (`vless://` link + Clash Meta YAML). No build, no lint, no test suite — everything ships from source.

There is a very detailed agent runbook at `SKILL.md`: read it before walking a user through first-time setup or troubleshooting. It contains the decision tree, gap-by-gap fix playbooks, and provider matrix. `CLAUDE.md` is for orienting in the code; `SKILL.md` is for orchestrating the user.

## Common commands

```bash
# install deps (only requests + pyyaml)
pip3 install -r requirements.txt

# preflight — diagnoses missing prerequisites, ALWAYS run this first on a fresh setup
python3 main.py doctor

# per-provider lifecycle
python3 main.py vultr  {create|destroy|rebuild|config|status|check|regions}
python3 main.py aliyun {list|deploy <ip>|config|status|check|destroy|rebuild}

# multi-provider auto-detect (walks every provider that has a state file)
python3 main.py {status|config|check}
```

Provider aliases registered in `main.py`: `v` → vultr, `a` / `ali` → aliyun.

Aliyun-specific extra runtime dep: `sshpass` (password SSH for the SWAS deploy). Not needed for Vultr.

## Architecture

### Provider plugin pattern

`main.py` is a thin dispatcher. Each cloud provider is a self-contained module under `providers/<name>/` exposing two contracts:

- `manager.COMMANDS` — `dict[str, Callable]` mapping subcommand names to argless functions
- `manager.STATE_FILE` — absolute path to that provider's JSON state file

Registration is two lines in `main.py`'s `PROVIDERS` / `PROVIDER_DISPLAY` dicts. The auto-detect commands (`status`/`config`/`check` with no provider prefix) iterate every distinct registered module and act on whichever providers have a state file present.

### Layers

- `core/` — provider-agnostic. `config.py` parses `.env` and auto-discovers an SSH pubkey; `client_config.py` builds the VLESS URI and Clash YAML; `connectivity.py` does state-file I/O, TCP+ping probes, and config printing; `preflight.py` is the `doctor` checker.
- `providers/<name>/` — per-provider. Typically:
  - `api.py` — cloud REST wrapper (Vultr: bearer token; Aliyun SWAS: custom HMAC-SHA1 query signing implemented inline — see comment at top of `providers/aliyun/api.py`)
  - `cloudinit.py` (Vultr) or `deploy_script.py` (Aliyun) — generates the **server-side bash install script** that installs xray and writes `/root/proxy_info.json`
  - `manager.py` — lifecycle commands

### Deploy flow (the non-obvious part)

Server config (Reality public key, short ID) is **generated on the server**, not locally. The flow:

1. Client generates a UUID locally, embeds it into a bash deploy script.
2. Vultr: passes script as cloud-init `user_data` at instance creation. Aliyun: `scp`s the script to a pre-existing SWAS instance and runs it via `sshpass ssh`.
3. The server-side script installs xray, generates a Reality x25519 keypair + short ID, writes them along with the UUID to `/root/proxy_info.json`.
4. Manager SSHs in and `cat`s `/root/proxy_info.json` to recover `public_key` / `short_id`, then writes the local state file.

This means `vultr create` blocks for ~2-3 min on `wait_for_active` + a 60s xray-init sleep; `aliyun deploy` blocks ~2-3 min on the install script. If `public_key` is missing from state, `cmd_config` re-fetches it over SSH.

### State files

- Vultr: `.proxy_state_vultr.json`. A legacy `.proxy_state.json` is read as a fallback for older deployments — both are cleared on `destroy`.
- Aliyun: `.proxy_state_aliyun_<region-short>.json` where region-short is `sg` for `ap-southeast-1`, `hk` for `cn-hongkong`, else the full region id. **One state file per region** — switching `ALIYUN_REGION` in `.env` effectively switches deployments.
- All state files and `clash_config_*.yaml` outputs are gitignored. `.env` too.

### Aliyun caveats

- The SWAS API does not expose instance *creation* in a usable way, so `aliyun rebuild` only destroys — the user must repurchase in the console. `manager.py` prints the URL and the next-step command.
- `aliyun destroy` with `instance_id == "manual"` (the marker set by `deploy`) falls back to listing all instances and prompting interactively.
- The HMAC-SHA1 signing in `providers/aliyun/api.py` is timestamp-sensitive; `IncompleteSignature` errors usually mean a skewed system clock.

## Adding a new provider

1. `mkdir providers/<name>/`, add `__init__.py`.
2. Implement `api.py`, a deploy-script generator, and `manager.py` with `COMMANDS` + `STATE_FILE`.
3. Add `<NAME>_*` env vars to `core/config.py` and `.env.example`.
4. Register the manager in `main.py`'s `PROVIDERS` and `PROVIDER_DISPLAY` dicts.
5. Add a preflight section to `core/preflight.py` (mirrors the existing Vultr/Aliyun stanzas).
6. Write a `providers/<name>/SETUP.md` covering account → AK → first deploy.
