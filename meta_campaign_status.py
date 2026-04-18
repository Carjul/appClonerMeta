#!/usr/bin/env python3
"""META ADS CAMPAIGN STATUS MANAGER
Activa o desactiva campañas de Meta Ads.
Recibe múltiples IDs de campañas, token y estatus (ACTIVE o PAUSED).
"""

import argparse
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==================== LOGGING ====================
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"campaign_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Crear logger con handlers específicos
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# FileHandler con UTF-8
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# StreamHandler con UTF-8 para console
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

# Formato
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# ==================== CONFIG ====================
parser = argparse.ArgumentParser(
    description="META ADS CAMPAIGN STATUS MANAGER - Activa o desactiva campañas"
)
parser.add_argument(
    "--campaign-ids",
    nargs="+",
    required=True,
    help="IDs de las campañas a modificar (una o varias)"
)
parser.add_argument(
    "--access-token",
    required=True,
    help="Access token de Meta Ads"
)
parser.add_argument(
    "--status",
    required=True,
    choices=["ACTIVE", "PAUSED"],
    help="Estatus a establecer: ACTIVE o PAUSED"
)
parser.add_argument(
    "--api-version",
    default="v21.0",
    help="Versión de la API de Meta (default: v21.0)"
)

args = parser.parse_args()

ACCESS_TOKEN = args.access_token
CAMPAIGN_IDS = args.campaign_ids
STATUS = args.status
API_VERSION = args.api_version
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Configuración de reintentos
TRANSIENT_SLEEP = 2.0
TRANSIENT_RETRIES = 3
SLEEP_BETWEEN = 0.5

# ==================== UTILIDADES ====================
def get_campaign_info(campaign_id: str) -> dict:
    """
    Obtiene información básica de una campaña.
    """
    fields = "id,name,status,account_id"
    url = f"{BASE_URL}/{campaign_id}"
    params = {"fields": fields, "access_token": ACCESS_TOKEN}

    try:
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
    except requests.RequestException as e:
        logger.error(f"Error de conexión obteniendo campaña {campaign_id}: {e}")
        return None

    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        logger.error(
            f"Error API obteniendo {campaign_id} [{err.get('code')}]: "
            f"{err.get('message')} | fbtrace: {err.get('fbtrace_id')}"
        )
        return None

    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "current_status": data.get("status"),
        "account_id": data.get("account_id")
    }


def update_campaign_status(campaign_id: str, new_status: str) -> bool:
    """
    Actualiza el estatus de una campaña con reintentos.
    """
    url = f"{BASE_URL}/{campaign_id}"
    params = {
        "status": new_status,
        "access_token": ACCESS_TOKEN
    }

    for attempt in range(TRANSIENT_RETRIES + 1):
        try:
            logger.info(f"  Intento {attempt + 1}/{TRANSIENT_RETRIES + 1}: Actualizando {campaign_id} a {new_status}...")
            r = requests.post(url, params=params, timeout=30)
            data = r.json()

            if isinstance(data, dict) and data.get("error"):
                err = data["error"]
                error_code = err.get("code")
                error_msg = err.get("message")
                fbtrace = err.get("fbtrace_id")

                # Algunos errores son transitorios
                if error_code in [17, 2, 1, 4]:  # Rate limit, temporary error, etc.
                    if attempt < TRANSIENT_RETRIES:
                        logger.warning(
                            f"  Error transitorio [{error_code}]: {error_msg}. "
                            f"Esperando {TRANSIENT_SLEEP}s antes de reintentar..."
                        )
                        time.sleep(TRANSIENT_SLEEP)
                        continue
                
                logger.error(
                    f"  [FAIL] Error actualizando {campaign_id} [{error_code}]: "
                    f"{error_msg} | fbtrace: {fbtrace}"
                )
                return False

            # Éxito
            success = data.get("success", False)
            if success or data.get("id"):
                logger.info(f"  [OK] Campaña {campaign_id} actualizada a {new_status}")
                return True
            else:
                logger.warning(f"  [?] Respuesta inesperada para {campaign_id}: {data}")
                return False

        except requests.RequestException as e:
            if attempt < TRANSIENT_RETRIES:
                logger.warning(
                    f"  Error de conexión: {e}. "
                    f"Esperando {TRANSIENT_SLEEP}s antes de reintentar..."
                )
                time.sleep(TRANSIENT_SLEEP)
                continue
            else:
                logger.error(f"  [FAIL] Error de conexión en {campaign_id} (intentos agotados): {e}")
                return False

    return False


# ==================== MAIN ====================
def main():
    logger.info("=" * 70)
    logger.info("META ADS CAMPAIGN STATUS MANAGER")
    logger.info("=" * 70)
    
    if not CAMPAIGN_IDS:
        logger.error("[!] No se proporcionaron IDs de campañas.")
        sys.exit(1)

    logger.info(f"Parámetros:")
    logger.info(f"  - Campañas a procesar: {len(CAMPAIGN_IDS)}")
    logger.info(f"  - Nuevo estatus: {STATUS}")
    logger.info(f"  - API version: {API_VERSION}")
    logger.info("")

    # Verificar y obtener info de las campañas
    logger.info("Validando campañas...")
    campaigns_info = {}
    valid_campaigns = []

    for campaign_id in CAMPAIGN_IDS:
        info = get_campaign_info(campaign_id)
        if info:
            campaigns_info[campaign_id] = info
            valid_campaigns.append(campaign_id)
            msg = f"  [OK] {campaign_id}: '{info['name']}' (actual: {info['current_status']})"
            logger.info(msg)
        else:
            logger.warning(f"  [FAIL] No se pudo validar {campaign_id}")
        time.sleep(SLEEP_BETWEEN)

    logger.info(f"\nCampañas válidas: {len(valid_campaigns)}/{len(CAMPAIGN_IDS)}")

    if not valid_campaigns:
        logger.error("No hay campañas válidas para procesar.")
        sys.exit(1)

    # Confirmación
    logger.info("")
    logger.info(f"Resumen:")
    logger.info(f"  - Campañas a actualizar: {len(valid_campaigns)}")
    logger.info(f"  - Estatus destino: {STATUS}")
    logger.info("")

    # Procesar campañas
    logger.info("Actualizando campañas...")
    results = {
        "success": [],
        "failed": []
    }

    for i, campaign_id in enumerate(valid_campaigns, 1):
        logger.info(f"\n[{i}/{len(valid_campaigns)}] Procesando campaña {campaign_id}...")
        
        # Saltar si ya tiene el estatus
        current_status = campaigns_info[campaign_id]["current_status"]
        if current_status.upper() == STATUS.upper():
            logger.info(f"  [INFO] Campaña ya tiene estatus {STATUS}. Omitiendo.")
            results["success"].append(campaign_id)
            continue

        # Actualizar
        if update_campaign_status(campaign_id, STATUS):
            results["success"].append(campaign_id)
        else:
            results["failed"].append(campaign_id)

        time.sleep(SLEEP_BETWEEN)

    # Resumen final
    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 70)
    logger.info(f"Exitosas: {len(results['success'])}")
    if results["success"]:
        for cid in results["success"]:
            logger.info(f"  [OK] {cid}")

    logger.info(f"\nFallidas: {len(results['failed'])}")
    if results["failed"]:
        for cid in results["failed"]:
            logger.info(f"  [FAIL] {cid}")

    logger.info("")
    logger.info(f"Total procesadas: {len(valid_campaigns)}")
    logger.info(f"Tasa de éxito: {len(results['success'])/len(valid_campaigns)*100:.1f}%")
    logger.info(f"\nLog guardado en: {log_filename}")
    logger.info("=" * 70)

    return 0 if not results["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
