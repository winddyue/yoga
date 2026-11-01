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

## 重置管理员密码

首次部署时 `deploy/install.sh` 会为管理员**随机生成强密码**（默认账号 `admin`，
默认密码 `admin123` 仅在未覆盖环境变量时生效）。若忘记或需要重置，按以下任一方式操作。

### 方式一：一键脚本（推荐）

SSH 登录服务器后执行：

```bash
cd /opt/yoga
sudo ./deploy/reset-admin.sh   # 普通用户加 sudo；root 可省略
```

脚本会打印新的管理员密码，记下即可。

### 方式二：后端代码直写（脚本缺失时兜底）

当 `deploy/reset-admin.sh` 不存在时（例如仓库开发线已清理部署脚本），
直接在后端目录用虚拟环境重置：

```bash
cd /opt/yoga/backend
source /opt/yoga/venv/bin/activate   # 虚拟环境路径以实际为准

python - <<'PY'
from app.database import SessionLocal
from app import models
from app.auth import hash_password

db = SessionLocal()
u = db.query(models.User).filter(models.User.username == "admin").first()
if not u:
    u = models.User(username="admin", role="owner", name="馆主")
    db.add(u)
u.password_hash = hash_password("YogaTest@2026")
u.is_active = True
db.commit()
print("管理员 admin 密码已重置为：YogaTest@2026")
PY
```

密码为直写数据库，一般无需重启；若登录异常再 `sudo systemctl restart yoga-backend`。

### 说明

- 密码使用 `passlib` 的 bcrypt 哈希，库内只存哈希值，不存明文。
- 管理员角色为 `owner`，可进入馆主后台（订阅套餐管理、教练/客户管理等）。
- 测试号 / 开发者工具自测时，须用「账号密码登录」；微信一键登录在测试号下不可用
  （测试号 `wx.code` 与正式号 `WX_APPID/SECRET` 不匹配）。
