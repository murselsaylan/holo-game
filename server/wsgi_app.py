"""WSGI entry point (PythonAnywhere free plan, gunicorn, uwsgi ...).

    from server.wsgi_app import application

Environment: HOLO_DB = path of the sqlite file (default: holo_scores.db next to this project, on a persistent disk).
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.leaderboard_server import Store, dispatch, client_ip, MAX_BODY  # noqa: E402

_store = None


def _get_store():
    global _store
    if _store is None:
        _store = Store(os.environ.get("DATABASE_URL") or os.environ.get("HOLO_DB") or os.path.join(ROOT, "holo_scores.db"))
    return _store


_REASON = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 409: "Conflict", 413: "Payload Too Large",
           422: "Unprocessable Entity", 429: "Too Many Requests"}


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    body = b""
    if method == "POST":
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            n = 0
        body = environ["wsgi.input"].read(min(n, MAX_BODY + 1)) if n > 0 else b""
    ip = client_ip(environ.get("HTTP_X_FORWARDED_FOR"), environ.get("REMOTE_ADDR", "?"))
    code, obj = dispatch(_get_store(), method, environ.get("PATH_INFO", "/"), environ.get("QUERY_STRING", ""), body, ip)
    out = json.dumps(obj, ensure_ascii=False).encode()
    start_response(f"{code} {_REASON.get(code, 'OK')}", [("Content-Type", "application/json; charset=utf-8"),
                                                         ("Content-Length", str(len(out))),
                                                         ("Access-Control-Allow-Origin", "*")])
    return [out]
