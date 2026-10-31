#!/usr/bin/env bash
# 重置馆主（admin）密码。
#
# 用法：sudo bash /opt/yoga/deploy/reset-admin.sh
#
# 什么时候需要：
#   - 部署脚本生成的初始密码只打印过一次，丢了/泄露了
#   - 系统里没有任何改密码的界面，只能这样改
#
# 说明：
#   - 同时更新 .env 里的 ADMIN_PASSWORD（保证以后重装/重建账号时一致）
#   - 直接改库里 admin 的密码哈希，**不影响任何其他数据**（客户、评估、打卡都在）
#   - 新密码会打印在屏幕上，记得存好
set -euo pipefail

BACKEND_DIR="/opt/yoga/backend"
ENV_FILE="$BACKEND_DIR/.env"
VENV="$BACKEND_DIR/.venv"

if [ "$(id -u)" -ne 0 ]; then
  echo "[错误] 请用 sudo 运行：sudo bash $0" >&2
  exit 1
fi
[ -f "$ENV_FILE" ] || { echo "[错误] 找不到 $ENV_FILE，后端没部署在这台机器上？" >&2; exit 1; }
[ -x "$VENV/bin/python" ] || { echo "[错误] 找不到虚拟环境 $VENV" >&2; exit 1; }

# hex 不会出现 / + = 这些在 .env 和 shell 里需要转义的字符，比 base64 稳
NEW_PW="$(openssl rand -hex 8)"

sed -i "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$NEW_PW/" "$ENV_FILE"

# 必须在 chdir 之后再 import app：config.py 的 env_file=".env" 是相对当前工作目录的
"$VENV/bin/python" - "$NEW_PW" <<'PY'
import os, sys
sys.path.insert(0, "/opt/yoga/backend")
os.chdir("/opt/yoga/backend")

from app.database import SessionLocal
from app import models
from app.auth import hash_password

new_pw = sys.argv[1]
db = SessionLocal()
try:
    u = db.query(models.User).filter(models.User.username == "admin").first()
    if not u:
        print("[错误] 库里没有 admin 用户，没法改" , file=sys.stderr)
        sys.exit(1)
    u.password_hash = hash_password(new_pw)
    db.commit()
    print("admin 密码已更新")
finally:
    db.close()
PY

systemctl restart yoga-backend
sleep 3
if curl -fsS --max-time 5 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "服务已重启，健康检查通过"
else
  echo "[警告] 服务重启后健康检查没通过，看日志：journalctl -u yoga-backend -n 50" >&2
fi

cat <<EOF

──────────── 新密码 ────────────
账号  admin
密码  $NEW_PW

立即存到密码管理器，然后登录验证一次。
EOF
