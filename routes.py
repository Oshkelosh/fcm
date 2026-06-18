"""FCM addon routes."""

from __future__ import annotations

from typing import Any

from app.addons.notifications.shared_routes import build_notification_routers


def _parse_fcm_config_form(form: Any) -> tuple[dict[str, Any], bool]:
    return (
        {
            "project_id": form.get("project_id", ""),
            "service_account_json": form.get("service_account_json", ""),
            "web_api_key": form.get("web_api_key", ""),
            "web_app_id": form.get("web_app_id", ""),
            "web_messaging_sender_id": form.get("web_messaging_sender_id", ""),
            "web_vapid_key": form.get("web_vapid_key", ""),
            "web_auth_domain": form.get("web_auth_domain", ""),
        },
        form.get("is_enabled") == "on",
    )


admin_router, jinja_env = build_notification_routers(
    "fcm",
    template_name="fcm_config.html",
    page_title="FCM Settings",
    secret_keys=("service_account_json",),
    parse_config_form=_parse_fcm_config_form,
)
