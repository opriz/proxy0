import os

# Load environment variables from .env if it exists
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# Vultr API key (sensitive, read from environment)
VULTR_API_KEY = os.environ.get("VULTR_API_KEY", "")

# SSH key ID (on Vultr, used for passwordless login)
SSH_KEY_ID = os.environ.get("VULTR_SSH_KEY_ID", "")

# Aliyun credentials
ALIYUN_ACCESS_KEY = os.environ.get("ALIYUN_ACCESS_KEY", "")
ALIYUN_ACCESS_SECRET = os.environ.get("ALIYUN_ACCESS_SECRET", "")
ALIYUN_PW = os.environ.get("ALIYUN_PW", "")
ALIYUN_REGION = os.environ.get("ALIYUN_REGION", "ap-southeast-1")  # ap-southeast-1 (SG) or cn-hongkong (HK)

# Instance config
INSTANCE_LABEL = "proxy0"
REGION = os.environ.get("VULTR_REGION", "icn")   # Seoul; other options: nrt, sgp, lax, itm
PLAN = "vc2-1c-1gb"     # $5/month (smallest plan)
OS_ID = 2136            # Debian 12 x64

# xray config
XRAY_PORT = 443
XRAY_SNI = "www.microsoft.com"   # Reality masquerade target

# State file (tracks the current instance)
STATE_FILE = ".proxy_state.json"
