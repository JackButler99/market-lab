"""WSGI adapter for the shared API routes; no HTTP server or worker starts on import."""

from email.message import Message
from http import HTTPStatus
import io
import json

import deploy_config
import server


class APIRequest(server.APIActions):
    def __init__(self, path, headers, body):
        self.path, self.headers, self.rfile = path, headers, io.BytesIO(body)
        self.status, self.payload = 500, {"error": "No response produced"}

    def send(self, code, data):
        self.status, self.payload = code, data


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    if query:
        path += "?" + query
    headers = Message()
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            headers[key[5:].replace("_", "-")] = value
    headers["Content-Length"] = environ.get("CONTENT_LENGTH", "0") or "0"
    headers["Content-Type"] = environ.get("CONTENT_TYPE", "")
    request = APIRequest(path, headers, b"")
    method = environ.get("REQUEST_METHOD", "GET").upper()
    try:
        if method != "OPTIONS" and not deploy_config.authorized(headers, path):
            request.send(401, {"error": "API authorization required"})
        elif method == "POST":
            size = int(headers["Content-Length"])
            if size < 1 or size > 2_000_000:
                request.send(413, {"error": "Request body must be between 1 byte and 2 MB"})
            else:
                body = environ["wsgi.input"].read(size)
                if len(body) != size:
                    request.send(400, {"error": "Incomplete request body"})
                else:
                    request.rfile = io.BytesIO(body)
                    request.do_POST()
        elif method == "GET":
            request.do_GET()
        elif method == "OPTIONS":
            request.do_OPTIONS()
        else:
            request.send(405, {"error": "Method not allowed"})
    except (ValueError, TypeError):
        request.send(400, {"error": "Invalid request"})
    except Exception:
        request.send(500, {"error": "Request failed; stored data retained"})
    body = json.dumps(request.payload, allow_nan=False).encode()
    response_headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
    ]
    response_headers.extend(deploy_config.cors(headers.get("Origin", "")).items())
    start_response(f"{request.status} {HTTPStatus(request.status).phrase}", response_headers)
    return [body]
