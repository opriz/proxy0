import os

# 从 .env 文件加载环境变量（如果存在）
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# Vultr API Key（敏感，从环境变量读取）
VULTR_API_KEY = os.environ.get("VULTR_API_KEY", "")

# SSH Key ID（Vultr 上的，用于免密登录）
SSH_KEY_ID = os.environ.get("VULTR_SSH_KEY_ID", "")

# 实例配置
INSTANCE_LABEL = "proxy0"
REGION = os.environ.get("VULTR_REGION", "icn")   # 首尔，可选: nrt, sgp, lax, itm
PLAN = "vc2-1c-1gb"     # $5/月（东京最低配置）
OS_ID = 2136            # Debian 12 x64

# xray 配置
XRAY_PORT = 443
XRAY_SNI = "www.microsoft.com"   # Reality 伪装目标

# 状态文件（记录当前实例信息）
STATE_FILE = ".proxy_state.json"
