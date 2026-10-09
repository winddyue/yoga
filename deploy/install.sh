#!/usr/bin/env bash
# 瑜伽馆小程序 · 后端一键部署脚本（Ubuntu 22.04 / 24.04）
#
# 用法：
#   sudo bash /opt/yoga/deploy/install.sh                      # 只起后端 + HTTP（先用 IP 验证）
#   sudo bash /opt/yoga/deploy/install.sh api.abc.com          # 顺便申请 HTTPS 证书
#
# 域名要求：必须已经解析到本机公网 IP（A 记录），否则证书申请会失败。
#
# 特性：
#   - 幂等：可重复执行；已存在的 backend/.env 不会被覆盖（密钥不丢）
#   - 只跑后端：小程序不需要 Web 前端，所以不构建 frontend/，省内存省时间
#   - 用 systemd 托管，开机自启、崩溃自动重启
set -euo pipefail

DOMAIN="${1:-}"
REPO_URL="https://github.com/winddyue/yoga.git"
APP_ROOT="/opt/yoga"
BACKEND_DIR="$APP_ROOT/backend"
VENV="$BACKEND_DIR/.venv"
ENV_FILE="$BACKEND_DIR/.env"
SERVICE="/etc/systemd/system/yoga-backend.service"
CRED_FILE="/root/yoga-credentials.txt"

info() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[提醒] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[错误] %s\033[0m\n' "$*" >&2; exit 1; }

# ---------- 0. 前置检查 ----------
if [ "$(id -u)" -ne 0 ]; then
  die "请用 sudo 运行：sudo bash $0 ${DOMAIN}"
fi

if [ -n "$DOMAIN" ]; then
  case "$DOMAIN" in
    *[!a-zA-Z0-9.-]*) die "域名格式不对：$DOMAIN" ;;
  esac
fi

PUBLIC_IP="$(curl -fsS --max-time 8 https://ifconfig.me 2>/dev/null || echo '未知')"
info "本机公网 IP：$PUBLIC_IP"
[ -n "$DOMAIN" ] && info "目标域名：$DOMAIN （HTTPS）" || warn "未提供域名 → 本轮只配 HTTP，稍后可再跑一次带域名"

# ---------- 1. 系统依赖 ----------
info "安装系统依赖（python3-venv / nginx / certbot）"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx git curl openssl ca-certificates >/dev/null

# ---------- 2. 代码 ----------
if [ -d "$APP_ROOT/.git" ]; then
  info "代码已存在，拉取最新版本"
  git -C "$APP_ROOT" pull --ff-only || warn "git pull 失败（本地有改动？）继续使用当前代码"
else
  info "克隆代码到 $APP_ROOT"
  mkdir -p "$APP_ROOT"
  git clone --depth 1 "$REPO_URL" "$APP_ROOT"
fi
[ -f "$BACKEND_DIR/requirements.txt" ] || die "没找到 $BACKEND_DIR/requirements.txt，代码目录不对"

# ---------- 3. Python 依赖 ----------
if [ ! -x "$VENV/bin/python" ]; then
  info "创建虚拟环境"
  python3 -m venv "$VENV"
fi
info "安装 Python 依赖（首次约 1-3 分钟）"
"$VENV/bin/pip" install -q --upgrade pip wheel
"$VENV/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

# ---------- 4. 生成生产配置 ----------
mkdir -p "$BACKEND_DIR/data/uploads"

if [ -f "$ENV_FILE" ]; then
  warn "已存在 $ENV_FILE，保留原配置（不会覆盖密钥与管理员密码）"
  ADMIN_PASSWORD="$(grep -E '^ADMIN_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
else
  info "生成生产配置与随机密钥"
  SECRET_KEY="$(openssl rand -hex 32)"
  ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-16)"
  # Fernet 密钥：手机号等敏感字段的加密密钥。丢了就解不开，必须随数据库一起备份
  DATA_ENC_KEY="$("$VENV/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  if [ -n "$DOMAIN" ]; then CORS_LINE="CORS_ORIGINS=https://$DOMAIN"; else CORS_LINE=""; fi

  cat > "$ENV_FILE" <<EOF
# 自动生成于 $(date '+%Y-%m-%d %H:%M:%S')。含密钥，勿提交到 git、勿外传。
ENV=prod

# ---- 数据库与文件 ----
DATABASE_URL=sqlite:///./data/yoga.db
UPLOAD_DIR=./data/uploads

# ---- 安全 ----
SECRET_KEY=$SECRET_KEY
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
DATA_ENC_KEY=$DATA_ENC_KEY
$CORS_LINE

# ---- 微信小程序（去公众平台「开发管理 → 开发设置」抄，填完重启服务）----
WX_APPID=wx9044a46abff9cf68
WX_SECRET=
WX_DEV_MOCK=false
EOF
  chmod 600 "$ENV_FILE"
fi

# 备份密钥与初始密码到 root 专属文件，防止忘记
{
  echo "瑜伽馆后端凭据（$(date '+%Y-%m-%d %H:%M:%S') 生成）"
  echo "后台地址：http://${DOMAIN:-$PUBLIC_IP}/"
  echo "管理员账号：admin"
  echo "管理员密码：${ADMIN_PASSWORD:-见 $ENV_FILE}"
  echo
  echo "DATA_ENC_KEY 在 $ENV_FILE —— 手机号加密密钥，务必和数据库一起备份，丢了无法恢复"
} > "$CRED_FILE"
chmod 600 "$CRED_FILE"

# ---------- 5. systemd 托管 ----------
info "配置 systemd 服务"
cat > "$SERVICE" <<EOF
[Unit]
Description=Yoga Backend (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable -q yoga-backend
systemctl restart yoga-backend

info "等待后端启动"
OK=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then OK=1; break; fi
  sleep 2
done
if [ "$OK" -ne 1 ]; then
  echo "----- 最近日志 -----"
  journalctl -u yoga-backend -n 40 --no-pager || true
  die "后端未能启动，请看上面日志"
fi
echo "后端启动成功：http://127.0.0.1:8000/api/health"

# ---------- 6. Nginx 反向代理 ----------
info "配置 Nginx"
SERVER_NAME="${DOMAIN:-_}"
cat > /etc/nginx/sites-available/yoga <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name __SERVER_NAME__;

    # 小程序要传照片，放宽请求体上限（与后端 MAX_UPLOAD_BYTES 对齐）
    client_max_body_size 12m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
NGINX
sed -i "s/__SERVER_NAME__/$SERVER_NAME/" /etc/nginx/sites-available/yoga

ln -sf /etc/nginx/sites-available/yoga /etc/nginx/sites-enabled/yoga
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# 本机可能开了 ufw，顺手放行（腾讯云控制台的防火墙要另外开，见最后提示）
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow 80/tcp >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
fi

# ---------- 7. HTTPS ----------
if [ -n "$DOMAIN" ]; then
  info "为 $DOMAIN 申请 Let's Encrypt 证书"
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
       --register-unsafely-without-email --redirect; then
    echo "HTTPS 已启用：https://$DOMAIN/api/health"
  else
    warn "证书申请失败。常见原因：域名没解析到 $PUBLIC_IP、443 端口未在腾讯云防火墙放行。"
    warn "修好后重跑：sudo bash $0 $DOMAIN"
  fi
fi

# ---------- 8. 收尾验证 ----------
info "最终验证"
curl -fsS --max-time 5 http://127.0.0.1:8000/api/health && echo

cat <<EOF

──────────────────────────── 部署完成 ────────────────────────────
后端状态    systemctl status yoga-backend
查看日志    journalctl -u yoga-backend -f

访问地址    ${DOMAIN:+https://$DOMAIN}${DOMAIN:-http://$PUBLIC_IP}
管理员账号  admin
管理员密码  ${ADMIN_PASSWORD:-见 $ENV_FILE}
（同样记录在 $CRED_FILE，权限 600，只有 root 能看）

下一步（必须做，否则顾客登不进来）：
  1. 去公众平台「开发管理 → 开发设置」拿到 AppSecret，
     填进 $ENV_FILE 的 WX_SECRET= 后面，然后：
       sudo systemctl restart yoga-backend
  2. 腾讯云控制台「轻量应用服务器 → 防火墙」放行 80、443
     （80 用于证书续期，443 用于 HTTPS，缺一不可）
  3. 公众平台「开发管理 → 开发设置 → 服务器域名」把 request 合法域名
     填成 ${DOMAIN:+https://$DOMAIN}${DOMAIN:-https://你的域名}
  4. 自检接口：http://127.0.0.1:8000/api/health 应返回 {"ok":true}

备份提醒：
  数据库  $BACKEND_DIR/data/yoga.db
  加密密钥 $ENV_FILE 里的 DATA_ENC_KEY
  两者必须一起备份。只备份数据库而丢了密钥，手机号将永远无法解密。
────────────────────────────────────────────────────────────────────
EOF
