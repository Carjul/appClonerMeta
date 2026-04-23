import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from app.config import PYTHON_BIN


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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


def bulk_clone_command(campaign_id: str, token: str) -> Tuple[List[str], Dict[str, str]]:
    cmd = [
        PYTHON_BIN,
        "meta_bulk_clone_fixed.py",
        "--campaign-id",
        campaign_id,
        "--access-token",
        token,
    ]
    return cmd, {}


def single_clone_command(campaign_ids: List[str], token: str) -> Tuple[List[str], Dict[str, str]]:
    cmd = [PYTHON_BIN, "Meta_clone_fixed.py", "--access-token", token, "--campaign-ids", *campaign_ids]
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
