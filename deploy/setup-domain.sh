#!/usr/bin/env bash
# 域名 + HTTPS 一键配置：把 api.zytzml.cn（接口）和 www.zytzml.cn（Web 后台）
# 接到本机 8000 端口的后端上，并签发 Let's Encrypt 证书。
#
# 前置条件（脚本会检查）：
#   1. DNS 已解析：zytzml.cn / api.zytzml.cn / www.zytzml.cn 的 A 记录指向本机公网 IP
#   2. 服务器 80 端口可从公网访问（certbot 的 HTTP-01 验证要用）
#   3. 后端已在 127.0.0.1:8000 运行
#
# 用法：sudo bash deploy/setup-domain.sh
set -euo pipefail

DOMAIN_ROOT="zytzml.cn"
DOMAIN_API="api.zytzml.cn"
DOMAIN_WWW="www.zytzml.cn"
SERVER_IP="43.128.26.65"
# 三个域名共用一张证书，用 --cert-name 固定目录名；
# 否则 certbot 按第一个 -d 命名目录，容易和 nginx 里写的路径对不上
CERT_NAME="zytzml.cn"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF_SRC="$REPO_DIR/deploy/nginx/zytzml.conf"
BOOTSTRAP="/etc/nginx/sites-available/yoga-bootstrap"
WEBROOT="/var/www/html"

info() { printf '\033[36m[信息]\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m[完成]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[错误]\033[0m %s\n' "$*"; }

reload_nginx() {
  systemctl reload nginx 2>/dev/null || systemctl start nginx
}

# ---------- 0. 环境检查 ----------
if [ "$(id -u)" -ne 0 ]; then err "请用 sudo 运行：sudo bash deploy/setup-domain.sh"; exit 1; fi
command -v nginx >/dev/null || { info "安装 nginx…"; apt update -qq && apt install -y nginx; }
command -v certbot >/dev/null || { info "安装 certbot…"; apt install -y certbot; }
mkdir -p "$WEBROOT"

# ---------- 1. DNS 解析检查 ----------
info "检查 DNS 解析（应为 $SERVER_IP）…"
DNS_OK=1
for d in "$DOMAIN_ROOT" "$DOMAIN_API" "$DOMAIN_WWW"; do
  resolved="$(dig +short "$d" 2>/dev/null | tail -1 || true)"
  [ -z "$resolved" ] && resolved="$(getent hosts "$d" | awk '{print $1}' | head -1 || true)"
  if [ "$resolved" = "$SERVER_IP" ]; then
    ok "$d -> $resolved"
  else
    err "$d 解析为 '${resolved:-未解析}'，不等于 $SERVER_IP"
    DNS_OK=0
  fi
done
if [ "$DNS_OK" -ne 1 ]; then
  err "请先在域名注册商处添加 A 记录（主机记录 @ / api / www，记录值 $SERVER_IP），"
  err "等生效（通常 1~10 分钟，最长 24 小时）后重跑本脚本。"
  exit 1
fi

# ---------- 2. 先换上「只管 80 端口」的临时配置 ----------
# 关键：服务器上现有的 nginx 很可能是把 / 整体反代给后端的，
# 那样 /.well-known/acme-challenge/ 也会被转给后端返回 404，
# certbot 的 HTTP-01 验证必然失败。所以必须先放一个放行 ACME 的 80 配置。
info "部署临时 HTTP 配置（放行证书验证，其余跳转 HTTPS）…"
# 备份当前已启用的站点，失败时可还原
ENABLED_BACKUP="$(mktemp)"
ls -1 /etc/nginx/sites-enabled 2>/dev/null > "$ENABLED_BACKUP" || true

cat > "$BOOTSTRAP" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_ROOT $DOMAIN_API $DOMAIN_WWW;

    # certbot HTTP-01 验证：必须直接从磁盘取文件，不能被反代
    location /.well-known/acme-challenge/ {
        root $WEBROOT;
        default_type "text/plain";
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF

# 只留 bootstrap，避免其它站点抢走 80 或把请求反代掉
find /etc/nginx/sites-enabled -maxdepth 1 -type l -delete 2>/dev/null || true
ln -sf "$BOOTSTRAP" /etc/nginx/sites-enabled/yoga-bootstrap
if ! nginx -t 2>&1 | tail -3; then
  err "临时配置校验失败，已还原原有站点"
  rm -f /etc/nginx/sites-enabled/yoga-bootstrap
  while read -r s; do
    [ -n "$s" ] && ln -sf "/etc/nginx/sites-available/$s" "/etc/nginx/sites-enabled/$s" 2>/dev/null || true
  done < "$ENABLED_BACKUP"
  reload_nginx || true
  exit 1
fi
reload_nginx
ok "80 端口已就绪"

# ---------- 3. 申请证书 ----------
if [ -d "/etc/letsencrypt/live/$CERT_NAME" ]; then
  ok "证书已存在（/etc/letsencrypt/live/$CERT_NAME），跳过签发"
else
  info "签发证书（$DOMAIN_ROOT, $DOMAIN_API, $DOMAIN_WWW）…"
  certbot certonly --webroot -w "$WEBROOT" \
    --cert-name "$CERT_NAME" \
    -d "$DOMAIN_ROOT" -d "$DOMAIN_API" -d "$DOMAIN_WWW" \
    --agree-tos --no-eff-email --keep-until-expiring
  ok "证书签发完成"
fi

# ---------- 4. 启用正式站点配置（含 443）----------
info "部署 nginx 正式配置…"
cp "$CONF_SRC" /etc/nginx/sites-available/yoga
find /etc/nginx/sites-enabled -maxdepth 1 -type l -delete 2>/dev/null || true
ln -sf /etc/nginx/sites-available/yoga /etc/nginx/sites-enabled/yoga
rm -f "$BOOTSTRAP"

if nginx -t 2>&1 | tail -3; then
  reload_nginx
  ok "nginx 已重载（HTTPS 生效）"
else
  err "nginx 配置校验失败，已回滚到临时 HTTP 配置，请检查 /etc/nginx/sites-available/yoga"
  rm -f /etc/nginx/sites-enabled/yoga
  cat > "$BOOTSTRAP" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_ROOT $DOMAIN_API $DOMAIN_WWW;
    location /.well-known/acme-challenge/ {
        root $WEBROOT;
        default_type "text/plain";
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF
  ln -sf "$BOOTSTRAP" /etc/nginx/sites-enabled/yoga-bootstrap
  reload_nginx || true
  exit 1
fi

# ---------- 5. 自动续期（续期后必须 reload 才会加载新证书）----------
info "配置证书自动续期…"
HOOK_DIR="/etc/letsencrypt/renewal-hooks/deploy"
mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/reload-nginx.sh" <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
chmod +x "$HOOK_DIR/reload-nginx.sh"
systemctl enable --now certbot.timer >/dev/null 2>&1 || true
ok "续期钩子已就绪（certbot.timer 每 12 小时检查一次）"

# ---------- 6. 验证 ----------
echo
info "验证结果："
API_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMAIN_API/api/health" || echo "失败")"
echo "  https://$DOMAIN_API/api/health  ->  $API_CODE"
echo "     （200 = 正常；000/502 = 后端未启动或端口不对；证书问题会直接报错）"

CERT_END="$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" 2>/dev/null | cut -d= -f2 || true)"
[ -n "$CERT_END" ] && echo "  证书有效期至：$CERT_END"

echo
ok "域名配置完成。下一步：到微信公众平台把 https://$DOMAIN_API 登记为"
echo "   request / uploadFile / downloadFile 合法域名（不填端口、不带路径）。"
echo "   未备案期间体验版需让顾客点右上角「⋯」→ 打开调试 才能正常请求。"
