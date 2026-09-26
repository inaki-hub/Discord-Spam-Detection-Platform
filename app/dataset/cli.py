from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.config import DATA_DIR
from app.dataset.storage import (
    apply_dataset_label,
    backfill_dataset_samples,
    export_dataset_jsonl,
)
from app.storage.database import close_db, init_db


async def _export(args: argparse.Namespace) -> int:
    await init_db()
    try:
        out = Path(args.output)
        if not out.is_absolute():
            out = DATA_DIR / out
        count = await export_dataset_jsonl(out, guild_id=args.guild_id)
        print(f"Exportadas {count} muestras -> {out}")
        return 0
    finally:
        await close_db()


async def _backfill(args: argparse.Namespace) -> int:
    await init_db()
    try:
        created, skipped = await backfill_dataset_samples(
            guild_id=args.guild_id,
            user_id=args.user_id,
            limit=args.limit,
        )
        print(f"Backfill: {created} creadas, {skipped} omitidas")
        return 0
    finally:
        await close_db()


def _validate_message_id(message_id: str) -> str | None:
    """Devuelve texto de error o None si el ID parece un snowflake de Discord."""
    mid = message_id.strip()
    if mid.upper() == "MESSAGE_ID":
        return (
            "Sustituye MESSAGE_ID por el ID numérico del mensaje "
            "(modo desarrollador → clic derecho → Copiar ID del mensaje)."
        )
    if not mid.isdigit():
        return "El message_id debe ser solo dígitos (ID de Discord)."
    if len(mid) < 17:
        return f"El ID {mid!r} es demasiado corto; un message_id de Discord suele tener 17–20 dígitos."
    return None


async def _label(args: argparse.Namespace) -> int:
    err = _validate_message_id(args.message_id)
    if err:
        print(err, file=sys.stderr)
        return 1
    await init_db()
    try:
        mid = args.message_id.strip()
        ok = await apply_dataset_label(mid, args.label)
        if not ok:
            print(
                f"No hay mensaje {mid} en SQLite (tabla messages). "
                "¿El bot procesó ese mensaje en este servidor?",
                file=sys.stderr,
            )
            return 1
        print(f"message_id={mid} label={args.label}")
        return 0
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(description="Herramientas del dataset")
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="Exportar muestras a JSONL")
    export_p.add_argument(
        "-o",
        "--output",
        default="dataset_export.jsonl",
        help="Archivo de salida (relativo a data/ si no es absoluto)",
    )
    export_p.add_argument("--guild-id", default=None, help="Filtrar por servidor")

    backfill_p = sub.add_parser(
        "backfill",
        help="Crear dataset_samples para mensajes ya guardados sin fila dataset",
    )
    backfill_p.add_argument("--guild-id", default=None)
    backfill_p.add_argument("--user-id", default=None)
    backfill_p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de mensajes a revisar (más recientes primero)",
    )

    label_p = sub.add_parser("label", help="Etiquetar una muestra tras revisión humana")
    label_p.add_argument("message_id", help="ID del mensaje de Discord")
    label_p.add_argument(
        "label",
        help="normal | spam | automated_spam | legitimate_bot | unknown",
    )

    args = parser.parse_args()
    if args.command == "export":
        raise SystemExit(asyncio.run(_export(args)))
    if args.command == "backfill":
        raise SystemExit(asyncio.run(_backfill(args)))
    if args.command == "label":
        raise SystemExit(asyncio.run(_label(args)))


if __name__ == "__main__":
    main()
