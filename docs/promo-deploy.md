# 拓客裂变 MVP 上线清单

对应代码：`backend/app/routers/promo.py`（接口）、`backend/app/models.py`（6 张 `promo_*` 表）。
新表靠后端启动时的 `create_all` 自动建，无需手动迁移。

## 一、Dylan 去办（微信侧）

1. **服务号认证**：mp.weixin.qq.com 注册服务号 → 微信认证（300 元/年，需营业执照，个体户即可）。
   订阅号权限不够，网页授权拿 openid 必须服务号。
2. **公众号后台配置**（认证通过后）：设置与开发 → 公众号设置 → 功能设置
   - **网页授权域名**：填活动页域名（如 `hd.zytzml.cn`，只填域名不加 `https://`，按提示下载验证文件放到该域名根目录）
   - **JS 接口安全域名**：同上（如需自定义分享标题/图片时用，MVP 可先不配）
3. **微信支付商户号**：MVP 不需要。只有做到在线收款/拼团付款时才申请（同样要营业执照+法人银行卡）。

## 二、代码同步（workspace → winddyue/yoga）

workspace 这边不是 git 仓库，部署前把下面变更同步到你 GitHub 仓库：

- 新增：`backend/app/routers/promo.py`、`backend/app/tests/test_promo.py`
- 修改：`backend/app/models.py`（新增 `PromoUser/PromoActivity/PromoShare/PromoVisit/PromoGroup/PromoSignup` 6 个模型）、
  `backend/app/config.py`（新增 4 个配置项）、`backend/app/main.py`（注册 `promo.router`）

同步后在你仓库跑一遍测试确认：`pytest app/tests/ -q`（应 40+ 通过，含拓客全流程）。

## 三、服务器环境变量（4 个新增 + 1 个已有）

```bash
export WX_MP_APPID="你的服务号 AppID"
export WX_MP_SECRET="你的服务号 Secret"
export PROMO_FRONT_URL="https://hd.zytzml.cn"   # 活动静态页的公网地址（模板工具导出的 HTML 放这里）
export PUBLIC_API_URL="https://api.zytzml.cn"   # 后端接口的公网地址（用于拼微信 OAuth 回调地址）
export DATA_ENC_KEY="..."                        # 已有：报名手机号加密存储依赖它，生产必须配
```

`WX_DEV_MOCK=true` 仅本地联调用，生产千万别开。

## 四、活动页部署

1. Nginx 新增 server 块（或复用现有站点目录）：`hd.zytzml.cn` → 静态目录，HTTPS（参考 `docs/deployment.md` 的 certbot 流程）。
2. 馆主登录后台 → `POST /api/promo/admin/activities`
   `{"title":"双十一3人拼团","status":"active","group_size":3}` → 拿到活动 `id`。
3. 打开推广页模板工具，在「对接配置」里填：后端接口地址（`https://api.zytzml.cn`）、活动 ID、活动页地址（`https://hd.zytzml.cn`），导出 HTML 上传到第 1 步的目录。
4. 顾客链路：打开活动页 → 点「立即报名」→ 微信 OAuth → 回到活动页（带登录态）→ 填姓名手机号报名 → 「生成我的专属链接」转发 → 好友打开归因到你名下 → 后台看板看访问/报名/推荐关系 → 到店核销。

## 五、联调

- 服务号下来之前：后端 `WX_DEV_MOCK=true` 启动，用 `code=mock:任意标识` 可走通 OAuth→归因→报名→成团→核销全流程（`test_promo.py` 即此逻辑）。
- 服务号就绪后：真机微信内打开活动页走一遍，重点看 OAuth 回调能否跳回活动页、分享链接验签是否通过。
