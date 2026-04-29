"""Preflight check — what's already in place vs. what the user still needs.

Designed for an agent to call (`python3 main.py doctor`) before any other
command. Output is structured-ish text so a model can read it and decide
which gap to walk the user through next.
"""
import os
import shutil
import subprocess
import sys

from core.config import (
    PROJECT_ROOT,
    VULTR_API_KEY, VULTR_SSH_KEY_ID, VULTR_REGION,
    ALIYUN_ACCESS_KEY, ALIYUN_ACCESS_SECRET, ALIYUN_PW, ALIYUN_REGION,
    SSH_PUBLIC_KEY, state_path,
)

OK = "  [ok]"
MISS = "  [missing]"
WARN = "  [warn]"


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _python_pkg(pkg: str) -> bool:
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


def _ssh_key_present() -> tuple[bool, str]:
    if SSH_PUBLIC_KEY:
        for fname in ("id_ed25519.pub", "id_rsa.pub"):
            path = os.path.expanduser(f"~/.ssh/{fname}")
            if os.path.exists(path):
                return True, path
        return True, "(value provided via SSH_PUBLIC_KEY env)"
    return False, ""


def _vultr_api_works() -> tuple[bool, str]:
    if not VULTR_API_KEY:
        return False, "VULTR_API_KEY not set"
    try:
        from providers.vultr import api
        api.list_regions()
        return True, "API key works"
    except Exception as e:
        return False, f"API call failed: {e}"


def _aliyun_api_works() -> tuple[bool, str]:
    if not (ALIYUN_ACCESS_KEY and ALIYUN_ACCESS_SECRET):
        return False, "ALIYUN_ACCESS_KEY / ALIYUN_ACCESS_SECRET not set"
    try:
        from providers.aliyun import api
        api.list_instances()
        return True, "API key works"
    except Exception as e:
        return False, f"API call failed: {e}"


def _aliyun_instances_exist() -> tuple[int, list]:
    try:
        from providers.aliyun import api
        return 1, api.list_instances()
    except Exception:
        return -1, []


def run():
    print("proxy0 preflight check")
    print("=" * 50)
    gaps = []  # list of (severity, gap_id, message, fix_hint)

    # ── Local toolchain ─────────────────────────────────────────────────────
    print("\n[1/5] Local toolchain")
    if sys.version_info >= (3, 8):
        print(f"{OK} Python {sys.version.split()[0]}")
    else:
        print(f"{MISS} Python 3.8+ required")
        gaps.append(("must", "python", "Install Python 3.8+", "https://www.python.org/downloads/"))

    for pkg in ("requests", "yaml"):
        if _python_pkg(pkg):
            print(f"{OK} python pkg: {pkg}")
        else:
            print(f"{MISS} python pkg: {pkg}")
            gaps.append(("must", f"pip-{pkg}", f"Missing {pkg}",
                         "Run: pip3 install -r requirements.txt"))

    if _has("ssh"):
        print(f"{OK} ssh")
    else:
        print(f"{MISS} ssh")
        gaps.append(("must", "ssh", "ssh not on PATH", "Install OpenSSH client"))

    # sshpass only required for Aliyun flow
    if _has("sshpass"):
        print(f"{OK} sshpass (needed for Aliyun)")
    else:
        print(f"{WARN} sshpass not found (only required if using Aliyun)")
        gaps.append(("aliyun", "sshpass",
                     "sshpass missing — required for Aliyun password SSH",
                     "macOS: brew install hudochenkov/sshpass/sshpass\n"
                     "       Debian/Ubuntu: sudo apt install sshpass"))

    # ── SSH keypair ─────────────────────────────────────────────────────────
    print("\n[2/5] SSH keypair")
    has_key, where = _ssh_key_present()
    if has_key:
        print(f"{OK} found: {where}")
    else:
        print(f"{MISS} no local SSH key found and SSH_PUBLIC_KEY not set")
        gaps.append(("must", "ssh-key",
                     "No SSH keypair found",
                     "Generate one: ssh-keygen -t ed25519\n"
                     "(accept the default ~/.ssh/id_ed25519 path)"))

    # ── .env file ───────────────────────────────────────────────────────────
    print("\n[3/5] .env file")
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        print(f"{OK} {env_path}")
    else:
        print(f"{MISS} .env not found")
        gaps.append(("must", "env-file",
                     ".env not created yet",
                     f"cp {os.path.join(PROJECT_ROOT, '.env.example')} {env_path}"))

    # ── Vultr ───────────────────────────────────────────────────────────────
    print("\n[4/5] Vultr provider")
    if not VULTR_API_KEY:
        print(f"{MISS} VULTR_API_KEY not set — Vultr disabled")
        gaps.append(("vultr", "vultr-account",
                     "No Vultr API key configured",
                     "1. Sign up at https://www.vultr.com/ (if no account)\n"
                     "2. Create API key: https://my.vultr.com/settings/#settingsapi\n"
                     "   - Click 'Enable API'\n"
                     "   - Whitelist your current IP under Access Control\n"
                     "3. Paste the token into .env as VULTR_API_KEY=...\n"
                     "Full guide: providers/vultr/SETUP.md"))
    else:
        ok, msg = _vultr_api_works()
        if ok:
            print(f"{OK} {msg}")
        else:
            print(f"{MISS} {msg}")
            gaps.append(("vultr", "vultr-api",
                         f"Vultr API key invalid: {msg}",
                         "Re-check the token; ensure your IP is whitelisted at\n"
                         "https://my.vultr.com/settings/#settingsapi"))

        if VULTR_SSH_KEY_ID:
            print(f"{OK} VULTR_SSH_KEY_ID set ({VULTR_SSH_KEY_ID[:8]}...)")
        else:
            print(f"{WARN} VULTR_SSH_KEY_ID empty — relying on injected key only")
            gaps.append(("vultr", "vultr-sshkey",
                         "No Vultr-side SSH key registered (optional but recommended)",
                         "1. Upload key at https://my.vultr.com/account/#accountssh\n"
                         "2. Get its UUID:\n"
                         "   curl -s -H \"Authorization: Bearer $VULTR_API_KEY\" \\\n"
                         "        https://api.vultr.com/v2/ssh-keys | jq\n"
                         "3. Set VULTR_SSH_KEY_ID=<uuid> in .env"))

        print(f"{OK} VULTR_REGION={VULTR_REGION}")

    # ── Aliyun ──────────────────────────────────────────────────────────────
    print("\n[5/5] Aliyun provider")
    if not (ALIYUN_ACCESS_KEY and ALIYUN_ACCESS_SECRET):
        print(f"{MISS} ALIYUN_ACCESS_KEY / SECRET not set — Aliyun disabled")
        gaps.append(("aliyun", "aliyun-account",
                     "No Aliyun AK/SK configured",
                     "1. Sign up at https://www.alibabacloud.com/ (or aliyun.com)\n"
                     "2. Create a RAM sub-user (NOT root account):\n"
                     "   https://ram.console.aliyun.com/users\n"
                     "3. Enable 'OpenAPI access', generate AccessKey + Secret\n"
                     "4. Attach policy AliyunSWASFullAccess to that user\n"
                     "5. Paste into .env as ALIYUN_ACCESS_KEY / ALIYUN_ACCESS_SECRET\n"
                     "Full guide: providers/aliyun/SETUP.md"))
    else:
        ok, msg = _aliyun_api_works()
        if ok:
            print(f"{OK} {msg}")
        else:
            print(f"{MISS} {msg}")
            gaps.append(("aliyun", "aliyun-api",
                         f"Aliyun AK/SK invalid: {msg}",
                         "Re-check the keys; ensure the RAM user has\n"
                         "AliyunSWASFullAccess attached and ALIYUN_REGION matches\n"
                         "the region where your instance lives."))

        if ALIYUN_PW:
            print(f"{OK} ALIYUN_PW set")
        else:
            print(f"{MISS} ALIYUN_PW empty — required for password SSH deploy")
            gaps.append(("aliyun", "aliyun-pw",
                         "ALIYUN_PW (root password of the SWAS VM) not set",
                         "Set it to the root password you chose when buying the\n"
                         "SWAS instance, or reset it at:\n"
                         "https://swasnext.console.aliyun.com/"))

        # SWAS instance must be bought manually — check it exists
        rc, instances = _aliyun_instances_exist()
        if rc < 0:
            print(f"{WARN} could not list instances (API not reachable)")
        elif not instances:
            print(f"{MISS} no SWAS instance bought yet in region {ALIYUN_REGION}")
            gaps.append(("aliyun", "aliyun-instance",
                         "No SWAS instance found — Aliyun create is manual",
                         f"IMPORTANT: buy the OVERSEAS edition of 轻量应用服务器 (SWAS),\n"
                         f"NOT the mainland-China edition. Overseas is cheap (~24-30 RMB/mo\n"
                         f"for the smallest plan) and the throughput is plenty for personal\n"
                         f"proxy use. Mainland-China SWAS cannot reach blocked sites.\n"
                         f"\n"
                         f"1. Buy at https://swasnext.console.aliyun.com/buy\n"
                         f"   - Product line: 轻量应用服务器 / Simple Application Server\n"
                         f"   - Region: {ALIYUN_REGION}  ← MUST be an overseas region\n"
                         f"     (ap-southeast-1 = Singapore, cn-hongkong = Hong Kong)\n"
                         f"   - Plan: cheapest one is enough (1C/1G, 30Mbps peak)\n"
                         f"   - Image: Alibaba Cloud Linux 3 (or any yum-based image)\n"
                         f"   - Set the same root password you put in ALIYUN_PW\n"
                         f"2. In the instance's Security/Firewall, open TCP 443\n"
                         f"3. Then run: python3 main.py aliyun deploy <public_ip>"))
        else:
            print(f"{OK} {len(instances)} SWAS instance(s) found in {ALIYUN_REGION}")

    # ── Existing deployments ────────────────────────────────────────────────
    print("\n[ ] Already-deployed proxies (state files)")
    any_state = False
    for label, path in [
        ("Vultr",   state_path(".proxy_state_vultr.json")),
        ("Vultr-legacy", state_path(".proxy_state.json")),
        ("Aliyun-sg", state_path(".proxy_state_aliyun_sg.json")),
        ("Aliyun-hk", state_path(".proxy_state_aliyun_hk.json")),
    ]:
        if os.path.exists(path):
            any_state = True
            print(f"{OK} {label}: {path}")
    if not any_state:
        print("  (none — nothing deployed yet)")

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    musts = [g for g in gaps if g[0] == "must"]
    vultr_gaps = [g for g in gaps if g[0] == "vultr"]
    aliyun_gaps = [g for g in gaps if g[0] == "aliyun"]

    if not gaps:
        print("All preflight checks passed. You can run:")
        print("  python3 main.py vultr create")
        print("  python3 main.py aliyun deploy <ip>")
        return 0

    print(f"Found {len(gaps)} gap(s):")
    if musts:
        print("\n  Must fix (blocking everything):")
        for _, gid, m, _ in musts:
            print(f"    - [{gid}] {m}")
    if vultr_gaps:
        print("\n  Vultr-specific:")
        for _, gid, m, _ in vultr_gaps:
            print(f"    - [{gid}] {m}")
    if aliyun_gaps:
        print("\n  Aliyun-specific:")
        for _, gid, m, _ in aliyun_gaps:
            print(f"    - [{gid}] {m}")

    print("\nDetailed fix instructions:")
    for sev, gid, m, fix in gaps:
        print(f"\n--- [{sev}/{gid}] {m} ---")
        print(fix)

    return 1


if __name__ == "__main__":
    sys.exit(run())
