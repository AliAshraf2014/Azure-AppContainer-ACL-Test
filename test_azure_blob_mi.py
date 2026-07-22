#!/usr/bin/env python3
"""
Read ACL for a path on the read-only Azure Data Lake (Gen2) container.
"""

from __future__ import annotations

import os
import sys

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient

# Read-only source (d3 EDP client data) — override via env if needed
ACCOUNT_NAME = os.environ.get("AZURE_DATALAKE_ACCOUNT_NAME", "d3stedpclientdata")
FILE_SYSTEM = os.environ.get("AZURE_DATALAKE_FILE_SYSTEM", "clientdata")
PATH = os.environ.get("AZURE_DATALAKE_PATH", "folder1/file.pdf")


def read_acl(
    account_name: str | None = None,
    file_system: str | None = None,
    path: str | None = None,
) -> dict:
    account = (account_name or ACCOUNT_NAME).strip()
    fs_name = (file_system or FILE_SYSTEM).strip()
    blob_path = (path or PATH).strip()

    service = DataLakeServiceClient(
        account_url=f"https://{account}.dfs.core.windows.net",
        credential=DefaultAzureCredential(),
    )
    fs = service.get_file_system_client(fs_name)
    file_client = fs.get_file_client(blob_path)
    return file_client.get_access_control()


def main() -> int:
    print(f"Account: {ACCOUNT_NAME}")
    print(f"File system: {FILE_SYSTEM}")
    print(f"Path: {PATH}")
    try:
        acl = read_acl()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Owner:", acl["owner"])
    print("Group:", acl["group"])
    print("Permissions:", acl["permissions"])
    print("ACL:", acl["acl"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
