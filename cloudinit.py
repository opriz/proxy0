import base64
import uuid

def generate_user_data(port: int, sni: str) -> str:
    """Generate cloud-init user_data that installs and configures xray VLESS+Reality."""
    # UUID and keys are generated on the server; the script reads them back afterwards
    client_uuid = str(uuid.uuid4())

    script = f"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

# Base dependencies
apt-get update -qq
apt-get install -y -qq curl wget unzip jq

# Install xray
bash <(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh) install

# Generate a Reality keypair (handles both old and new xray output formats)
KEYS=$(xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep -iE 'privatekey|private key' | awk -F': ' '{{print $2}}' | tr -d ' ')
PUBLIC_KEY=$(echo "$KEYS" | grep -iE 'password|public key' | awk -F': ' '{{print $2}}' | tr -d ' ')
SHORT_ID=$(openssl rand -hex 4)
CLIENT_UUID="{client_uuid}"

# Write xray config
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

# Save client parameters so the local script can read them back later
cat > /root/proxy_info.json << EOF
{{
  "uuid": "$CLIENT_UUID",
  "public_key": "$PUBLIC_KEY",
  "short_id": "$SHORT_ID",
  "port": {port},
  "sni": "{sni}"
}}
EOF

# Install SSH key
mkdir -p /root/.ssh
chmod 700 /root/.ssh
cat > /root/.ssh/authorized_keys << 'SSHKEY'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFiDB8l5XVSwN94gj5K0INj5inFtYP/uBkh/ZW2+kKNi zhujian@zhujiandeMacBook-Air.local
SSHKEY
chmod 600 /root/.ssh/authorized_keys

# Disable SSH password login
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd

# Start xray
systemctl enable xray
systemctl restart xray

# Open firewall if ufw is present
if command -v ufw &>/dev/null; then
  ufw allow {port}/tcp
fi

echo "xray setup done"
"""

    encoded = base64.b64encode(script.encode()).decode()
    return encoded


def get_client_uuid_from_script(user_data_b64: str) -> str:
    """Extract the preset client UUID from the user_data script."""
    script = base64.b64decode(user_data_b64).decode()
    for line in script.splitlines():
        if line.startswith("CLIENT_UUID="):
            return line.split('"')[1]
    return ""
