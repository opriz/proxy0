# Vultr Setup Guide

## 1. Create a Vultr account

Sign up at https://www.vultr.com/. New accounts often get free credit.

## 2. Create an API key

1. Open https://my.vultr.com/settings/#settingsapi
2. Click **Enable API**
3. Add your current IP to the **Access Control** allowlist (or use `0.0.0.0/0` if you accept the risk)
4. Copy the **Personal Access Token** → this is your `VULTR_API_KEY`

## 3. (Recommended) Upload an SSH public key

So the script can SSH in to read `proxy_info.json`.

```bash
# Generate a key locally if you don't have one
ssh-keygen -t ed25519 -f ~/.ssh/proxy0_ed25519
cat ~/.ssh/proxy0_ed25519.pub      # copy this
```

1. Open https://my.vultr.com/account/#accountssh
2. **Add SSH Key** → paste the public key
3. After saving, click the key — the URL contains the SSH key ID (a UUID).
   Or list via API:
   ```bash
   curl -s -H "Authorization: Bearer $VULTR_API_KEY" \
        https://api.vultr.com/v2/ssh-keys | jq
   ```
4. Copy the `id` → this is your `VULTR_SSH_KEY_ID`

The deployment script also writes a key directly into `/root/.ssh/authorized_keys`
as defence in depth (in case Vultr's metadata-injection step fails). By default
it auto-picks up `~/.ssh/id_ed25519.pub` (or `id_rsa.pub`); to use a different
key, set `SSH_PUBLIC_KEY=ssh-ed25519 AAAA... user@host` in `.env`.

## 4. Pick a region

```bash
python3 main.py vultr regions
```

Common picks:
- `icn` — Seoul (default; low latency from East Asia)
- `nrt` — Tokyo
- `sgp` — Singapore
- `lax` — Los Angeles
- `fra` — Frankfurt

## 5. Fill in `.env`

```env
VULTR_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxx
VULTR_SSH_KEY_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VULTR_REGION=icn
SSH_PUBLIC_KEY=ssh-ed25519 AAAA... user@host
```

## 6. Create the server

```bash
python3 main.py vultr create
```

After ~3 minutes you'll get a `vless://` link and a `clash_config_vultr.yaml`.

## Cost

- `vc2-1c-1gb` plan: ~$5 / month
- Destroy + recreate is free; you only pay for hours used

## When the IP is blocked

```bash
python3 main.py vultr rebuild   # destroys and recreates with new IP
```
