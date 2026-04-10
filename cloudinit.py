import base64
import uuid

def generate_user_data(port: int, sni: str) -> str:
    """生成 cloud-init user_data，自动安装并配置 xray VLESS+Reality"""
    # UUID 和密钥在服务端生成，脚本运行后从服务端读取
    client_uuid = str(uuid.uuid4())

    script = f"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

# 基础依赖
apt-get update -qq
apt-get install -y -qq curl wget unzip jq

# 安装 xray
bash <(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh) install

# 生成 Reality 密钥对（兼容新旧版本输出格式）
KEYS=$(xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep -iE 'privatekey|private key' | awk -F': ' '{{print $2}}' | tr -d ' ')
PUBLIC_KEY=$(echo "$KEYS" | grep -iE 'password|public key' | awk -F': ' '{{print $2}}' | tr -d ' ')
SHORT_ID=$(openssl rand -hex 4)
CLIENT_UUID="{client_uuid}"

# 写入 xray 配置
cat > /usr/local/etc/xray/config.json << EOF
{{
  "log": {{
    "loglevel": "warning"
  }},
  "inbounds": [
    {{
      "listen": "0.0.0.0",
      "port": {port},
      "protocol": "vless",
      "settings": {{
        "clients": [
          {{
            "id": "$CLIENT_UUID",
            "flow": "xtls-rprx-vision"
          }}
        ],
        "decryption": "none"
      }},
      "streamSettings": {{
        "network": "tcp",
        "security": "reality",
        "realitySettings": {{
          "show": false,
          "dest": "{sni}:443",
          "xver": 0,
          "serverNames": ["{sni}"],
          "privateKey": "$PRIVATE_KEY",
          "shortIds": ["$SHORT_ID"]
        }}
      }},
      "sniffing": {{
        "enabled": true,
        "destOverride": ["http", "tls"]
      }}
    }}
  ],
  "outbounds": [
    {{
      "protocol": "freedom",
      "tag": "direct"
    }},
    {{
      "protocol": "blackhole",
      "tag": "block"
    }}
  ]
}}
EOF

# 保存客户端所需参数到文件（供后续读取）
cat > /root/proxy_info.json << EOF
{{
  "uuid": "$CLIENT_UUID",
  "public_key": "$PUBLIC_KEY",
  "short_id": "$SHORT_ID",
  "port": {port},
  "sni": "{sni}"
}}
EOF

# 添加 SSH key
mkdir -p /root/.ssh
chmod 700 /root/.ssh
cat > /root/.ssh/authorized_keys << 'SSHKEY'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFiDB8l5XVSwN94gj5K0INj5inFtYP/uBkh/ZW2+kKNi zhujian@zhujiandeMacBook-Air.local
SSHKEY
chmod 600 /root/.ssh/authorized_keys

# 禁用 SSH 密码登录
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd

# 启动 xray
systemctl enable xray
systemctl restart xray

# 开放防火墙（如果有 ufw）
if command -v ufw &>/dev/null; then
  ufw allow {port}/tcp
fi

echo "xray setup done"
"""

    encoded = base64.b64encode(script.encode()).decode()
    return encoded


def get_client_uuid_from_script(user_data_b64: str) -> str:
    """从 user_data 中提取预设的 client UUID"""
    script = base64.b64decode(user_data_b64).decode()
    for line in script.splitlines():
        if line.startswith("CLIENT_UUID="):
            return line.split('"')[1]
    return ""
