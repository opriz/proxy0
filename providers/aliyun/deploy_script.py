"""Generate the deployment shell script that runs on Alibaba Cloud Linux (yum)."""
import uuid

from core.config import SSH_PUBLIC_KEY


def generate_script(port: int, sni: str) -> tuple:
    """Returns (client_uuid, shell_script_text)."""
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
        ssh_block = "# SSH_PUBLIC_KEY not set; password auth stays enabled\n"

    script = f"""#!/bin/bash
set -e

yum install -y curl wget unzip jq openssl

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

if command -v firewall-cmd &>/dev/null; then
  firewall-cmd --permanent --add-port={port}/tcp
  firewall-cmd --reload
fi

echo "xray setup done"
"""
    return client_uuid, script
