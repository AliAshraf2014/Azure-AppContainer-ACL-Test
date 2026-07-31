#!/usr/bin/env python3
# Recursively read ACL for every file on the read-only Data Lake (UPN form).
# Also resolve known Entra group IDs to user members via Microsoft Graph.

from __future__ import annotations

# import os
import sys

import requests
from azure.identity import DefaultAzureCredential
# from azure.storage.filedatalake import DataLakeServiceClient

# Read-only source (d3 EDP client data) - override via env if needed
# ACCOUNT_NAME = os.environ.get("AZURE_DATALAKE_ACCOUNT_NAME", "d3stedpclientdata")
# FILE_SYSTEM = os.environ.get("AZURE_DATALAKE_FILE_SYSTEM", "clientdata")
# Optional root prefix to walk from (empty = entire container)
# PATH = os.environ.get("AZURE_DATALAKE_PATH", "").strip()

# Group object IDs that appear in ACLs
GROUP_IDS = [
    "b88db9f9-e035-4572-9f64-1eb136a85a88",
    "df594b8f-eb27-4cdd-99a6-3c4a09bb13e5",
]

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


# def _service_client(account_name: str) -> DataLakeServiceClient:
#     return DataLakeServiceClient(
#         account_url=f"https://{account_name}.dfs.core.windows.net",
#         credential=DefaultAzureCredential(),
#     )


def _graph_headers() -> dict[str, str]:
    token = DefaultAzureCredential().get_token(GRAPH_SCOPE)
    return {"Authorization": f"Bearer {token.token}"}


def get_group_user_members(group_id: str) -> list[dict]:
    """Return user members of a group (users only; includes nested group users).

    Uses Graph transitiveMembers cast to microsoft.graph.user so nested
    security groups are expanded and non-user members are excluded.
    Requires GroupMember.Read.All or Directory.Read.All.
    """
    url = (
        f"{GRAPH_BASE}/groups/{group_id}/transitiveMembers/microsoft.graph.user"
        f"?$select=id,displayName,userPrincipalName,mail"
    )
    headers = _graph_headers()
    members: list[dict] = []

    while url:
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload.get("value", []):
            members.append(
                {
                    "id": item.get("id"),
                    "displayName": item.get("displayName"),
                    "userPrincipalName": item.get("userPrincipalName"),
                    "mail": item.get("mail"),
                }
            )
        url = payload.get("@odata.nextLink")

    return members


def resolve_group_members(group_ids: list[str] | None = None) -> dict[str, list[dict]]:
    """Fetch user-only members for each group ID."""
    ids = group_ids or GROUP_IDS
    by_group: dict[str, list[dict]] = {}

    for group_id in ids:
        print(f"\n=== Group {group_id} (users only) ===")
        try:
            members = get_group_user_members(group_id)
            by_group[group_id] = members
            print(f"User members: {len(members)}")
            for m in members:
                upn = m.get("userPrincipalName") or m.get("mail") or "(no UPN)"
                name = m.get("displayName") or "(no name)"
                print(f"  - {name} <{upn}>  [{m.get('id')}]")
        except Exception as exc:
            by_group[group_id] = []
            print(f"ERROR resolving group {group_id}: {exc}", file=sys.stderr)

    return by_group


# def read_all_acls(
#     account_name: str | None = None,
#     file_system: str | None = None,
#     root_path: str | None = None,
# ) -> list[dict]:
#     """Walk folders and return ACL (with UPN) for every file."""
#     account = (account_name or ACCOUNT_NAME).strip()
#     fs_name = (file_system or FILE_SYSTEM).strip()
#     root = (root_path if root_path is not None else PATH).strip().strip("/")
#
#     fs = _service_client(account).get_file_system_client(fs_name)
#     results: list[dict] = []
#
#     for entry in fs.get_paths(path=root or None, recursive=True):
#         if entry.is_directory:
#             continue
#
#         path_name = entry.name
#         try:
#             acl = fs.get_file_client(path_name).get_access_control(upn=True)
#             row = {
#                 "path": path_name,
#                 "owner": acl.get("owner"),
#                 "group": acl.get("group"),
#                 "permissions": acl.get("permissions"),
#                 "acl": acl.get("acl"),
#             }
#             results.append(row)
#             print(f"--- {path_name} ---")
#             print("Owner:", acl["owner"])
#             print("Group:", acl["group"])
#             print("Permissions:", acl["permissions"])
#             print("ACL:", acl["acl"])
#         except Exception as exc:
#             results.append({"path": path_name, "error": str(exc)})
#             print(f"--- {path_name} ---", file=sys.stderr)
#             print(f"ERROR: {exc}", file=sys.stderr)
#
#     print(f"\nFiles scanned: {len(results)}")
#     return results


def main() -> int:
    # print(f"Account: {ACCOUNT_NAME}")
    # print(f"File system: {FILE_SYSTEM}")
    # print(f"Root path: {PATH or '(container root)'}")
    # print("Filter: none (all files)")
    # print("ACL: get_access_control(upn=True)")

    # Resolve known ACL group IDs to user members via Graph
    print("Resolving ACL group members (users only) via Microsoft Graph...")
    group_members = resolve_group_members()
    for gid, members in group_members.items():
        print(f"Group {gid}: {len(members)} user(s)")

    # try:
    #     results = read_all_acls()
    # except Exception as exc:
    #     print(f"ERROR: {exc}", file=sys.stderr)
    #     return 1
    #
    # errors = sum(1 for r in results if "error" in r)
    # print(f"Done. Files: {len(results)}, errors: {errors}")
    # return 1 if errors else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
