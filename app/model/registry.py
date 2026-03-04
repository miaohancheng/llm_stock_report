from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
from pathlib import Path
import pickle
import subprocess
from typing import Any


@dataclass
class ModelBundle:
    model: Any
    feature_columns: list[str]
    model_version: str
    engine: str
    trained_at: str
    data_window_start: str
    data_window_end: str


def git_sha_short(project_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            text=True,
        ).strip()
        return out or "nogit"
    except Exception:
        return "nogit"


def build_model_version(market: str, asof_date: date, project_root: Path) -> str:
    return f"{market}_{asof_date.strftime('%Y%m%d')}_{git_sha_short(project_root)}"


def model_dir(models_root: Path, market: str, model_version: str) -> Path:
    return models_root / market / model_version


def save_model_bundle(models_root: Path, market: str, bundle: ModelBundle) -> Path:
    target = model_dir(models_root, market, bundle.model_version)
    target.mkdir(parents=True, exist_ok=True)

    with (target / "model.pkl").open("wb") as fh:
        pickle.dump(bundle.model, fh)

    metadata = asdict(bundle)
    metadata.pop("model", None)
    (target / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def _load_bundle_from_dir(path: Path) -> ModelBundle:
    metadata_path = path / "metadata.json"
    model_path = path / "model.pkl"
    if not metadata_path.exists() or not model_path.exists():
        raise FileNotFoundError(f"Incomplete model artifact under {path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    with model_path.open("rb") as fh:
        model = pickle.load(fh)

    return ModelBundle(
        model=model,
        feature_columns=list(metadata["feature_columns"]),
        model_version=str(metadata["model_version"]),
        engine=str(metadata.get("engine", "unknown")),
        trained_at=str(metadata["trained_at"]),
        data_window_start=str(metadata["data_window_start"]),
        data_window_end=str(metadata["data_window_end"]),
    )


def load_latest_model(models_root: Path, market: str) -> ModelBundle | None:
    market_root = models_root / market
    if not market_root.exists():
        return None

    candidates = [p for p in market_root.iterdir() if p.is_dir()]
    if not candidates:
        return None

    latest = sorted(candidates, key=lambda p: p.name, reverse=True)[0]
    return _load_bundle_from_dir(latest)


def model_is_expired(bundle: ModelBundle, asof_date: date, expire_days: int) -> bool:
    try:
        trained_day = datetime.strptime(bundle.trained_at[:10], "%Y-%m-%d").date()
    except Exception:
        return True
    return (asof_date - trained_day).days > expire_days
