"""Provision or rotate a local App user without enabling public registration."""

from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import getpass
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.db import AsyncSessionLocal
from app.services.auth_service import upsert_local_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--role",
        choices=("Admin", "Architect", "Analyst", "Viewer"),
        default="Admin",
    )
    parser.add_argument(
        "--grant-existing-projects",
        action="store_true",
        help="Grant membership to every existing project (appropriate for initial bootstrap).",
    )
    parser.add_argument(
        "--project-id",
        action="append",
        default=[],
        help="Grant membership to one project ID. Repeat for multiple projects.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from standard input instead of an interactive prompt.",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace, password: str) -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            user = await upsert_local_user(
                username=args.username,
                email=args.email,
                display_name=args.display_name,
                role=args.role,
                password=password,
                grant_existing_projects=args.grant_existing_projects,
                project_ids=args.project_id,
                db=db,
            )
        print(
            f"Local user ready: id={user.id} username={args.username.strip().casefold()} "
            f"role={user.role} existing_projects_granted={args.grant_existing_projects}"
            f" selected_projects_granted={len(args.project_id)}"
        )


def main() -> None:
    args = parse_args()
    password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass()
    if not password:
        raise SystemExit("Password must not be empty")
    asyncio.run(run(args, password))


if __name__ == "__main__":
    main()
