import requests


def notify_fb_catalog(config: dict | None, text: str) -> dict:
    if not config:
        return {"telegram": False, "slack": False}

    result = {"telegram": False, "slack": False, "errors": []}
    bot_token = (config.get("telegram_bot_token") or "").strip()
    chat_id = (config.get("telegram_chat_id") or "").strip()
    if bot_token and chat_id:
        try:
            res = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:3900]},
                timeout=20,
            )
            res.raise_for_status()
            result["telegram"] = True
        except Exception as exc:
            result["errors"].append(f"telegram: {exc}")

    slack_webhook = (config.get("slack_webhook_url") or "").strip()
    if slack_webhook:
        try:
            res = requests.post(slack_webhook, json={"text": text[:3900]}, timeout=20)
            res.raise_for_status()
            result["slack"] = True
        except Exception as exc:
            result["errors"].append(f"slack: {exc}")

    return result
