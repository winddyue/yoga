# -*- coding: utf-8 -*-
"""拓客裂变 MVP 测试：OAuth 归因、专属分享链接、报名、拼团、后台看板。
全程用 WX_DEV_MOCK 走通，不依赖真实微信。"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_promo.db"
os.environ["WX_DEV_MOCK"] = "true"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_promo.db"):
    os.remove("test_promo.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _oauth(client: TestClient, who: str, state: str = "") -> dict:
    r = client.get("/api/promo/oauth/callback",
                   params={"code": f"mock:{who}", "state": state})
    assert r.status_code == 200, r.text
    return r.json()


def test_promo_full_flow():
    with TestClient(app) as client:
        owner_h = _h(_login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD))

        # 1. 馆主创建活动：3 人成团
        r = client.post("/api/promo/admin/activities",
                        json={"title": "双十一3人拼团", "status": "active",
                              "group_size": 3, "rules": "99元享3节团课"},
                        headers=owner_h)
        assert r.status_code == 200, r.text
        act_id = r.json()["id"]

        # 2. A 进入活动页（无推荐人），拿到专属分享链接
        a = _oauth(client, "userA", state=str(act_id))
        a_h, a_token = _h(a["token"]), a["token"]
        r = client.get("/api/promo/share-link", params={"activity_id": act_id}, headers=a_h)
        assert r.status_code == 200, r.text
        a_ref = r.json()["ref_code"]
        assert r.json()["url"].endswith(f"ref={a_ref}&sig=" + r.json()["url"].rsplit("sig=", 1)[1])

        # 3. B 通过 A 的链接进入：归因到 A
        b = _oauth(client, "userB", state=f"{act_id}:{a_ref}")
        assert b["referrer"] and b["referrer"]["nickname"].endswith("serA"), b
        b_h = _h(b["token"])

        # 4. 验签：合法链接通过，篡改签名拒绝
        good = client.get("/api/promo/share/verify",
                          params={"activity_id": act_id, "ref": a_ref,
                                  "sig": r.json()["url"].rsplit("sig=", 1)[1]})
        assert good.json()["valid"] is True, good.text
        bad = client.get("/api/promo/share/verify",
                         params={"activity_id": act_id, "ref": a_ref, "sig": "deadbeef"})
        assert bad.json()["valid"] is False

        # 5. 手机号格式校验
        r = client.post("/api/promo/signup",
                        json={"activity_id": act_id, "name": "B", "phone": "123"},
                        headers=b_h)
        assert r.status_code == 400 and "手机号" in r.json()["detail"]

        # 6. B 报名：归因给 A，自己开团（1/3）
        r = client.post("/api/promo/signup",
                        json={"activity_id": act_id, "name": "小B", "phone": "13800138001"},
                        headers=b_h)
        assert r.status_code == 200, r.text
        assert r.json()["group"]["members"] == 1
        assert r.json()["group"]["status"] == "forming"
        # 重复报名拒绝
        r = client.post("/api/promo/signup",
                        json={"activity_id": act_id, "name": "小B", "phone": "13800138001"},
                        headers=b_h)
        assert r.status_code == 400

        # 7. A 报名（不用自己的推荐码）：加入 B 的团（2/3）
        r = client.post("/api/promo/signup",
                        json={"activity_id": act_id, "name": "小A", "phone": "13800138002"},
                        headers=a_h)
        assert r.json()["group"]["members"] == 2, r.text

        # 8. C 通过 A 的链接进入并报名：团满（3/3）
        c = _oauth(client, "userC", state=f"{act_id}:{a_ref}")
        c_h = _h(c["token"])
        r = client.post("/api/promo/signup",
                        json={"activity_id": act_id, "name": "小C",
                              "phone": "13800138003", "ref": a_ref},
                        headers=c_h)
        assert r.json()["group"]["status"] == "full", r.text
        assert r.json()["group"]["members"] == 3

        # 9. B 查我的拼团：已成团，3 名成员
        r = client.get("/api/promo/my-group", params={"activity_id": act_id}, headers=b_h)
        g = r.json()
        assert g["in_group"] and g["status"] == "full" and len(g["members"]) == 3, g

        # 10. 后台：报名列表（手机号解密）、推荐看板、核销
        r = client.get("/api/promo/admin/signups",
                       params={"activity_id": act_id}, headers=owner_h)
        signups = r.json()
        assert len(signups) == 3, signups
        phones = {s["name"]: s["phone"] for s in signups}
        assert phones["小B"] == "13800138001", phones  # 解密正确
        refs = {s["name"]: s["referrer"] for s in signups}
        assert refs["小B"].endswith("serA") and refs["小C"].endswith("serA"), refs

        r = client.get("/api/promo/admin/referrals",
                       params={"activity_id": act_id}, headers=owner_h)
        board = {x["nickname"]: x for x in r.json()}
        a_board = [v for k, v in board.items() if k.endswith("serA")][0]
        assert a_board["visits"] == 2 and a_board["signups"] == 2, a_board

        sid = [s["id"] for s in signups if s["name"] == "小B"][0]
        r = client.post(f"/api/promo/admin/signups/{sid}/verify", headers=owner_h)
        assert r.json()["status"] == "verified"

        # 11. 未配置公众号时 /oauth/url 给出可操作的提示
        r = client.get("/api/promo/oauth/url", params={"activity_id": act_id})
        assert r.status_code == 400 and "WX_MP_APPID" in r.json()["detail"], r.text

        # 12. 非馆主调后台接口被拒绝
        r = client.get("/api/promo/admin/activities", headers=b_h)
        assert r.status_code in (401, 403), r.text
