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

## HTTPS 配置（生产必须）

1. 域名解析到服务器，申请证书（以 certbot + Let's Encrypt 为例）：
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```
2. Nginx 反向代理到 `127.0.0.1:8000`，强制 80 → 443 跳转。
3. certbot 会自动续期；确认 `systemctl status certbot.timer` 正常。
4. 小程序 request 域名必须使用 HTTPS，并在小程序后台配置合法域名。

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
