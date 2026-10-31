# -*- coding: utf-8 -*-
"""微信支付 v3：JSAPI 统一下单 / 调起参数签名 / 退款 / 回调验签解密。

场景：C 端学员付钱给瑜伽馆（馆主商户号；商户平台把小程序 AppID 绑定到商户号）。
只用 stdlib + cryptography 发请求（urllib），不引入 requests。
HTTP 出口统一走 _api_request，便于测试 mock。

签名方案（微信支付 v3 规范）：
- 商户请求签名：RSA-SHA256，签名串为
  "{method}\\n{canonical_url}\\n{timestamp}\\n{nonce}\\n{body}\\n"，
  Authorization: WECHATPAY2-SHA256-RSA2048 ...
- 回调验签：微信平台证书公钥验签
  "{timestamp}\\n{nonce}\\n{body}\\n"，timestamp 漂移超过 5 分钟拒收；
- 回调 resource 解密：APIv3Key 做 AES-256-GCM。
"""
import base64
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings

API_BASE = "https://api.mch.weixin.qq.com"
# 回调时间戳允许漂移（秒），防重放
NOTIFY_TIME_SKEW = 300


class WxPayError(Exception):
    """微信支付调用/验签失败。"""


def is_configured() -> bool:
    """商户号四件套 + API 证书私钥 + 回调地址是否配齐。"""
    return all([
        settings.WXPAY_APPID, settings.WXPAY_MCHID, settings.WXPAY_APIV3_KEY,
        settings.WXPAY_NOTIFY_URL, settings.WXPAY_PRIVATE_KEY,
        settings.WXPAY_CERT_SERIAL,
    ])


def _require_config() -> None:
    if not is_configured():
        raise WxPayError("馆主尚未配置微信支付")


def _pem_text(raw: str) -> str:
    # 环境变量里 \n 常写成字面量 \\n，两种都兼容
    t = (raw or "").strip().replace("\\n", "\n")
    return t


def _load_private_key():
    pem = _pem_text(settings.WXPAY_PRIVATE_KEY)
    if "PRIVATE KEY" not in pem:
        raise WxPayError("WXPAY_PRIVATE_KEY 不是有效 PEM 私钥")
    try:
        return serialization.load_pem_private_key(pem.encode(), password=None)
    except Exception as e:
        raise WxPayError(f"私钥解析失败：{e}")


def _sign(message: str) -> str:
    key = _load_private_key()
    sig = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def _auth_header(method: str, canonical_url: str, body: str = "") -> Dict[str, str]:
    """v3 商户请求签名头。canonical_url 为 path+query，不含域名。"""
    _require_config()
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    message = f"{method}\n{canonical_url}\n{timestamp}\n{nonce}\n{body}\n"
    signature = _sign(message)
    serial = settings.WXPAY_CERT_SERIAL.strip()
    auth = (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{settings.WXPAY_MCHID}",'
        f'nonce_str="{nonce}",signature="{signature}",'
        f'timestamp="{timestamp}",serial_no="{serial}"'
    )
    return {"Authorization": auth, "Wechatpay-Serial": serial}


def _api_request(method: str, path: str,
                 payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """v3 API 通用调用（测试时 mock 此函数即可，不碰网络）。"""
    body = json.dumps(payload or {}, ensure_ascii=False)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers.update(_auth_header(method, path, body if method != "GET" else ""))
    req = urllib.request.Request(API_BASE + path,
                                 data=(body.encode() if method != "GET" else None),
                                 method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise WxPayError(f"微信接口 {path} 返回 {e.code}：{detail}")


# ---------- 统一下单 / 调起参数 ----------

def jsapi_unified_order(*, description: str, out_trade_no: str,
                        amount_cents: int, openid: str,
                        notify_url: str = "") -> str:
    """JSAPI 统一下单，返回 prepay_id（2 小时有效）。"""
    payload = {
        "appid": settings.WXPAY_APPID,
        "mchid": settings.WXPAY_MCHID,
        "description": description,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url or settings.WXPAY_NOTIFY_URL,
        "amount": {"total": amount_cents, "currency": "CNY"},
        "payer": {"openid": openid},
    }
    resp = _api_request("POST", "/v3/pay/transactions/jsapi", payload)
    prepay_id = resp.get("prepay_id", "")
    if not prepay_id:
        raise WxPayError(f"统一下单未返回 prepay_id：{resp}")
    return prepay_id


def build_prepay_params(prepay_id: str) -> Dict[str, str]:
    """小程序 wx.requestPayment 所需参数（每次调起重新签名）。"""
    _require_config()
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    package = f"prepay_id={prepay_id}"
    message = f"{settings.WXPAY_APPID}\n{timestamp}\n{nonce}\n{package}\n"
    return {
        "timeStamp": timestamp,
        "nonceStr": nonce,
        "package": package,
        "signType": "RSA",
        "paySign": _sign(message),
    }


# ---------- 退款 ----------

def refund(*, out_trade_no: str, out_refund_no: str,
           total_cents: int, refund_cents: int) -> Dict[str, Any]:
    """国内退款（全额）。out_refund_no 由调用方保证幂等。"""
    payload = {
        "out_trade_no": out_trade_no,
        "out_refund_no": out_refund_no,
        "amount": {"refund": refund_cents, "total": total_cents,
                   "currency": "CNY"},
    }
    return _api_request("POST", "/v3/refund/domestic/refunds", payload)


# ---------- 回调验签 / 解密 ----------

_platform_cert_cache: Optional[str] = None


def _get_platform_pubkey_pem() -> str:
    """微信支付平台证书公钥 PEM：优先用环境变量，否则从 /v3/certificates 拉取解密后缓存。"""
    global _platform_cert_cache
    env_pem = _pem_text(settings.WXPAY_PLATFORM_CERT)
    if env_pem:
        return env_pem
    if _platform_cert_cache:
        return _platform_cert_cache
    resp = _api_request("GET", "/v3/certificates")
    data = resp.get("data") or []
    if not data:
        raise WxPayError("拉取微信平台证书为空")
    enc = data[0]["encrypt_certificate"]
    plain = _aead_decrypt(
        ciphertext_b64=enc["ciphertext"], nonce=enc["nonce"],
        associated_data=enc.get("associated_data", ""),
    )
    _platform_cert_cache = plain.decode("utf-8")
    return _platform_cert_cache


def _load_platform_public_key(pem: str):
    if "CERTIFICATE" in pem:
        return x509.load_pem_x509_certificate(pem.encode()).public_key()
    if "PUBLIC KEY" in pem:
        return serialization.load_pem_public_key(pem.encode())
    raise WxPayError("平台公钥 PEM 格式不支持（需证书或公钥 PEM）")


def verify_notify_signature(*, signature: str, timestamp: str,
                            nonce: str, body: str) -> None:
    """验签微信回调。失败抛 WxPayError。"""
    _require_config()
    if not signature or not timestamp or not nonce:
        raise WxPayError("回调缺少签名头")
    try:
        ts = int(timestamp)
    except ValueError:
        raise WxPayError("回调时间戳非法")
    if abs(int(time.time()) - ts) > NOTIFY_TIME_SKEW:
        raise WxPayError("回调时间戳漂移过大，可能为重放")
    pub = _load_platform_public_key(_get_platform_pubkey_pem())
    message = f"{timestamp}\n{nonce}\n{body}\n"
    try:
        pub.verify(base64.b64decode(signature), message.encode("utf-8"),
                   padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, ValueError) as e:
        raise WxPayError(f"回调验签失败：{e}")


def _aead_decrypt(*, ciphertext_b64: str, nonce: str,
                  associated_data: str = "") -> bytes:
    key = settings.WXPAY_APIV3_KEY.encode("utf-8")
    if len(key) != 32:
        raise WxPayError("WXPAY_APIV3_KEY 长度必须为 32 字节")
    aesgcm = AESGCM(key)
    ct = base64.b64decode(ciphertext_b64)
    aad = associated_data.encode("utf-8") or None
    try:
        return aesgcm.decrypt(nonce.encode("utf-8"), ct, aad)
    except Exception as e:
        raise WxPayError(f"回调解密失败：{e}")


def parse_notify(headers: Dict[str, str], body: str) -> Dict[str, Any]:
    """验签 + 解密回调，返回交易明文（含 out_trade_no/transaction_id/trade_state）。"""
    # starlette 已把 header 名小写化，兼容两种写法
    def _h(name: str) -> str:
        return headers.get(name) or headers.get(name.lower()) or ""

    verify_notify_signature(
        signature=_h("Wechatpay-Signature"),
        timestamp=_h("Wechatpay-Timestamp"),
        nonce=_h("Wechatpay-Nonce"),
        body=body,
    )
    data = json.loads(body)
    if data.get("event_type") != "TRANSACTION.SUCCESS":
        raise WxPayError(f"非支付成功回调：{data.get('event_type')}")
    resource = data.get("resource") or {}
    plain = _aead_decrypt(
        ciphertext_b64=resource.get("ciphertext", ""),
        nonce=resource.get("nonce", ""),
        associated_data=resource.get("associated_data", ""),
    )
    return json.loads(plain.decode("utf-8"))


def wxpay_fingerprint() -> str:
    """配置指纹（日志用，不含密钥）：mchid 前后各 2 位。"""
    m = settings.WXPAY_MCHID or ""
    return f"mchid={m[:2]}***{m[-2:]}" if len(m) >= 4 else "mchid=未配置"
