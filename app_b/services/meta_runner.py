import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from app_b.config import PYTHON_BIN


# app_b/services/ → app_b/ → app/  (raíz del proyecto)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTIFACTS_DIR = os.path.join(ROOT_DIR, "logs", "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def _artifact_path(prefix: str, suffix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return os.path.join(ARTIFACTS_DIR, f"{prefix}_{ts}{suffix}")


def explorer_command(bm_id: str, token: str) -> Tuple[List[str], Dict[str, str]]:
    output_path = _artifact_path("explorer", ".json")
    cmd = [
        PYTHON_BIN,
        "fb_daily_report.py",
        "--access-token",
        token,
        "--bm-id",
        bm_id,
        "--output-json",
        output_path,
    ]
    return cmd, {"output_json": output_path}


def bulk_clone_command(
    campaign_id: str,
    token: str,
    copies: int = 4,
    start_copy: int = 2,
    adsets_per_campaign: int = 50,
    ads_per_adset: int = 1,
    max_workers: int = 5,
) -> Tuple[List[str], Dict[str, str]]:
    cmd = [
        PYTHON_BIN,
        "meta_bulk_clone_fixed.py",
        "--campaign-id",
        campaign_id,
        "--access-token",
        token,
        "--copies",
        str(copies),
        "--start-copy",
        str(start_copy),
        "--adsets-per-campaign",
        str(adsets_per_campaign),
        "--ads-per-adset",
        str(ads_per_adset),
        "--max-workers",
        str(max_workers),
    ]
    return cmd, {}


def single_clone_command(
    campaign_ids: List[str],
    token: str,
    copies_to_create: int = 49,
    ads_per_adset: int = 1,
) -> Tuple[List[str], Dict[str, str]]:
    cmd = [
        PYTHON_BIN,
        "Meta_clone_fixed.py",
        "--access-token",
        token,
        "--copies-to-create",
        str(copies_to_create),
        "--ads-per-adset",
        str(ads_per_adset),
        "--campaign-ids",
        *campaign_ids,
    ]
    return cmd, {}


def delete_campaigns_command(campaign_ids: List[str], token: str, batch: int = 10) -> Tuple[List[str], Dict[str, str]]:
    cmd = [
        PYTHON_BIN,
        "meta_ads_delete.py",
        "--campaign-ids",
        *campaign_ids,
        "--access-token",
        token,
        "--batch",
        str(batch),
    ]
    return cmd, {}


def campaign_status_command(campaign_ids: List[str], token: str, status: str, api_version: str = "v21.0") -> Tuple[List[str], Dict[str, str]]:
    cmd = [
        PYTHON_BIN,
        "meta_campaign_status.py",
        "--campaign-ids",
        *campaign_ids,
        "--access-token",
        token,
        "--status",
        status,
        "--api-version",
        api_version,
    ]
    return cmd, {}


def reduce_budgets_command(
    token: str,
    campaign_ids: List[str],
    execute: bool = False,
    min_spend: float = 5.0,
    target_budget: float = 1.0,
) -> Tuple[List[str], Dict[str, str]]:
    cmd = [
        PYTHON_BIN,
        "reduce_budgets.py",
        "--access-token",
        token,
        "--campaign-ids",
        *campaign_ids,
        "--min-spend",
        str(min_spend),
        "--target-budget",
        str(target_budget),
    ]
    if execute:
        cmd.append("--execute")
    return cmd, {}
