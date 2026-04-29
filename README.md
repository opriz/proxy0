# proxy0

一键部署 VLESS+Reality 代理服务器，支持 **Vultr** 和 **阿里云** 双平台，IP 被封时可快速销毁重建换 IP。

English version: [README.en.md](README.en.md)

---

## 原理

本地脚本调用云厂商 API 创建 VPS，通过 `user_data`（cloud-init）在服务器首次启动时自动安装并配置 xray。创建完成后脚本通过 SSH 读取服务端生成的 Reality 公钥等信息，生成客户端配置。IP 被封时一条命令销毁重建，约 4 分钟得到新 IP。

---

## 前置条件

- Python 3.8+
- Vultr 账号 或 阿里云账号
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
# Vultr 配置（可选）
VULTR_API_KEY=your_vultr_api_key
VULTR_SSH_KEY_ID=your_ssh_key_id
VULTR_REGION=icn

# 阿里云配置（可选）
ALIYUN_ACCESS_KEY=your_aliyun_ak
ALIYUN_ACCESS_SECRET=your_aliyun_sk
ALIYUN_PW=your_root_password
```

**获取 Vultr SSH Key ID：**
先在 Vultr 控制台 Account → SSH Keys 上传本地公钥，复制显示的 ID 填入 `.env`。

**阿里云密码：**
在阿里云轻量控制台重置服务器密码，填入 `ALIYUN_PW`。

---

## 统一入口（推荐）

使用 `main.py` 管理所有平台：

```bash
# Vultr 命令
python3 main.py vultr create              # 创建 Vultr 服务器
python3 main.py vultr destroy             # 销毁 Vultr 服务器
python3 main.py vultr rebuild             # 重建 Vultr 服务器
python3 main.py vultr config              # 显示 Vultr 配置
python3 main.py vultr status              # 查看 Vultr 状态
python3 main.py vultr check               # 检测 Vultr 连通性
python3 main.py vultr regions             # 列出 Vultr 地区

# 阿里云命令
python3 main.py aliyun list               # 列出阿里云实例
python3 main.py aliyun deploy <ip>        # 部署到阿里云实例
python3 main.py aliyun config             # 显示阿里云配置
python3 main.py aliyun status             # 查看阿里云状态
python3 main.py aliyun check              # 检测阿里云连通性
python3 main.py aliyun destroy            # 销毁阿里云服务器
python3 main.py aliyun rebuild            # 重建阿里云服务器

# 自动检测命令（有哪个显示哪个）
python3 main.py status                    # 显示所有配置的服务器状态
python3 main.py config                    # 显示所有配置的服务器配置
python3 main.py check                     # 检测所有服务器连通性
```

---

## Vultr 使用指南

### 创建服务器

```bash
python3 main.py vultr create
```

### 常用命令

| 命令 | 说明 |
|------|------|
| `python3 main.py vultr create` | 创建服务器并输出客户端配置 |
| `python3 main.py vultr destroy` | 销毁当前服务器（停止计费）|
| `python3 main.py vultr rebuild` | 销毁并重建，用于 IP 被封时换 IP |
| `python3 main.py vultr config` | 重新显示客户端配置 |
| `python3 main.py vultr status` | 查看当前服务器状态 |
| `python3 main.py vultr check` | 检测 IP 连通性（TCP + Ping）|
| `python3 main.py vultr regions` | 列出所有可用地区 |

### 推荐地区

| 代码 | 地区 | 延迟参考 |
|------|------|---------|
| `nrt` | 东京 Tokyo | ~50ms |
| `itm` | 大阪 Osaka | ~55ms |
| `icn` | 首尔 Seoul | ~60ms |
| `sgp` | 新加坡 Singapore | ~80ms |
| `lax` | 洛杉矶 Los Angeles | ~150ms |

---

## 阿里云使用指南

### 购买服务器

1. 访问 https://swasnext.console.aliyun.com/buy
2. 选择：**中国香港** 地域
3. 镜像：**Alibaba Cloud Linux** 或 **Debian 12**
4. 套餐：入门型（30元/月）或 锐驰型（40元/月不限流）
5. 购买后记录 **公网 IP**，在控制台重置 **root 密码**

### 部署代理

```bash
# 方式1：指定 IP 部署
python3 main.py aliyun deploy 8.x.x.x

# 方式2：列出已有实例，选择部署
python3 main.py aliyun deploy
```

### 常用命令

| 命令 | 说明 |
|------|------|
| `python3 main.py aliyun list` | 列出所有实例 |
| `python3 main.py aliyun deploy <ip>` | 部署 xray 到指定实例 |
| `python3 main.py aliyun config` | 显示客户端配置 |
| `python3 main.py aliyun status` | 查看当前服务器状态 |
| `python3 main.py aliyun check` | 检测 IP 连通性 |
| `python3 main.py aliyun destroy` | 销毁当前服务器 |
| `python3 main.py aliyun rebuild` | 销毁并重建 |

### 阿里云特点

- **延迟低**：到香港节点约 30-50ms（比 Vultr 韩国快）
- **带宽大**：200Mbps 峰值（锐驰型）
- **换 IP 限制**：每月可免费更换 3 次 IP

---

## 默认配置

- 套餐：最低配（约 $5/月 或 30元/月）
- 协议：**VLESS + XTLS-Reality**
- 端口：**443**
- SNI 伪装目标：`www.microsoft.com`
- 规则：Anthropic 域名强制走代理

如需修改，编辑 `core/config.py` 或 `.env`。

---

## 文件说明

```
proxy0/
├── main.py                       # 统一入口
├── SKILL.md                      # 给 AI agent 用的完整说明
├── core/                         # 平台无关的共享代码
│   ├── config.py                 # 读取 .env / 环境变量
│   ├── client_config.py          # 生成 VLESS 链接 / Clash YAML
│   └── connectivity.py           # state 文件、TCP/ping 探活
├── providers/
│   ├── vultr/                    # Vultr 实现
│   │   ├── api.py / cloudinit.py / manager.py
│   │   └── SETUP.md              # 如何申请 AK
│   └── aliyun/                   # 阿里云 SWAS 实现
│       ├── api.py / deploy_script.py / manager.py
│       └── SETUP.md              # 如何申请 AK/SK
├── .env.example
├── requirements.txt
└── .gitignore
```

新增云厂商时只需在 `providers/<name>/` 下放一个带 `COMMANDS` dict 的 `manager.py`，然后在 `main.py` 的 `PROVIDERS` 注册即可。

运行后会生成（已加入 .gitignore）：

- `.proxy_state.json` — Vultr 实例状态
- `.proxy_state_aliyun.json` — 阿里云实例状态
- `clash_config.yaml` — Vultr Clash 配置
- `clash_config_aliyun.yaml` — 阿里云 Clash 配置

---

## 安全说明

- `.env` 和所有状态文件已加入 `.gitignore`，不会提交到 git
- 服务器禁用 SSH 密码登录，仅允许 SSH Key 认证（部署完成后）
- xray 仅监听 443 端口
- Reality 协议无需证书，流量特征接近真实 HTTPS

---

## 快捷别名

为简化输入，你可以在 shell 配置中添加别名：

```bash
# ~/.zshrc 或 ~/.bashrc
alias vultr='python3 ~/github/proxy0/main.py vultr'
alias aliyun='python3 ~/github/proxy0/main.py aliyun'
alias proxy='python3 ~/github/proxy0/main.py'
```

然后可以直接使用：
```bash
vultr status      # 等同于 python3 main.py vultr status
aliyun config     # 等同于 python3 main.py aliyun config
proxy check       # 检查所有服务器
```

---

## 平台对比

| 特性 | Vultr | 阿里云 |
|------|-------|--------|
| 价格 | $5/月 (~36元) | 30-40元/月 |
| 延迟 | 50-150ms | 30-50ms |
| 带宽 | 1Gbps | 200Mbps |
| 流量 | 不限 | 500GB-不限 |
| 换 IP | 不限次数 | 3次/月 |
| 稳定性 | 高 | 高 |
| 被封风险 | 低 | 中 |

**建议**：国内用户优先选择 **阿里云香港**，延迟更低；需要频繁换 IP 选 **Vultr**。
