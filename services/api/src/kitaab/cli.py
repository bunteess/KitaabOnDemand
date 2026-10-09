"""Operations CLI.

kitaab migrate [--init-storage]        run migrations (one-shot deploy step)
kitaab seed [--demo]                   cities, placeholder pricing, settings (--demo: logins)
kitaab create-admin EMAIL NAME         new admin; prints a temporary password and TOTP setup
kitaab create-vendor-user VENDOR EMAIL NAME
kitaab purge [--dry-run]               run the storage purge now
"""

import argparse
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from kitaab.config import get_settings

if TYPE_CHECKING:
    from kitaab.domain.auth import NewStaff
    from kitaab.domain.context import Ctx

API_ROOT = Path(__file__).resolve().parents[2]

# Placeholder zones: replace with real courier zones before launch (OWNER_TODO.md).
CITIES: list[tuple[str, str, str]] = [
    ("Karachi", "Sindh", "Z1"),
    ("Lahore", "Punjab", "Z1"),
    ("Islamabad", "Islamabad Capital Territory", "Z1"),
    ("Rawalpindi", "Punjab", "Z1"),
    ("Faisalabad", "Punjab", "Z2"),
    ("Multan", "Punjab", "Z2"),
    ("Peshawar", "Khyber Pakhtunkhwa", "Z2"),
    ("Hyderabad", "Sindh", "Z2"),
    ("Gujranwala", "Punjab", "Z2"),
    ("Sialkot", "Punjab", "Z2"),
    ("Sargodha", "Punjab", "Z2"),
    ("Bahawalpur", "Punjab", "Z2"),
    ("Sukkur", "Sindh", "Z2"),
    ("Abbottabad", "Khyber Pakhtunkhwa", "Z2"),
    ("Mardan", "Khyber Pakhtunkhwa", "Z2"),
    ("Quetta", "Balochistan", "Z3"),
    ("Dera Ismail Khan", "Khyber Pakhtunkhwa", "Z3"),
    ("Muzaffarabad", "Azad Jammu and Kashmir", "Z3"),
    ("Gilgit", "Gilgit-Baltistan", "Z3"),
    ("Gwadar", "Balochistan", "Z3"),
]

DEMO_ADMIN = ("admin@example.com", "Demo Admin", "demo-admin-password", "JBSWY3DPEHPK3PXP")
DEMO_VENDOR = ("vendor@example.com", "Demo Vendor Staff", "demo-vendor-password")


def out(text: str) -> None:
    print(text)  # noqa: T201 (CLI output)


def alembic_config() -> Config:
    # Docker installs the package into site-packages, so prefer alembic.ini in
    # the working directory (/app) and fall back to the source checkout.
    ini = Path.cwd() / "alembic.ini"
    if not ini.exists():
        ini = API_ROOT / "alembic.ini"
    return Config(str(ini))


def cmd_migrate(args: argparse.Namespace) -> int:
    command.upgrade(alembic_config(), "head")
    out("Database migrated to head.")
    if args.init_storage:
        from kitaab.providers.storage import S3ObjectStore

        S3ObjectStore(get_settings()).ensure_bucket()
        out(f"Storage bucket '{get_settings().s3_bucket}' ready.")
    return 0


def _ctx() -> "Ctx":
    from kitaab.container import build_services
    from kitaab.domain.context import Ctx

    services = build_services(get_settings())
    return Ctx(services.session(), services)


def seed_base(ctx: "Ctx") -> list[str]:
    from kitaab.domain import app_settings, pricing_store
    from kitaab.domain.pricing import PLACEHOLDER_RULES
    from kitaab.models import City, PricingConfig
    from kitaab.schemas.admin import AppSettings

    notes = []
    existing = set(ctx.session.scalars(select(City.name)))
    for order, (name, province, zone) in enumerate(CITIES):
        if name not in existing:
            ctx.session.add(City(name=name, province=province, zone_code=zone, sort_order=order))
    notes.append(f"cities: {len(CITIES) - len(existing & {c[0] for c in CITIES})} added")
    if ctx.session.scalar(select(PricingConfig.id).limit(1)) is None:
        pricing_store.create(
            ctx,
            PLACEHOLDER_RULES,
            datetime(2026, 1, 1, tzinfo=UTC),
            "Placeholder prices: replace before launch",
        )
        notes.append("pricing: placeholder version 1 created")
    if app_settings.load(ctx) == AppSettings():
        app_settings.save(
            ctx,
            AppSettings(
                support_phone="+920000000000",
                support_whatsapp="+920000000000",
                support_email="support@example.com",
                support_hours="Mon to Sat, 10 am to 6 pm",
            ),
        )
        notes.append("settings: placeholder support contact saved")
    return notes


def cmd_seed(args: argparse.Namespace) -> int:
    from kitaab.domain import auth
    from kitaab.domain.enums import Role
    from kitaab.models import User, Vendor

    ctx = _ctx()
    with ctx.session:
        for note in seed_base(ctx):
            out(note)
        if args.demo:
            if ctx.services.settings.is_production:
                out("Refusing to create demo logins in production.")
                return 1
            email, name, password, secret = DEMO_ADMIN
            if ctx.session.scalar(select(User.id).where(User.email == email)) is None:
                auth.create_staff(
                    ctx,
                    email=email,
                    full_name=name,
                    role=Role.ADMIN,
                    password=password,
                    totp_secret=secret,
                )
            vendor = ctx.session.scalar(select(Vendor).where(Vendor.name == "Demo Print House"))
            if vendor is None:
                vendor = Vendor(
                    name="Demo Print House",
                    contact_name="Demo Vendor",
                    contact_phone_e164="+923211234567",
                    is_active=True,
                )
                ctx.session.add(vendor)
                ctx.session.flush()
            v_email, v_name, v_password = DEMO_VENDOR
            if ctx.session.scalar(select(User.id).where(User.email == v_email)) is None:
                auth.create_staff(
                    ctx,
                    email=v_email,
                    full_name=v_name,
                    role=Role.VENDOR,
                    vendor_id=vendor.id,
                    password=v_password,
                )
            out("Demo logins (development only):")
            out(f"  admin   {email} / {password}  TOTP secret {secret}")
            out(f"  vendor  {v_email} / {v_password}")
            out("  customer: any 03XX number; the code is in GET /api/v1/_dev/sms-outbox")
        ctx.session.commit()
    return 0


def _print_new_staff(new: "NewStaff") -> None:
    out(f"Created {new.user.role.value.lower()} {new.user.email}")
    out(f"Temporary password: {new.temporary_password}")
    if new.totp_uri:
        out(f"TOTP secret: {new.totp_secret}")
        out(f"Authenticator link: {new.totp_uri}")
    out("Share these over a secure channel. They are not shown again.")


def cmd_create_admin(args: argparse.Namespace) -> int:
    from kitaab.domain import auth
    from kitaab.domain.enums import Role

    ctx = _ctx()
    with ctx.session:
        new = auth.create_staff(ctx, email=args.email, full_name=args.name, role=Role.ADMIN)
        ctx.session.commit()
        _print_new_staff(new)
    return 0


def cmd_create_vendor_user(args: argparse.Namespace) -> int:
    from kitaab.domain import auth
    from kitaab.domain.enums import Role
    from kitaab.models import Vendor

    ctx = _ctx()
    with ctx.session:
        vendor = ctx.session.get(Vendor, uuid.UUID(args.vendor_id))
        if vendor is None:
            out("No vendor with that id.")
            return 1
        new = auth.create_staff(
            ctx, email=args.email, full_name=args.name, role=Role.VENDOR, vendor_id=vendor.id
        )
        ctx.session.commit()
        _print_new_staff(new)
    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    from kitaab import jobs
    from kitaab.container import build_services

    report = jobs.purge_files(build_services(get_settings()), dry_run=args.dry_run or None)
    out(", ".join(f"{k}={v}" for k, v in report.items()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kitaab", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser("migrate", help="Run database migrations (one-shot step)")
    migrate.add_argument(
        "--init-storage",
        action="store_true",
        help="Also create the storage bucket (development only)",
    )
    migrate.set_defaults(func=cmd_migrate)

    seed = sub.add_parser("seed", help="Seed cities, placeholder pricing and settings")
    seed.add_argument(
        "--demo", action="store_true", help="Also create demo admin and vendor logins"
    )
    seed.set_defaults(func=cmd_seed)

    admin = sub.add_parser("create-admin", help="Create an admin login")
    admin.add_argument("email")
    admin.add_argument("name")
    admin.set_defaults(func=cmd_create_admin)

    vendor = sub.add_parser("create-vendor-user", help="Create a login for a vendor")
    vendor.add_argument("vendor_id")
    vendor.add_argument("email")
    vendor.add_argument("name")
    vendor.set_defaults(func=cmd_create_vendor_user)

    purge = sub.add_parser("purge", help="Run the storage purge now")
    purge.add_argument("--dry-run", action="store_true")
    purge.set_defaults(func=cmd_purge)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
