#!/usr/bin/env bash
# 瑜伽馆小程序 · 后端更新脚本（拉最新代码 + 装依赖 + 重启 + 续期证书）
#
# 用法（在服务器上，需 root）：
#   sudo bash /opt/yoga/deploy/update.sh
#
# 适用场景：代码已推送到 GitHub main，需要让线上服务器同步到最新。
# 脚本只更新代码与运行环境，不会改动 backend/.env（密钥 / 密码 / 商户配置都保留）。
set -euo pipefail

APP_ROOT="/opt/yoga"
BACKEND_DIR="$APP_ROOT/backend"
VENV="$BACKEND_DIR/.venv"
ENV_FILE="$BACKEND_DIR/.env"
SERVICE="yoga-backend"

info() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[提醒] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[错误] %s\033[0m\n' "$*" >&2; exit 1; }

# ---------- 0. 前置检查 ----------
if [ "$(id -u)" -ne 0 ]; then
  die "请用 sudo 运行：sudo bash $0"
fi
[ -d "$APP_ROOT/.git" ] || die "$APP_ROOT 不是 git 仓库（本脚本面向 git clone 部署方式）。请改用 install.sh 重新部署。"
[ -x "$VENV/bin/python" ] || die "找不到虚拟环境 $VENV，可能未用 install.sh 部署过。"

# ---------- 1. 拉取最新代码 ----------
info "拉取最新代码（与 GitHub main 对齐）"
cd "$APP_ROOT"
git pull --ff-only || warn "git pull 失败，继续使用当前代码（如需强制同步可手动：git fetch origin && git reset --hard origin/main）"
echo "当前部署版本： $(git rev-parse --short HEAD)  $(git log -1 --format='%s')"

# ---------- 2. 安装 / 更新 Python 依赖 ----------
# 新版本可能新增依赖（如微信支付 / 订阅），必须重装，否则 import 新包会 500
info "更新 Python 依赖"
"$VENV/bin/pip" install -q --upgrade pip wheel
"$VENV/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

# ---------- 3. 重启服务 ----------
# 项目用 SQLAlchemy create_all 自动建表，重启即应用新表结构（无需手动迁移）
info "重启 $SERVICE"
systemctl daemon-reload
systemctl restart "$SERVICE"

info "等待后端启动"
OK=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then OK=1; break; fi
  sleep 2
done
if [ "$OK" -ne 1 ]; then
  echo "----- 最近日志 -----"
  journalctl -u "$SERVICE" -n 40 --no-pager || true
  die "后端未能启动，请看上面日志"
fi
echo "后端启动成功：http://127.0.0.1:8000/api/health"

# ---------- 4. 续期证书（如有） ----------
if command -v certbot >/dev/null 2>&1; then
  info "续期 Let's Encrypt 证书（未到期会自动跳过）"
  certbot renew --quiet || warn "证书续期失败（不影响运行，可稍后手动 certbot renew）"
  systemctl reload nginx 2>/dev/null || true
fi

# ---------- 5. 收尾 ----------
info "最终验证"
curl -fsS --max-time 5 http://127.0.0.1:8000/api/health && echo
echo
cat <<EOF
──────────────────────────── 更新完成 ────────────────────────────
后端状态    systemctl status $SERVICE
查看日志    journalctl -u $SERVICE -f

如尚未完成，请补这几步：
  1. 确认 $ENV_FILE 中 WX_APPID / WX_SECRET / WXPAY_* 等已填写并重启过服务
  2. 公众平台「服务器域名」request + uploadFile 都填 https://api.zytzml.cn
  3. 配置《用户隐私保护指引》（勾 微信登录 / 手机号 / 相册 / 摄像头 / 健康数据）
  4. 微信开发者工具上传代码 → 版本管理设为体验版 → 发二维码给顾客
────────────────────────────────────────────────────────────────────
EOF
