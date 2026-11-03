"""Idempotent seed for TapOrder (tables 1 & 3, 3 categories, 12 menu items, 2 staff users)."""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_session_factory
from app.models import DiningTable, MenuCategory, MenuItem, StaffUser
from app.security import (
    decrypt_qr_token,
    encrypt_qr_token,
    generate_opaque_token,
    hash_password,
    sha256_bytes,
)

# Deterministic UUIDv5 namespace for natural-key idempotent seed entities
SEED_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _seed_uuid(kind: str, natural_key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"taporder:{kind}:{natural_key}")


SEED_TABLES: list[tuple[int, str]] = [
    (1, "Bàn 1"),
    (3, "Bàn 3"),
]

SEED_CATEGORIES: list[tuple[str, int, str]] = [
    ("Cà phê", 1, "coffee"),
    ("Trà trái cây", 2, "tea"),
    ("Đá xay & Bánh", 3, "other"),
]

SEED_MENU_ITEMS: list[tuple[str, str, str, int, int]] = [
    # (category_name, item_name, description, price_vnd, sort_order)
    ("Cà phê", "Cà phê sữa", "Cà phê phin truyền thống pha cùng sữa đặc thơm béo.", 30000, 1),
    ("Cà phê", "Cà phê đen đá", "Cà phê nguyên chất đậm vị, phục vụ kèm đá viên.", 25000, 2),
    ("Cà phê", "Bạc xỉu", "Sữa tươi hòa quyện cốt cà phê nhẹ dịu, dễ uống.", 32000, 3),
    ("Cà phê", "Cà phê muối", "Cà phê đậm đà phủ lớp kem muối mặn ngọt đặc trưng.", 38000, 4),
    ("Trà trái cây", "Trà đào", "Trà đen ủ lạnh kết hợp miếng đào giòn ngọt.", 35000, 1),
    ("Trà trái cây", "Trà vải hoa hồng", "Trà thanh mát cùng trái vải ngâm và hương hoa hồng.", 38000, 2),
    ("Trà trái cây", "Trà ổi hồng", "Trà ổi hồng chua ngọt tự nhiên giải nhiệt.", 36000, 3),
    ("Trà trái cây", "Trà sen vàng", "Trà ô long hạt sen và lớp kem macchiato mịn.", 42000, 4),
    ("Đá xay & Bánh", "Matcha đá xay", "Bột trà xanh Nhật Bản xay nhuyễn cùng sữa tươi.", 45000, 1),
    ("Đá xay & Bánh", "Cacao nóng", "Cacao nguyên chất pha sữa nóng ấm áp.", 35000, 2),
    ("Đá xay & Bánh", "Bánh sừng bò bơ", "Croissant ngàn lớp nướng bơ Pháp giòn xốp.", 28000, 3),
    ("Đá xay & Bánh", "Bánh tiramisu", "Bánh mềm mịn vị cà phê và phô mai mascarpone.", 40000, 4),
]

SEED_STAFF: list[tuple[str, str]] = [
    ("barista.demo", "barista"),
    ("cashier.demo", "cashier"),
]


def run_seed(
    db: Session,
    *,
    barista_password: str | None = None,
    cashier_password: str | None = None,
    export_accounts_txt: bool = False,
) -> dict[int, str]:
    """Idempotently seed tables 1 & 3, categories, 12 items, and staff users.

    Never creates fake shifts, bills, orders, or payments.
    Never rotates existing table QR tokens or staff passwords on rerun.
    Returns mapping of {table_number: raw_qr_token} for local test/demo usage.
    """
    settings = get_settings()
    b_pwd = (
        barista_password
        or settings.demo_barista_password
        or "BaristaDemo#2026"
    )
    c_pwd = (
        cashier_password
        or settings.demo_cashier_password
        or "CashierDemo#2026"
    )

    table_tokens: dict[int, str] = {}
    for number, label in SEED_TABLES:
        existing_table = db.execute(
            select(DiningTable).where(DiningTable.number == number)
        ).scalar_one_or_none()
        if existing_table is None:
            raw_token = generate_opaque_token()
            thash = sha256_bytes(raw_token)
            encrypted = encrypt_qr_token(raw_token, settings.qr_encryption_key)
            existing_table = DiningTable(
                id=_seed_uuid("table", str(number)),
                number=number,
                label=label,
                qr_token_hash=thash,
                qr_token_encrypted=encrypted,
                enabled=True,
            )
            db.add(existing_table)
            table_tokens[number] = raw_token
        else:
            existing_table.label = label
            existing_table.enabled = True
            table_tokens[number] = decrypt_qr_token(
                existing_table.qr_token_encrypted,
                settings.qr_encryption_key,
                settings.qr_encryption_backup_keys,
            )

    db.flush()

    cat_by_name: dict[str, MenuCategory] = {}
    for cat_name, sort_order, bucket in SEED_CATEGORIES:
        existing_cat = db.execute(
            select(MenuCategory).where(MenuCategory.name == cat_name)
        ).scalar_one_or_none()
        if existing_cat is None:
            existing_cat = MenuCategory(
                id=_seed_uuid("category", cat_name),
                name=cat_name,
                sort_order=sort_order,
                recommendation_bucket=bucket,
            )
            db.add(existing_cat)
        else:
            existing_cat.sort_order = sort_order
            existing_cat.recommendation_bucket = bucket
        cat_by_name[cat_name] = existing_cat

    db.flush()

    for cat_name, item_name, desc, price_vnd, sort_order in SEED_MENU_ITEMS:
        cat = cat_by_name[cat_name]
        existing_item = db.execute(
            select(MenuItem).where(
                MenuItem.category_id == cat.id,
                MenuItem.name == item_name,
            )
        ).scalar_one_or_none()
        if existing_item is None:
            db.add(
                MenuItem(
                    id=_seed_uuid("menu_item", f"{cat_name}:{item_name}"),
                    category_id=cat.id,
                    name=item_name,
                    description=desc,
                    price_vnd=price_vnd,
                    available=True,
                    active=True,
                    sort_order=sort_order,
                    version=1,
                )
            )
        else:
            # Preserve current available/version across idempotent reruns
            existing_item.description = desc
            existing_item.price_vnd = price_vnd
            existing_item.sort_order = sort_order
            existing_item.active = True

    for username, role in SEED_STAFF:
        existing_user = db.execute(
            select(StaffUser).where(StaffUser.username == username)
        ).scalar_one_or_none()
        if existing_user is None:
            pwd = b_pwd if role == "barista" else c_pwd
            db.add(
                StaffUser(
                    id=_seed_uuid("staff", username),
                    username=username,
                    password_hash=hash_password(pwd),
                    role=role,
                    active=True,
                )
            )
        else:
            existing_user.role = role
            existing_user.active = True

    db.commit()

    if export_accounts_txt:
        out_path = Path(settings.demo_export_accounts_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        base_url = settings.public_base_url
        content = (
            f"TAPORDER LOCAL DEMO ACCOUNTS & QR (IGNORED - DO NOT COMMIT)\n"
            f"Generated At: {now_iso}\n"
            f"Base URL: {base_url}\n\n"
            f"[Barista]\n"
            f"Username: barista.demo\n"
            f"Password: {b_pwd}\n"
            f"Login URL: {base_url}/staff/login\n"
            f"Kitchen URL: {base_url}/staff/kitchen\n\n"
            f"[Cashier]\n"
            f"Username: cashier.demo\n"
            f"Password: {c_pwd}\n"
            f"Login URL: {base_url}/staff/login\n"
            f"Cashier URL: {base_url}/staff/cashier\n\n"
            f"[Guest Table Capabilities]\n"
            f"Bàn 1 QR URL: {base_url}/t/{table_tokens[1]}\n"
            f"Bàn 3 QR URL: {base_url}/t/{table_tokens[3]}\n"
        )
        out_path.write_text(content, encoding="utf-8")

    return table_tokens


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotent TapOrder database seed")
    parser.add_argument(
        "--export-demo-txt",
        action="store_true",
        help="Export local ignored demo accounts & QR file (.local-tools/demo/accounts.txt)",
    )
    args = parser.parse_args()
    factory = get_session_factory()
    with factory() as session:
        run_seed(session, export_accounts_txt=args.export_demo_txt)
    print("Seed completed idempotently (tables 1 & 3, 3 categories, 12 items, 2 staff users).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

