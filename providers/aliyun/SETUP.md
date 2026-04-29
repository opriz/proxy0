# Aliyun (Alibaba Cloud) SWAS Setup Guide

This provider targets **轻量应用服务器 (Simple Web App Server / SWAS)**, the
cheap fixed-spec VM product, not full ECS.

## 1. Create an Alibaba Cloud account

Sign up: https://www.alibabacloud.com/ (international) or https://www.aliyun.com/ (China).

## 2. Create a RAM user with API credentials (AK/SK)

> Don't use the **root account**'s AccessKey — Alibaba's own console will
> warn you about it. Always use a RAM sub-user.

1. Open https://ram.console.aliyun.com/users
2. **Create User** → enable **OpenAPI Access** (programmatic access). Name it
   e.g. `proxy0-bot`.
3. After creation, click **Create AccessKey** for that user.
4. Copy:
   - `AccessKeyId` → `ALIYUN_ACCESS_KEY`
   - `AccessKeySecret` → `ALIYUN_ACCESS_SECRET`
   (the secret is only shown once — save it now)
5. Give the user permission to manage SWAS:
   - Click the user → **Permissions** tab → **Grant Permission**
   - Attach the system policy **`AliyunSWASFullAccess`**

## 3. Create a SWAS instance manually (one-time)

The Aliyun SWAS API does **not** support creating instances programmatically
in a region-agnostic way (the create flow requires a paid plan ID and varies
per region), so you create the VM in the console once, then this tool deploys
xray onto it.

> ⚠️ **Buy the *overseas* edition of 轻量应用服务器 (SWAS)**, not the mainland-China
> edition. Only overseas regions can reach blocked sites — a mainland instance
> is useless as a proxy. The overseas edition is cheap (~24–30 RMB/month for
> the smallest plan) and the throughput is more than enough for personal use.

1. Open https://swasnext.console.aliyun.com/buy
2. Product: **轻量应用服务器 / Simple Application Server** — make sure the
   region selector at the top is set to an overseas region:
   - **Singapore (`ap-southeast-1`)** — recommended default; best for Anthropic / Google / general
   - **Hong Kong (`cn-hongkong`)** — lowest latency from mainland China, but probed more aggressively
3. Plan: the cheapest one (e.g. 1 vCPU / 1 GB / 30 Mbps peak, ~24–30 RMB/mo).
   Don't pay for a bigger plan — proxy throughput is bottlenecked by the IP,
   not by CPU/RAM.
4. Image: **Alibaba Cloud Linux 3** (other yum-based images also work; the script uses `yum`)
5. Set a **root password** — you'll put this in `ALIYUN_PW`
6. Buy. Wait ~1 minute for the instance to come up.
7. In the instance detail page, **Security → Firewall**: open TCP port `443`
   (the protocol port).

## 4. Fill in `.env`

```env
ALIYUN_ACCESS_KEY=LTAI5txxxxxxxxxxxxxxx
ALIYUN_ACCESS_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALIYUN_PW=<the root password you just set>
ALIYUN_REGION=ap-southeast-1     # or cn-hongkong
# SSH_PUBLIC_KEY=ssh-ed25519 AAAA... user@host
# ↑ optional; if omitted, auto-detected from ~/.ssh/id_ed25519.pub
```

## 5. Deploy xray onto the instance

You need `sshpass` locally for password-based SCP/SSH:

```bash
brew install hudochenkov/sshpass/sshpass    # macOS
# or: apt install sshpass                   # Debian/Ubuntu
```

```bash
python3 main.py aliyun list                 # confirm the API key works
python3 main.py aliyun deploy <PUBLIC_IP>   # runs the install script
```

After ~3 minutes you'll get a `vless://` link and `clash_config_aliyun.yaml`.

## When the IP is blocked

SWAS gives you **3 free IP changes per month** via the console:

1. https://swasnext.console.aliyun.com/ → instance → **更换公网 IP / Replace Public IP**
2. After the new IP is assigned, redeploy:
   ```bash
   python3 main.py aliyun deploy <NEW_IP>
   ```

If you've used up your IP changes, `python3 main.py aliyun rebuild` will
delete the instance — you then need to buy a fresh one in the console.

## Cost

- Smallest SWAS plan: ~30-40 RMB/month (≈$5)
- IP changes: 3/month free, then paid
