#!/usr/bin/env python3
"""HTTP entrypoint for Azure Container Apps (health + ACL smoke)."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


def _listen_host() -> str:
    # LISTEN_HOST only — do not use HOSTNAME (Kubernetes/ACA sets it for the pod).
    host = os.environ.get("LISTEN_HOST", "0.0.0.0").strip()
    return host if host else "0.0.0.0"


def _listen_port() -> int:
    return int(os.environ.get("PORT", "8080"))


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = json.dumps({"status": "ok", "service": "datalake-acl-test"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/smoke":
            self.send_response(404)
            self.end_headers()
            return

        from test_azure_blob_mi import (
            DOWNLOAD_ACCOUNT_NAME,
            DOWNLOAD_CONTAINER_NAME,
            MANAGED_IDENTITY_CLIENT_ID,
            UPLOAD_ACCOUNT_NAME,
            UPLOAD_BLOB_PATH,
            UPLOAD_CONTAINER_NAME,
            run_smoke,
        )

        try:
            results = run_smoke()
            errors = sum(1 for r in results if not r.get("ok"))
            payload = {
                "exitCode": 1 if errors else 0,
                "managedIdentityClientId": MANAGED_IDENTITY_CLIENT_ID,
                "uploadAccountName": UPLOAD_ACCOUNT_NAME,
                "uploadContainerName": UPLOAD_CONTAINER_NAME,
                "uploadBlobPath": UPLOAD_BLOB_PATH,
                "downloadAccountName": DOWNLOAD_ACCOUNT_NAME,
                "downloadContainerName": DOWNLOAD_CONTAINER_NAME,
                "checkCount": len(results),
                "errorCount": errors,
                "checks": results,
            }
            status = 200 if not errors else 500
        except Exception as exc:
            payload = {
                "exitCode": 1,
                "managedIdentityClientId": MANAGED_IDENTITY_CLIENT_ID,
                "uploadAccountName": UPLOAD_ACCOUNT_NAME,
                "uploadContainerName": UPLOAD_CONTAINER_NAME,
                "downloadAccountName": DOWNLOAD_ACCOUNT_NAME,
                "downloadContainerName": DOWNLOAD_CONTAINER_NAME,
                "error": str(exc),
            }
            status = 500

        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = _listen_host()
    port = _listen_port()
    print(f"Listening on http://{host}:{port}/ (GET /health, POST /smoke)")
    HTTPServer((host, port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
