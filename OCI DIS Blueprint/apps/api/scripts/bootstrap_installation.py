"""Bootstrap the first local Admin and optional deployment API token once."""

from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import IO

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.api_token_scopes import ALL_API_TOKEN_SCOPES
from app.core.db import AsyncSessionLocal
from app.services.installation_service import (
    InstallationAlreadyInitializedError,
    bootstrap_installation_admin,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    password = parser.add_mutually_exclusive_group(required=True)
    password.add_argument(
        "--password-file",
        type=Path,
        help="Read the initial password from a mounted secret file.",
    )
    password.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate a high-entropy password and write it only to --output-file.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Exclusive mode-0600 JSON destination for generated one-time credentials.",
    )
    parser.add_argument(
        "--grant-existing-projects",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--create-api-token",
        action="store_true",
        help="Create one expiring read-only token for deployment automation.",
    )
    parser.add_argument(
        "--api-token-scope",
        action="append",
        default=[],
        choices=sorted(ALL_API_TOKEN_SCOPES),
        help="Repeat for granular token capabilities; defaults to projects:read.",
    )
    parser.add_argument("--api-token-days", type=int, default=30, choices=range(1, 366))
    return parser.parse_args()


def read_password(path: Path) -> str:
    """Read one bounded regular secret file without echoing its contents."""

    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("password file must be a regular file")
    if metadata.st_size > 4096:
        raise ValueError("password file exceeds 4096 bytes")
    value = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not value:
        raise ValueError("password file must not be empty")
    return value


def reserve_secret_output(path: Path) -> IO[str]:
    """Reserve a non-following, exclusive mode-0600 credential artifact."""

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    return os.fdopen(descriptor, "w", encoding="utf-8")


async def run(args: argparse.Namespace, password: str) -> dict[str, object]:
    scopes = args.api_token_scope or ["projects:read"]
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await bootstrap_installation_admin(
                username=args.username,
                email=args.email,
                display_name=args.display_name,
                password=password,
                grant_existing_projects=args.grant_existing_projects,
                create_initial_api_token=args.create_api_token,
                api_token_scopes=scopes,
                api_token_days=args.api_token_days,
                db=db,
            )
    return {
        "created": result.created,
        "user_id": result.user_id,
        "username": result.username,
        "password": password if result.created and args.generate_password else None,
        "api_token": result.api_token,
        "api_token_id": result.api_token_id,
        "api_token_scopes": scopes if result.api_token else [],
    }


def main() -> None:
    args = parse_args()
    if (args.generate_password or args.create_api_token) and args.output_file is None:
        raise SystemExit("--output-file is required for every generated password or API token")

    output: IO[str] | None = None
    if args.output_file is not None:
        try:
            output = reserve_secret_output(args.output_file)
        except FileExistsError as exc:
            raise SystemExit(f"credential output already exists: {args.output_file}") from exc

    try:
        password = (
            secrets.token_urlsafe(32)
            if args.generate_password
            else read_password(args.password_file)
        )
        payload = asyncio.run(run(args, password))
        if output is not None:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
            output.close()
        if payload["created"]:
            print(
                "Installation identity ready; one-time credentials were written to "
                f"{args.output_file}" if args.output_file else "Installation identity ready"
            )
        else:
            if args.output_file is not None:
                args.output_file.unlink(missing_ok=True)
            print("Installation identity already exists; bootstrap made no changes")
    except (InstallationAlreadyInitializedError, ValueError) as exc:
        if output is not None and not output.closed:
            output.close()
        if args.output_file is not None:
            args.output_file.unlink(missing_ok=True)
        raise SystemExit(str(exc)) from exc
    except BaseException:
        if output is not None and not output.closed:
            output.close()
        if args.output_file is not None:
            args.output_file.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
