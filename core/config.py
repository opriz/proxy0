"""Shared configuration loaded from .env (project root)."""
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_file = os.path.join(_PROJECT_ROOT, ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

PROJECT_ROOT = _PROJECT_ROOT

# ─── Common ──────────────────────────────────────────────────────────────────
INSTANCE_LABEL = os.environ.get("INSTANCE_LABEL", "proxy0")
XRAY_PORT = int(os.environ.get("XRAY_PORT", "443"))
XRAY_SNI = os.environ.get("XRAY_SNI", "www.microsoft.com")

# SSH public key that the deployment script will inject into the server's
# /root/.ssh/authorized_keys. If unset, auto-discover the user's local key
# (~/.ssh/id_ed25519.pub then ~/.ssh/id_rsa.pub). Set explicitly to "" in
# .env to opt out (e.g. when relying purely on cloud-provider key injection).
def _autodetect_ssh_pubkey() -> str:
    for fname in ("id_ed25519.pub", "id_rsa.pub"):
        path = os.path.expanduser(f"~/.ssh/{fname}")
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    return ""


_ssh_env = os.environ.get("SSH_PUBLIC_KEY")
if _ssh_env is None:
    SSH_PUBLIC_KEY = _autodetect_ssh_pubkey()
else:
    SSH_PUBLIC_KEY = _ssh_env.strip()

# ─── Vultr ───────────────────────────────────────────────────────────────────
VULTR_API_KEY = os.environ.get("VULTR_API_KEY", "")
VULTR_SSH_KEY_ID = os.environ.get("VULTR_SSH_KEY_ID", "")
VULTR_REGION = os.environ.get("VULTR_REGION", "icn")
VULTR_PLAN = os.environ.get("VULTR_PLAN", "vc2-1c-1gb")
VULTR_OS_ID = int(os.environ.get("VULTR_OS_ID", "2136"))  # Debian 12 x64

# ─── Aliyun ──────────────────────────────────────────────────────────────────
ALIYUN_ACCESS_KEY = os.environ.get("ALIYUN_ACCESS_KEY", "")
ALIYUN_ACCESS_SECRET = os.environ.get("ALIYUN_ACCESS_SECRET", "")
ALIYUN_PW = os.environ.get("ALIYUN_PW", "")
ALIYUN_REGION = os.environ.get("ALIYUN_REGION", "ap-southeast-1")


def state_path(filename: str) -> str:
    """Resolve a state file path under the project root."""
    return os.path.join(PROJECT_ROOT, filename)
