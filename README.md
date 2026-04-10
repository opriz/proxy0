# proxy0

一键在 Vultr 上部署 VLESS+Reality 代理服务器，IP 被封时可快速销毁重建换 IP。

English version: [README.en.md](README.en.md)

---

## 原理

本地脚本调用 Vultr API 创建 VPS，通过 `user_data`（cloud-init）在服务器首次启动时自动安装并配置 xray。创建完成后脚本通过 SSH 读取服务端生成的 Reality 公钥等信息，生成客户端配置。IP 被封时一条命令销毁重建，约 4 分钟得到新 IP。

---

## 前置条件

- Python 3.8+
- Vultr 账号及 API Key
- 本地 SSH 密钥对（`~/.ssh/id_ed25519` 或 `id_rsa`），并已上传到 Vultr 控制台
- 客户端：Clash Meta（推荐 [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)）或 Shadowrocket / v2rayN

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
VULTR_API_KEY=your_vultr_api_key
VULTR_SSH_KEY_ID=your_ssh_key_id   # Vultr 控制台 Account → SSH Keys
VULTR_REGION=icn                   # 默认首尔，其他地区见下方列表
```

**获取 SSH Key ID：**
先在 Vultr 控制台 Account → SSH Keys 上传本地公钥，复制显示的 ID 填入 `.env`。

### 3. 创建服务器

```bash
python3 proxy.py create
```

完成后自动输出 Shadowrocket / v2rayN 导入链接，并将 Clash 配置保存到 `clash_config.yaml`。

---

## 命令

| 命令 | 说明 |
|------|------|
| `python3 proxy.py create` | 创建服务器并输出客户端配置 |
| `python3 proxy.py destroy` | 销毁当前服务器（停止计费）|
| `python3 proxy.py rebuild` | 销毁并重建，用于 IP 被封时换 IP |
| `python3 proxy.py config` | 重新显示客户端配置（VLESS 链接 + Clash YAML）|
| `python3 proxy.py status` | 查看当前服务器状态 |
| `python3 proxy.py check` | 检测 IP 连通性（TCP + Ping）|
| `python3 proxy.py regions` | 列出所有可用地区 |

---

## 推荐地区

| 代码 | 地区 | 延迟参考 |
|------|------|---------|
| `nrt` | 东京 Tokyo | ~50ms |
| `itm` | 大阪 Osaka | ~55ms |
| `icn` | 首尔 Seoul | ~60ms |
| `sgp` | 新加坡 Singapore | ~80ms |
| `lax` | 洛杉矶 Los Angeles | ~150ms |

切换地区：修改 `.env` 中的 `VULTR_REGION`，然后 `python3 proxy.py rebuild`。完整列表可通过 `python3 proxy.py regions` 查看。

---

## 默认配置

- 套餐：`vc2-1c-1gb`（约 $5/月）
- 系统：Debian 12 x64
- 协议：VLESS + XTLS-Reality
- 端口：443
- SNI 伪装目标：`www.microsoft.com`

如需修改，编辑 `config.py`。

---

## 文件说明

```
proxy0/
├── proxy.py          # 主入口，所有命令
├── vultr.py          # Vultr API v2 封装
├── cloudinit.py      # 服务端 cloud-init 脚本生成
├── client_config.py  # 生成 VLESS 链接和 Clash YAML
├── config.py         # 配置读取（从 .env 或环境变量）
├── requirements.txt
├── .env.example      # 环境变量模板
└── .gitignore
```

运行后会生成：

- `.proxy_state.json` — 当前实例状态（ID、IP、UUID、Reality 公钥等）
- `clash_config.yaml` — Clash Meta 配置文件

---

## 安全说明

- `.env` 和 `.proxy_state.json` 已加入 `.gitignore`，不会提交到 git
- 服务器禁用 SSH 密码登录，仅允许 SSH Key 认证
- xray 仅监听 443 端口
- Reality 协议无需证书，流量特征接近真实 HTTPS
