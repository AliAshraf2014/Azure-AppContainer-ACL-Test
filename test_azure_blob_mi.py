#!/usr/bin/env python3
# Smoke-test managed-identity access to upload + download storage.

from __future__ import annotations

import sys

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# User-assigned managed identity (mapping agent)
MANAGED_IDENTITY_CLIENT_ID = "0ff70cda-3e59-494b-914a-146bfeceab9f"

# Upload (player) — look for a known mapping-agent output blob
UPLOAD_ACCOUNT_NAME = "s3stapplayeruks001"
UPLOAD_CONTAINER_NAME = "intellixcore-mappingagent"
UPLOAD_BLOB_PATH = (
    "TB/20260907092846/"
    "testClientA-2883119-Client 2 - Client 2 - TB from client_trial_balance.json"
)

# Download (EDP client data) — verify read access
DOWNLOAD_ACCOUNT_NAME = "s3stedpclientdata"
DOWNLOAD_CONTAINER_NAME = "clientdata"
DOWNLOAD_ACCOUNT_URL = "https://s3stedpclientdata.blob.core.windows.net"


def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(
        managed_identity_client_id=MANAGED_IDENTITY_CLIENT_ID,
    )


def _blob_service(account_name: str, account_url: str | None = None) -> BlobServiceClient:
    url = (account_url or f"https://{account_name}.blob.core.windows.net").rstrip("/")
    return BlobServiceClient(account_url=url, credential=_credential())


def check_upload_blob(
    account_name: str | None = None,
    container_name: str | None = None,
    blob_path: str | None = None,
) -> dict:
    """Look for the known file in the upload container."""
    account = (account_name or UPLOAD_ACCOUNT_NAME).strip()
    container = (container_name or UPLOAD_CONTAINER_NAME).strip()
    path = (blob_path or UPLOAD_BLOB_PATH).strip()

    print(f"\n=== Upload container check ===")
    print(f"Account:   {account}")
    print(f"Container: {container}")
    print(f"Blob:      {path}")

    client = _blob_service(account).get_blob_client(container=container, blob=path)
    try:
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
        print(f"FOUND size={props.size} contentType={props.content_settings.content_type}")
        print(f"lastModified={row['lastModified']}")
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
        print(f"ERROR: {exc}", file=sys.stderr)
        return row


def check_download_read_access(
    account_name: str | None = None,
    container_name: str | None = None,
    account_url: str | None = None,
) -> dict:
    """Verify the identity can read from the download container."""
    account = (account_name or DOWNLOAD_ACCOUNT_NAME).strip()
    container = (container_name or DOWNLOAD_CONTAINER_NAME).strip()
    url = (account_url or DOWNLOAD_ACCOUNT_URL).strip()

    print(f"\n=== Download container read-access check ===")
    print(f"Account:   {account}")
    print(f"Container: {container}")
    print(f"URL:       {url}")

    try:
        cc = _blob_service(account, url).get_container_client(container)
        # Container properties + a short list prove list/read permission.
        props = cc.get_container_properties()
        sample: list[str] = []
        for i, blob in enumerate(cc.list_blobs()):
            sample.append(blob.name)
            if i >= 4:
                break

        row = {
            "ok": True,
            "account": account,
            "container": container,
            "accountUrl": url,
            "canRead": True,
            "lastModified": props.last_modified.isoformat() if props.last_modified else None,
            "sampleBlobs": sample,
            "sampleCount": len(sample),
        }
        print(f"READ OK lastModified={row['lastModified']}")
        print(f"Sample blobs ({len(sample)}):")
        for name in sample:
            print(f"  - {name}")
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
        print(f"ERROR: {exc}", file=sys.stderr)
        return row


def run_smoke() -> list[dict]:
    """Run upload blob + download read checks; return result rows."""
    return [
        check_upload_blob(),
        check_download_read_access(),
    ]


def main() -> int:
    print(f"Managed identity client ID: {MANAGED_IDENTITY_CLIENT_ID}")
    print(f"Upload:   {UPLOAD_ACCOUNT_NAME}/{UPLOAD_CONTAINER_NAME}")
    print(f"Download: {DOWNLOAD_ACCOUNT_NAME}/{DOWNLOAD_CONTAINER_NAME}")

    results = run_smoke()
    errors = sum(1 for r in results if not r.get("ok"))
    print(f"\nDone. Checks: {len(results)}, errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
