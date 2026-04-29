"""Generate cloud-init user_data for Debian-based Vultr instances."""
import base64
import uuid

from core.config import SSH_PUBLIC_KEY


def generate_user_data(port: int, sni: str) -> str:
    """Generate cloud-init script that installs and configures xray VLESS+Reality."""
    client_uuid = str(uuid.uuid4())

    if SSH_PUBLIC_KEY:
        ssh_block = f"""mkdir -p /root/.ssh
chmod 700 /root/.ssh
cat > /root/.ssh/authorized_keys << 'SSHKEY'
{SSH_PUBLIC_KEY}
SSHKEY
chmod 600 /root/.ssh/authorized_keys

sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd
"""
    else:
        ssh_block = "# SSH_PUBLIC_KEY not set; relying on Vultr's default SSH-key injection\n"

    script = f"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq curl wget unzip jq

bash <(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh) install

KEYS=$(xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep -iE 'privatekey|private key' | awk -F': ' '{{print $2}}' | tr -d ' ')
PUBLIC_KEY=$(echo "$KEYS" | grep -iE 'password|public key' | awk -F': ' '{{print $2}}' | tr -d ' ')
SHORT_ID=$(openssl rand -hex 4)
CLIENT_UUID="{client_uuid}"

cat > /usr/local/etc/xray/config.json << EOF
{{
  "log": {{"loglevel": "warning"}},
  "inbounds": [{{
    "listen": "0.0.0.0",
    "port": {port},
    "protocol": "vless",
    "settings": {{
      "clients": [{{"id": "$CLIENT_UUID", "flow": "xtls-rprx-vision"}}],
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
    "sniffing": {{"enabled": true, "destOverride": ["http", "tls"]}}
  }}],
  "outbounds": [
    {{"protocol": "freedom", "tag": "direct"}},
    {{"protocol": "blackhole", "tag": "block"}}
  ]
}}
EOF

cat > /root/proxy_info.json << EOF
{{
  "uuid": "$CLIENT_UUID",
  "public_key": "$PUBLIC_KEY",
  "short_id": "$SHORT_ID",
  "port": {port},
  "sni": "{sni}"
}}
EOF

{ssh_block}

systemctl enable xray
systemctl restart xray

if command -v ufw &>/dev/null; then
  ufw allow {port}/tcp
fi

echo "xray setup done"
"""
    return base64.b64encode(script.encode()).decode()


def get_client_uuid_from_script(user_data_b64: str) -> str:
    script = base64.b64decode(user_data_b64).decode()
    for line in script.splitlines():
        if line.startswith("CLIENT_UUID="):
            return line.split('"')[1]
    return ""
