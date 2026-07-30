#!/usr/bin/env python3
# Recursively read ACL for every file on the read-only Data Lake (UPN form).

from __future__ import annotations

import os
import sys

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient

# Read-only source (d3 EDP client data) - override via env if needed
ACCOUNT_NAME = os.environ.get("AZURE_DATALAKE_ACCOUNT_NAME", "d3stedpclientdata")
FILE_SYSTEM = os.environ.get("AZURE_DATALAKE_FILE_SYSTEM", "clientdata")
# Optional root prefix to walk from (empty = entire container)
PATH = os.environ.get("AZURE_DATALAKE_PATH", "").strip()


def _service_client(account_name: str) -> DataLakeServiceClient:
    return DataLakeServiceClient(
        account_url=f"https://{account_name}.dfs.core.windows.net",
        credential=DefaultAzureCredential(),
    )


def read_all_acls(
    account_name: str | None = None,
    file_system: str | None = None,
    root_path: str | None = None,
) -> list[dict]:
    """Walk folders and return ACL (with UPN) for every file."""
    account = (account_name or ACCOUNT_NAME).strip()
    fs_name = (file_system or FILE_SYSTEM).strip()
    root = (root_path if root_path is not None else PATH).strip().strip("/")

    fs = _service_client(account).get_file_system_client(fs_name)
    results: list[dict] = []

    for entry in fs.get_paths(path=root or None, recursive=True):
        if entry.is_directory:
            continue

        path_name = entry.name
        try:
            acl = fs.get_file_client(path_name).get_access_control(upn=True)
            row = {
                "path": path_name,
                "owner": acl.get("owner"),
                "group": acl.get("group"),
                "permissions": acl.get("permissions"),
                "acl": acl.get("acl"),
            }
            results.append(row)
            print(f"--- {path_name} ---")
            print("Owner:", acl["owner"])
            print("Group:", acl["group"])
            print("Permissions:", acl["permissions"])
            print("ACL:", acl["acl"])
        except Exception as exc:
            results.append({"path": path_name, "error": str(exc)})
            print(f"--- {path_name} ---", file=sys.stderr)
            print(f"ERROR: {exc}", file=sys.stderr)

    print(f"\nFiles scanned: {len(results)}")
    return results


def main() -> int:
    print(f"Account: {ACCOUNT_NAME}")
    print(f"File system: {FILE_SYSTEM}")
    print(f"Root path: {PATH or '(container root)'}")
    print("Filter: none (all files)")
    print("ACL: get_access_control(upn=True)")
    try:
        results = read_all_acls()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = sum(1 for r in results if "error" in r)
    print(f"Done. Files: {len(results)}, errors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
