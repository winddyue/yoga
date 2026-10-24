# 部署运维

## 架构

- 后端：FastAPI + SQLite（单馆规模；多馆/高并发时可迁 PostgreSQL）
- 前端：React + Vite 静态页面（可部署到同一服务器的 Nginx，或对象存储 + CDN）
- 小程序：微信小程序原生，`miniprogram/` 目录，调用同一后端

## 后端部署（Ubuntu 示例）

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# 环境变量（不要写进代码）
export DATABASE_URL="sqlite:///./yoga.db"
export JWT_SECRET="随机长字符串"
export DATA_ENC_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
# 可选第三方
export OCR_API_URL OCR_API_KEY AI_API_URL AI_API_KEY AI_MODEL ASR_API_URL ASR_API_KEY
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

建议用 systemd 托管 uvicorn，开机自启；前端 `npm run build` 产物用 Nginx 托管。

## 域名与 HTTPS（线上域名 zytzml.cn）

规划（服务器 43.128.26.65）：

| 用途 | 域名 | 说明 |
|---|---|---|
| 小程序接口 | `api.zytzml.cn` | 小程序后台登记的唯一合法域名 |
| Web 管理端 | `www.zytzml.cn` | 馆主/教练后台，浏览器访问 |

两者分开，后台改动不影响顾客端。

### 1. DNS 解析

在域名注册商处加两条 A 记录（主机记录填子域名，记录值填服务器 IP）：

| 主机记录 | 类型 | 记录值 |
|---|---|---|
| `api` | A | `43.128.26.65` |
| `www` | A | `43.128.26.65` |
| `@` | A | `43.128.26.65`（可选，裸域也指过去） |

验证（等 1~10 分钟生效）：

```bash
dig api.zytzml.cn +short   # 应返回 43.128.26.65
```

### 2. 证书与 Nginx

推荐直接跑脚本（含 DNS 校验、签发、配置校验、续期钩子，失败会自动回滚）：

```bash
sudo bash deploy/setup-domain.sh
```

手动步骤（想自己控制时用）：

```bash
sudo apt install -y nginx certbot
# 顺序很关键：必须先有证书，才能启用引用证书路径的配置，否则 nginx -t 直接失败
sudo certbot certonly --webroot -w /var/www/html --cert-name zytzml.cn \
     -d zytzml.cn -d api.zytzml.cn -d www.zytzml.cn
sudo cp deploy/nginx/zytzml.conf /etc/nginx/sites-available/yoga
sudo ln -sf /etc/nginx/sites-available/yoga /etc/nginx/sites-enabled/yoga
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

证书 90 天过期，续期后必须 reload nginx 才会加载新证书——续期钩子
`/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh` 已处理，
确认 `systemctl status certbot.timer` 正常即可。
微信要求 TLS ≥ 1.2，配置里已强制 TLSv1.2/1.3，自签证书不可用。

#### ⚠️ 大陆服务器 + 未备案域名：HTTP 验证会被劫持，必须用 DNS 验证

2026-10-24 实测：域名未备案时，**腾讯云内网对 80 端口的 HTTP 请求会劫持**，
返回一个体积很大的"域名未备案"拦截页面。Let's Encrypt 的多视角验证
（secondary validation）有验证机落在腾讯云内网，读到的响应体超限，
报 `unauthorized / Error reading HTTP response body: reader size limit exceeded`。
主验证点（境外）能通过也没用——只要有一个验证点失败，整张证书就拒签。

**结论：备案审核期间，HTTP-01（80 端口）验证在大陆腾讯云机器上不可用，
必须换 DNS-01 验证**（走 DNSPod API 加 TXT 记录，完全不碰 80 端口）：

```bash
# 1. 装 certbot + DNSPod 插件（Ubuntu 24.04 的 apt 源没有 dnspod 插件，走 pip venv）
python3 -m venv /opt/certbot-venv
/opt/certbot-venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    certbot certbot-dns-dnspod zope.interface

# 2. DNSPod 密钥（控制台 → 账号中心 → 密钥管理 → 创建密钥，ID + Token）
cat > /root/dnspod.ini <<'EOF'
dns_dnspod_api_id = 你的密钥ID(纯数字)
dns_dnspod_api_token = 你的密钥Token
EOF
chmod 600 /root/dnspod.ini

# 3. 签证书（DNS-01，-d 可多个域名）
/opt/certbot-venv/bin/certbot certonly --dns-dnspod \
    --dns-dnspod-credentials /root/dnspod.ini \
    -d api.zytzml.cn -d www.zytzml.cn \
    --non-interactive --agree-tos --register-unsafely-without-email

# 4. 续期：apt 的 certbot.timer 跑的是 /usr/bin/certbot（无 dnspod 插件），
#    必须换成 venv 里的 certbot，否则续期必失败
systemctl disable --now certbot.timer
echo '17 3 * * 1 root /opt/certbot-venv/bin/certbot renew -q --deploy-hook "systemctl reload nginx"' \
    > /etc/cron.d/certbot-renew
```

> 备案通过后 HTTP-01 恢复可用，但 DNS-01 无需更换，一把钥匙用到老。
> 另：`deploy/install.sh` 的 apt 列表曾漏装 certbot（提示语写了但安装行没写），
> 已于 2026-10-24 修复，新部署不会复现。

### 3. 小程序后台登记合法域名

公众平台 → 开发管理 → 开发设置 → 服务器域名，三类都填 `https://api.zytzml.cn`
（不填端口、不带路径）：

- request 合法域名
- uploadFile 合法域名
- downloadFile 合法域名

保存后约 5~10 分钟生效。

### 4. 未备案域名：体验版绕行方案

**微信小程序要求 request 合法域名必须完成 ICP 备案**；服务器在中国香港时无法
直接备案（备案要求服务器在大陆境内）。未备案期间按下面方式跑体验版：

- 顾客进入体验版后，点右上角「⋯」→ **打开调试**，确认后重新进入，请求不再校验
  域名备案状态。
- 开发者工具里勾选「不校验合法域名」仅供开发调试，真机无效。

要走正式版，二选一：

1. 加一台大陆境内服务器（或大陆 CDN）接入备案，周期约 10~25 个工作日；
2. 改用微信云托管/云开发，用微信自带域名，免备案、免证书。

### 5. 前端与管理端

```bash
cd frontend && npm install && npm run build
sudo mkdir -p /var/www/yoga-admin && sudo cp -r dist/* /var/www/yoga-admin/
```

后端环境变量需放开管理端来源：`CORS_ORIGINS=https://www.zytzml.cn,https://zytzml.cn`
（小程序请求不受跨域限制，此项只影响浏览器）。

## 备份

- SQLite 单文件：每日定时 `cp yoga.db /backup/yoga-$(date +%F).db`，保留 30 天。
- 备份文件同样含敏感数据，存放目录权限 600，仅运维可读。
- 恢复：停服务 → 替换 db 文件 → 启服务。

## 敏感字段加密方案

- 实现：`backend/app/services/crypto.py`，手机号用 Fernet（AES-128-CBC + HMAC）对称加密，
  数据库中以 `enc:` 前缀区分密文与明文。
- 密钥：`DATA_ENC_KEY` 环境变量（Fernet 32 字节 base64）。**密钥丢失则手机号无法解密，
  请随备份一并妥善保管（与数据库分开存放）。**
- 当前为基础版：仅加密手机号；评估备注、伤病史等字段后续按需扩展。
- 开发模式（未设置 `DATA_ENC_KEY`）下降级为明文存储并记录警告——**生产环境必须设置**。

## 日志与审计

- 关键写操作（客户/评估/计划/饮食/约课/签到/订阅/同意/设置）写入 `audit_logs` 表，
  含操作人、动作、对象、时间，可在出问题时追溯。
- 应用日志不记录密码、密钥、手机号明文。
