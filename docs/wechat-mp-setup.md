# 微信公众平台后台配置指南（体验版上线必做）

> 适用场景：服务器已部署（v12 订阅制），域名 `api.zytzml.cn` 已备案且 HTTPS 已就绪，
> 现在要配置微信公众平台后台，让小程序能联网调用后端、并通过体验版发给顾客试用。
>
> AppID：`wx9044a46abff9cf68`

---

## 前置确认（应已就绪，不用再弄）

- [x] 域名 `api.zytzml.cn` 已完成 ICP 备案
- [x] HTTPS 证书已配置（Let's Encrypt / certbot）
- [x] 服务器后端已部署并运行（`/api/health` 返回 200）
- [x] `miniprogram/api.js` 中 `PROD_BASE = https://api.zytzml.cn`

---

## 第 1 步：服务器域名（最关键，也是触发校验文件的步骤）

1. 打开 **https://mp.weixin.qq.com** （微信公众平台，不是腾讯云域名控制台）。
2. 左侧菜单：**开发管理 → 开发设置 → 服务器域名**。
3. 在「修改」里填写以下合法域名（只填 https 开头的，不要带路径）：
   - **request 合法域名**：`https://api.zytzml.cn`
   - **uploadFile 合法域名**：`https://api.zytzml.cn`（体测图片上传用到）
   - **downloadFile 合法域名**：`https://api.zytzml.cn`（头像/图片下载用到）
   - **socket 合法域名**：`wss://api.zytzml.cn`（如用到 WebSocket 才填）
4. 点击 **「保存」**。

> ⚠️ **保存时会弹出一个提示：让你「下载校验文件 `MP_verify_xxxx.txt`」**。
> 这个文件名字里 `xxxx` 是微信随机生成的，**先别关这个页面**，直接跳到第 3 步把它放到服务器上，再回来点「验证」。

---

## 第 2 步：用户隐私保护指引

1. 左侧菜单：**设置 → 用户隐私保护指引 → 编辑**。
2. 勾选小程序实际用到的采集项（至少包含以下）：
   - 微信登录（openid / 用户信息）
   - 手机号（学员注册/绑定）
   - 相册 / 摄像头（体测拍照、上传）
   - 健康与运动数据（体测指标、训练记录）
3. 填写隐私接口使用说明，提交审核（通常很快，几分钟到几小时）。
4. 必须审核通过，否则小程序调用相关接口会被拦截。

---

## 第 3 步：把 `MP_verify_xxxx.txt` 校验文件放到服务器（承接第 1 步弹窗）

第 1 步保存时弹出的校验文件，微信会去 `https://api.zytzml.cn/MP_verify_xxxx.txt` 抓它来验证域名归属。
所以要把这个文件放到服务器、并且能通过上面的 URL 访问到。

1. **下载**弹窗里的 `MP_verify_xxxx.txt`（文件名是随机的，记好这个名字）。
2. **传到服务器**的 `/var/www/html/` 目录（nginx 的静态根目录）：
   ```bash
   # 假设文件已传到你的 home 目录
   sudo cp ~/MP_verify_*.txt /var/www/html/
   sudo chmod 644 /var/www/html/MP_verify_*.txt
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **验证能否访问**（把文件名换成你下载的那个）：
   ```bash
   curl -I https://api.zytzml.cn/MP_verify_xxxx.txt
   ```
   应返回 `HTTP/2 200`。
   - 若返回 **404**：说明 nginx 没有把这个文件暴露出来。确认 nginx 配置里有（或补上）这一段：
     ```nginx
     location /MP_verify_ {
         root /var/www/html;
     }
     ```
     > ⚠️ 常见坑：不要写成 `location = /MP_verify_*.txt { ... }`。
     > nginx 的 `=` 是**精确匹配**，不支持 `*` 通配符，随机后缀会直接 404。
     > 用前缀匹配 `/MP_verify_` 或正则 `location ~* ^/MP_verify_.*\.txt$` 才正确。
   - 改完配置记得 `sudo nginx -t && sudo systemctl reload nginx` 再测一次。
4. 返回**第 1 步那个微信页面**，点击「验证 / 确认」完成保存。验证通过后才算域名配置成功。

---

## 第 4 步：添加体验成员（让顾客能打开体验版）

1. 左侧菜单：**管理 → 成员管理 → 体验成员 → 添加**。
2. 输入**顾客的微信号**（不是昵称、不是手机号），保存。
3. 体验成员有数量上限（平台规则，通常为若干名）；若顾客超过体验版名额，需走正式版或企业主体。
   > 注意：体验版顾客仍需在体验成员名单内，否则扫码会提示「无权限」。

---

## 第 5 步：确认后端 AppID / AppSecret（登录态相关接口要用）

1. 登录服务器，检查环境变量：
   ```bash
   sudo grep '^WX_' /opt/yoga/backend/.env
   ```
   应能看到：
   ```
   WX_APPID=wx9044a46abff9cf68
   WX_SECRET=xxxxxxxxxxxxxxxx
   ```
2. 若 `WX_SECRET` 为空：
   - 到公众平台 **开发管理 → 开发设置 → AppSecret** 获取（需管理员扫码，只显示一次，妥善保存）。
   - 填入 `/opt/yoga/backend/.env` 的 `WX_SECRET=...`，然后重启：
     ```bash
     sudo systemctl restart yoga-backend
     ```
3. 改完用 `curl https://api.zytzml.cn/api/health` 确认后端仍 200。

---

## 第 6 步：上传体验版并给顾客二维码

1. 打开**微信开发者工具**，导入 `miniprogram` 目录。
2. 点「上传」，版本号随意（如 `1.0.0-trial`），备注写「体验版」。
3. 回到公众平台：**管理 → 版本管理 → 体验版 → 选中刚上传的版本 → 设为体验版**。
4. 点「二维码」下载体验版二维码，发给已在体验成员名单里的顾客扫码打开。

---

## 不阻塞试用的部分（可后补）

- **微信支付商户号 7 项配置 + 订阅定价**：只影响「学员付费 → 馆主开通/续期 AI」这条链路。
  注册、打卡、体测、训练计划生成在体验版里**仍可正常使用**，不影响顾客先试用核心功能。
- 商户配置齐全后，未订阅用户调用 AI 接口会走 `402` 弹窗引导订阅（已在 v12 实现）。

---

## 安全提醒（建议尽快处理）

- 本次沟通过程中 GitHub **PAT** 和管理员**初始密码**曾出现在聊天记录里。
  - 建议到 GitHub → Settings → Developer settings → Personal access tokens 把该 PAT **revoke**。
  - 登录服务器后用 `deploy/reset-admin.sh`（或已部署的等价脚本）**重置馆主密码**。
