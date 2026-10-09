"""Operations CLI: `kitaab migrate`, `kitaab seed`, `kitaab create-admin`, ..."""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from alembic import command
from alembic.config import Config

from kitaab.config import get_settings

API_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    # Docker installs the package into site-packages, so prefer alembic.ini in
    # the working directory (/app) and fall back to the source checkout.
    ini = Path.cwd() / "alembic.ini"
    if not ini.exists():
        ini = API_ROOT / "alembic.ini"
    return Config(str(ini))


def cmd_migrate(args: argparse.Namespace) -> int:
    command.upgrade(alembic_config(), "head")
    print("Database migrated to head.")  # noqa: T201
    if args.init_storage:
        from kitaab.providers.storage import S3ObjectStore

        S3ObjectStore(get_settings()).ensure_bucket()
        print(f"Storage bucket '{get_settings().s3_bucket}' ready.")  # noqa: T201
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kitaab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser("migrate", help="Run database migrations (one-shot step)")
    migrate.add_argument(
        "--init-storage",
        action="store_true",
        help="Also create the storage bucket (development only)",
    )
    migrate.set_defaults(func=cmd_migrate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
