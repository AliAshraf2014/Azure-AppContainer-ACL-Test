#!/usr/bin/env python3
# Smoke-test managed-identity access to upload + download storage.

from __future__ import annotations

import argparse
import sys

from azure.core.exceptions import HttpResponseError, ServiceRequestError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient

# User-assigned managed identity (mapping agent)
MANAGED_IDENTITY_CLIENT_ID = "ec09a650-91b9-4af5-8868-7098384ac2ac"

# Upload (player) — look for a known mapping-agent output blob (d3 / develop)
UPLOAD_ACCOUNT_NAME = "d3stapplayeruks001"
UPLOAD_CONTAINER_NAME = "intellixcore-mappingagent"
UPLOAD_BLOB_PATH = (
    "TB/20260907092846/"
    "testClientA-2883119-Client 2 - Client 2 - TB from client_trial_balance.json"
)

# Download (EDP client data) — verify read access (d3 / develop)
DOWNLOAD_ACCOUNT_NAME = "d3stedpclientdata"
DOWNLOAD_CONTAINER_NAME = "clientdata"
DOWNLOAD_ACCOUNT_URL = "https://d3stedpclientdata.blob.core.windows.net"

# Fail fast instead of hanging on private-endpoint / ACL list stalls
CONNECTION_TIMEOUT = 15
READ_TIMEOUT = 30


def _log(msg: str) -> None:
    print(msg, flush=True)


def _credential() -> ManagedIdentityCredential:
    # Direct UAMI — avoids DefaultAzureCredential chain stalls.
    return ManagedIdentityCredential(client_id=MANAGED_IDENTITY_CLIENT_ID)


def _blob_service(account_name: str, account_url: str | None = None) -> BlobServiceClient:
    url = (account_url or f"https://{account_name}.blob.core.windows.net").rstrip("/")
    return BlobServiceClient(
        account_url=url,
        credential=_credential(),
        connection_timeout=CONNECTION_TIMEOUT,
        read_timeout=READ_TIMEOUT,
    )


def check_upload_blob(
    account_name: str | None = None,
    container_name: str | None = None,
    blob_path: str | None = None,
) -> dict:
    """Look for the known file in the upload container."""
    account = (account_name or UPLOAD_ACCOUNT_NAME).strip()
    container = (container_name or UPLOAD_CONTAINER_NAME).strip()
    path = (blob_path or UPLOAD_BLOB_PATH).strip()

    _log("\n=== Upload container check ===")
    _log(f"Account:   {account}")
    _log(f"Container: {container}")
    _log(f"Blob:      {path}")

    client = _blob_service(account).get_blob_client(container=container, blob=path)
    try:
        _log("Getting blob properties...")
        props = client.get_blob_properties()
        row = {
            "ok": True,
            "account": account,
            "container": container,
            "blobPath": path,
            "exists": True,
            "size": props.size,
            "contentType": props.content_settings.content_type,
            "lastModified": props.last_modified.isoformat() if props.last_modified else None,
        }
        _log(f"FOUND size={props.size} contentType={props.content_settings.content_type}")
        _log(f"lastModified={row['lastModified']}")
        return row
    except Exception as exc:
        row = {
            "ok": False,
            "account": account,
            "container": container,
            "blobPath": path,
            "exists": False,
            "error": str(exc),
        }
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return row


def check_download_read_access(
    account_name: str | None = None,
    container_name: str | None = None,
    account_url: str | None = None,
) -> dict:
    """Verify the identity can read from the download container.

    Uses a single lightweight list page (1 item). Full container walks hang
    on large / ACL-restricted Data Lake containers.
    """
    account = (account_name or DOWNLOAD_ACCOUNT_NAME).strip()
    container = (container_name or DOWNLOAD_CONTAINER_NAME).strip()
    url = (account_url or DOWNLOAD_ACCOUNT_URL).strip()

    _log("\n=== Download container read-access check ===")
    _log(f"Account:   {account}")
    _log(f"Container: {container}")
    _log(f"URL:       {url}")
    _log(f"Timeouts:  connect={CONNECTION_TIMEOUT}s read={READ_TIMEOUT}s")

    try:
        _log("Creating blob service client...")
        cc = _blob_service(account, url).get_container_client(container)

        # Lightest read probe: one page of list, max 1 blob.
        # Avoid get_container_properties + full iteration (often hangs on HNS/ACL).
        _log("Listing up to 1 blob (read probe)...")
        pager = cc.list_blobs(results_per_page=1).by_page()
        first_page = next(pager)
        sample = [b.name for b in first_page]

        row = {
            "ok": True,
            "account": account,
            "container": container,
            "accountUrl": url,
            "canRead": True,
            "sampleBlobs": sample,
            "sampleCount": len(sample),
        }
        _log("READ OK")
        if sample:
            _log(f"Sample blob: {sample[0]}")
        else:
            _log("Container is readable but empty (or no blobs visible at root).")
        return row
    except StopIteration:
        # Empty container still means list permission worked.
        row = {
            "ok": True,
            "account": account,
            "container": container,
            "accountUrl": url,
            "canRead": True,
            "sampleBlobs": [],
            "sampleCount": 0,
        }
        _log("READ OK (empty listing)")
        return row
    except (ServiceRequestError, TimeoutError, OSError) as exc:
        row = {
            "ok": False,
            "account": account,
            "container": container,
            "accountUrl": url,
            "canRead": False,
            "error": f"timeout/network: {exc}",
        }
        print(
            f"ERROR (likely firewall/private endpoint or hung list): {exc}",
            file=sys.stderr,
            flush=True,
        )
        return row
    except HttpResponseError as exc:
        row = {
            "ok": False,
            "account": account,
            "container": container,
            "accountUrl": url,
            "canRead": False,
            "error": str(exc),
            "statusCode": getattr(exc, "status_code", None),
        }
        print(f"ERROR (HTTP {row['statusCode']}): {exc}", file=sys.stderr, flush=True)
        return row
    except Exception as exc:
        row = {
            "ok": False,
            "account": account,
            "container": container,
            "accountUrl": url,
            "canRead": False,
            "error": str(exc),
        }
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return row


def run_smoke(*, upload: bool = True, download: bool = True) -> list[dict]:
    """Run selected upload / download checks; return result rows."""
    results: list[dict] = []
    if upload:
        results.append(check_upload_blob())
    if download:
        results.append(check_download_read_access())
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test managed-identity access to upload / download storage.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help=f"Check blob exists in {UPLOAD_ACCOUNT_NAME}/{UPLOAD_CONTAINER_NAME}",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help=f"Check read access on {DOWNLOAD_ACCOUNT_NAME}/{DOWNLOAD_CONTAINER_NAME}",
    )
    args = parser.parse_args(argv)

    if not args.upload and not args.download:
        parser.error("specify --upload and/or --download")

    _log(f"Managed identity client ID: {MANAGED_IDENTITY_CLIENT_ID}")
    if args.upload:
        _log(f"Upload:   {UPLOAD_ACCOUNT_NAME}/{UPLOAD_CONTAINER_NAME}")
    if args.download:
        _log(f"Download: {DOWNLOAD_ACCOUNT_NAME}/{DOWNLOAD_CONTAINER_NAME}")

    results = run_smoke(upload=args.upload, download=args.download)
    errors = sum(1 for r in results if not r.get("ok"))
    _log(f"\nDone. Checks: {len(results)}, errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
