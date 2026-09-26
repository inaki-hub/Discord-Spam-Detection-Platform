from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import joblib

from app.ml.advisor import MlAdvisor
from app.ml.data import load_labeled_samples
from app.ml.train import (
    DEFAULT_MODEL_PATH,
    InsufficientDataError,
    metrics_as_json,
    train_models,
)
from app.storage.database import close_db, init_db


async def _train(args: argparse.Namespace) -> int:
    await init_db()
    try:
        samples = await load_labeled_samples(guild_id=args.guild_id)
        if not samples:
            print("No hay muestras etiquetadas (label != unknown).", file=sys.stderr)
            return 1
        out = Path(args.output) if args.output else DEFAULT_MODEL_PATH
        result = train_models(
            samples,
            min_samples=args.min_samples,
            model_path=out,
        )
        print(f"Modelo guardado en {result.model_path}")
        print(f"Muestras spam: {result.spam_samples}, automation: {result.automation_samples}")
        print(metrics_as_json(result.metrics))
        return 0
    except InsufficientDataError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        await close_db()


async def _status(args: argparse.Namespace) -> int:
    path = Path(args.model) if args.model else DEFAULT_MODEL_PATH
    if not path.is_file():
        print(f"No existe modelo en {path}")
        return 1
    bundle = joblib.load(path)
    print(f"Ruta: {path}")
    print(f"Versión bundle: {bundle.get('version')}")
    print(f"Entrenado: {bundle.get('trained_at')}")
    metrics = bundle.get("metrics") or {}
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    advisor = MlAdvisor(path)
    print(f"Advisor cargado: {advisor.enabled}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ML supervisado")
    sub = parser.add_subparsers(dest="command", required=True)

    train_p = sub.add_parser("train", help="Entrenar modelos spam/automation")
    train_p.add_argument(
        "--min-samples",
        type=int,
        default=20,
        help="Mínimo de filas etiquetadas por tarea",
    )
    train_p.add_argument("--guild-id", default=None)
    train_p.add_argument(
        "-o",
        "--output",
        default=None,
        help=f"Ruta del .joblib (default: {DEFAULT_MODEL_PATH})",
    )

    status_p = sub.add_parser("status", help="Estado del modelo en disco")
    status_p.add_argument(
        "--model",
        default=None,
        help=f"Ruta al .joblib (default: {DEFAULT_MODEL_PATH})",
    )

    args = parser.parse_args()
    if args.command == "train":
        raise SystemExit(asyncio.run(_train(args)))
    if args.command == "status":
        raise SystemExit(asyncio.run(_status(args)))


if __name__ == "__main__":
    main()
