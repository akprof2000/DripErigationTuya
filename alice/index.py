"""Навык «Умный дом» для Алисы: контроллер полива через облако Tuya.

Одна функция Яндекс Облака, вызывается двумя способами:
  * через API Gateway (api-gateway.yaml) — запросы Яндекса и привязка аккаунта (OAuth);
  * по таймеру раз в минуту — состояние отправляется в Яндекс (callback), на нём работают сценарии.

Переменные окружения (секреты задаёт владелец в консоли облака, в код и git не попадают):
  TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_DEVICE_ID, TUYA_ENDPOINT (по умолчанию Европа)
  ALICE_PASSWORD     — пароль на странице привязки аккаунта
  ALICE_SECRET       — ключ подписи токенов (любая длинная случайная строка)
  ALICE_CLIENT_ID, ALICE_CLIENT_SECRET — те же, что в настройках авторизации навыка
  YANDEX_SKILL_ID, YANDEX_OAUTH_TOKEN  — для уведомлений об изменении состояния (callback)
"""
import base64
import hashlib
import hmac
import html
import json
import os
import time
import urllib.parse
import urllib.request

import mapping
from tuya_api import Tuya, TuyaError

USER_ID = "owner"   # навык приватный, пользователь один
CODE_TTL = 600
ACCESS_TTL = 365 * 24 * 3600
REDIRECT_PREFIXES = ("https://social.yandex.net/", "https://social.yandex.ru/")

_tuya = None


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        raise RuntimeError("не задана переменная окружения " + name)
    return v


def tuya():
    global _tuya
    if _tuya is None:
        _tuya = Tuya(env("TUYA_ACCESS_ID"), env("TUYA_ACCESS_SECRET"),
                     env("TUYA_ENDPOINT", "https://openapi.tuyaeu.com"))
    return _tuya


# ---------------------------------------------------------------------- токены (без хранилища)
def _sig(text):
    return hmac.new(env("ALICE_SECRET").encode(), text.encode(), hashlib.sha256).hexdigest()


def make_token(kind, ttl):
    body = "%s.%d" % (kind, int(time.time()) + ttl)
    return base64.urlsafe_b64encode(body.encode()).decode().rstrip("=") + "." + _sig(body)


def check_token(token, kind):
    try:
        b64, sig = token.rsplit(".", 1)
        body = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode()
        k, until = body.split(".")
        return hmac.compare_digest(sig, _sig(body)) and k == kind and int(until) > time.time()
    except Exception:
        return False


# ---------------------------------------------------------------------- HTTP-ответы
def resp(status, body, ctype="application/json", headers=None):
    h = {"Content-Type": ctype + ("; charset=utf-8" if ctype.startswith("text/") else "")}
    h.update(headers or {})
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False)
    return {"statusCode": status, "headers": h, "body": body, "isBase64Encoded": False}


def _body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    return raw


def _header(event, name):
    for k, v in (event.get("headers") or {}).items():
        if k.lower() == name.lower():
            return v
    return ""


# ---------------------------------------------------------------------- OAuth для привязки
LOGIN_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Полив — вход</title>
<style>body{font-family:system-ui,sans-serif;max-width:360px;margin:15vh auto;padding:0 16px}
input,button{width:100%%;font-size:18px;padding:12px;margin-top:12px;box-sizing:border-box}
button{background:#1989fa;color:#fff;border:0;border-radius:8px}.e{color:#c00}</style></head>
<body><h2>Контроллер полива</h2><p>Введите пароль, чтобы подключить его к Алисе.</p>%s
<form method="post"><input type="password" name="password" placeholder="Пароль" autofocus>
%s<button>Подключить</button></form></body></html>"""


def oauth_authorize(event):
    q = dict(event.get("queryStringParameters") or {})
    if event.get("httpMethod") == "POST":
        q.update({k: v[0] for k, v in urllib.parse.parse_qs(_body(event)).items()})
    redirect = q.get("redirect_uri", "")
    if not redirect.startswith(REDIRECT_PREFIXES) or q.get("client_id") != env("ALICE_CLIENT_ID"):
        return resp(400, "неверный запрос привязки", "text/plain")
    hidden = "".join('<input type="hidden" name="%s" value="%s">' % (k, html.escape(q.get(k, "")))
                     for k in ("redirect_uri", "client_id", "state", "response_type", "scope"))
    if event.get("httpMethod") != "POST":
        return resp(200, LOGIN_PAGE % ("", hidden), "text/html")
    if not hmac.compare_digest(q.get("password", ""), env("ALICE_PASSWORD")):
        return resp(200, LOGIN_PAGE % ('<p class="e">Неверный пароль</p>', hidden), "text/html")
    params = {"code": make_token("code", CODE_TTL), "state": q.get("state", ""),
              "client_id": q.get("client_id", "")}
    sep = "&" if "?" in redirect else "?"
    return resp(302, "", "text/plain", {"Location": redirect + sep + urllib.parse.urlencode(params)})


def oauth_token(event):
    form = {k: v[0] for k, v in urllib.parse.parse_qs(_body(event)).items()}
    auth = _header(event, "Authorization")
    if auth.lower().startswith("basic "):
        cid, _, csec = base64.b64decode(auth[6:]).decode().partition(":")
        form.setdefault("client_id", cid)
        form.setdefault("client_secret", csec)
    if form.get("client_id") != env("ALICE_CLIENT_ID") or \
            not hmac.compare_digest(form.get("client_secret", ""), env("ALICE_CLIENT_SECRET")):
        return resp(401, {"error": "invalid_client"})
    grant = form.get("grant_type")
    ok = (grant == "authorization_code" and check_token(form.get("code", ""), "code")) or \
         (grant == "refresh_token" and check_token(form.get("refresh_token", ""), "refresh"))
    if not ok:
        return resp(400, {"error": "invalid_grant"})
    return resp(200, {"access_token": make_token("access", ACCESS_TTL), "token_type": "bearer",
                      "expires_in": ACCESS_TTL, "refresh_token": make_token("refresh", 10 * ACCESS_TTL)})


# ---------------------------------------------------------------------- протокол «Умного дома»
def smart_home(event, path):
    if not check_token(_header(event, "Authorization").replace("Bearer ", "").strip(), "access"):
        return resp(401, {"error": "unauthorized"})
    rid = _header(event, "X-Request-Id")
    dev_id = env("TUYA_DEVICE_ID")
    if path.endswith("/user/unlink"):
        return resp(200, {"request_id": rid})
    if path.endswith("/user/devices"):
        status = tuya().status(dev_id)
        return resp(200, {"request_id": rid, "payload": {"user_id": USER_ID, "devices": mapping.devices(status)}})
    if path.endswith("/user/devices/query"):
        req = json.loads(_body(event) or "{}")
        try:
            status = tuya().status(dev_id)
            online = True
        except TuyaError:
            status, online = {}, False
        out = []
        for d in req.get("devices", []):
            if not online:
                out.append({"id": d["id"], "error_code": "DEVICE_UNREACHABLE"})
                continue
            out.append(dict(id=d["id"], **mapping.state(d["id"], status)))
        return resp(200, {"request_id": rid, "payload": {"devices": out}})
    if path.endswith("/user/devices/action"):
        req = json.loads(_body(event) or "{}")
        out = []
        for d in req.get("payload", {}).get("devices", []):
            caps = []
            for cap in d.get("capabilities", []):
                result = {"status": "DONE"}
                try:
                    cmds = mapping.commands(d["id"], cap)
                    if cmds:
                        tuya().send(dev_id, cmds)
                except ValueError as e:
                    result = {"status": "ERROR", "error_code": "INVALID_ACTION", "error_message": str(e)}
                except TuyaError as e:
                    result = {"status": "ERROR", "error_code": "DEVICE_UNREACHABLE", "error_message": str(e)}
                caps.append({"type": cap["type"], "state": {"instance": cap["state"]["instance"],
                                                            "action_result": result}})
            out.append({"id": d["id"], "capabilities": caps})
        return resp(200, {"request_id": rid, "payload": {"devices": out}})
    return resp(404, {"error": "not found"})


# ---------------------------------------------------------------------- уведомление Яндекса по таймеру
def push_state():
    status = tuya().status(env("TUYA_DEVICE_ID"))
    devs = [dict(id=d["id"], **mapping.state(d["id"], status)) for d in mapping.devices(status)]
    body = json.dumps({"ts": time.time(), "payload": {"user_id": USER_ID, "devices": devs}}).encode()
    url = "https://dialogs.yandex.net/api/v1/skills/%s/callback/state" % env("YANDEX_SKILL_ID")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": "OAuth " + env("YANDEX_OAUTH_TOKEN"), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


# ---------------------------------------------------------------------- вход
def handler(event, context):
    if "messages" in event:   # таймер
        return {"pushed": push_state()}
    path = event.get("path") or event.get("url") or "/"
    path = path.split("?")[0].rstrip("/")
    method = event.get("httpMethod", "GET")
    if path.endswith("/oauth/authorize"):
        return oauth_authorize(event)
    if path.endswith("/oauth/token"):
        return oauth_token(event)
    if path.endswith("/v1.0") and method == "HEAD":
        return resp(200, "")
    if "/v1.0/" in path:
        return smart_home(event, path)
    return resp(404, {"error": "not found"})
