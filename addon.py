"""Firebase Cloud Messaging (FCM HTTP v1) push integration."""

from __future__ import annotations

import json
import time
from typing import Any, ClassVar, Dict, List

import httpx
from fastapi import APIRouter
from jose import jwt
from pydantic import BaseModel, Field, SecretStr

from app.addons.notifications.base import NotificationAddon
from app.addons.notifications.helpers import post_json_webhook
from app.addons.log import info, warning
from app.addons.config_serialization import dump_addon_config


class FcmConfig(BaseModel):
    project_id: str = Field(default=..., description="Firebase / GCP project ID")
    service_account_json: SecretStr = Field(
        default=...,
        description="Service account JSON with Firebase Cloud Messaging scope",
    )
    web_api_key: str = Field(default=..., description="Firebase web API key (public)")
    web_app_id: str = Field(default=..., description="Firebase web app ID")
    web_messaging_sender_id: str = Field(
        default=...,
        description="Firebase Cloud Messaging sender ID",
    )
    web_vapid_key: str = Field(
        default=...,
        description="Web push certificate VAPID key (public)",
    )
    web_auth_domain: str = Field(
        default="",
        description="Optional Firebase auth domain for web app config",
    )

    @classmethod
    def config_model(cls):
        return cls


class FcmAddon(NotificationAddon):
    addon_id: str = "fcm"
    addon_name: str = "Firebase Cloud Messaging"
    addon_description: str = "Send push notifications via FCM HTTP v1."
    addon_category: str = "notification"
    version: str = "1.0.0"
    is_enabled: bool = False
    supported_channels: ClassVar[list[str]] = ["push"]

    _config: Dict[str, Any] | None = None
    _project_id: str | None = None
    _service_account: dict[str, Any] | None = None
    _access_token: str | None = None
    _token_expires_at: float = 0.0

    @classmethod
    def config_schema(cls):
        return FcmConfig

    async def initialize(self, config: dict) -> None:
        validated = self.config_schema()(**config)
        self._config = dump_addon_config(validated)
        self._project_id = validated.project_id
        raw_json = validated.service_account_json.get_secret_value()
        self._service_account = json.loads(raw_json)
        self._access_token = None
        self._token_expires_at = 0.0
        self.is_enabled = True
        info("FCM", "Initialized (project={})", self._project_id)

    async def validate_config(self, config: dict) -> None:
        import json
        import time

        from app.core.exceptions import ValidationError
        from jose import jwt

        validated = self.config_schema()(**config)
        raw_json = validated.service_account_json.get_secret_value()
        if not raw_json:
            return
        try:
            service_account = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValidationError(message="Service account JSON is invalid") from exc
        for field in ("client_email", "private_key"):
            if not service_account.get(field):
                raise ValidationError(
                    message=f"Service account JSON is missing required field: {field}"
                )
        now = int(time.time())
        claims = {
            "iss": service_account["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(claims, service_account["private_key"], algorithm="RS256")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
        if resp.status_code == 401:
            raise ValidationError(
                message="Invalid service account credentials — check your credentials"
            )
        if resp.status_code == 403:
            raise ValidationError(
                message="Service account is valid but missing required permissions: firebase.messaging"
            )
        if resp.status_code >= 400:
            raise ValidationError(message="Google rejected the service account credentials")

    async def shutdown(self) -> None:
        self._project_id = None
        self._service_account = None
        self._access_token = None
        self.is_enabled = False

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        if not self._service_account:
            raise RuntimeError("FCM service account not configured")

        now = int(time.time())
        claims = {
            "iss": self._service_account["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(
            claims,
            self._service_account["private_key"],
            algorithm="RS256",
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = now + int(data.get("expires_in", 3600))
            return self._access_token

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> Dict[str, Any]:
        return self.channel_not_supported("email", to)

    async def send_sms(self, to: str, body: str) -> Dict[str, Any]:
        return self.channel_not_supported("sms", to)

    async def send_push(
        self,
        to: str,
        title: str,
        body: str,
        data: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if not self._project_id or not self._service_account:
            return {"success": False, "message_id": "", "error": "Not configured", "to": to}

        message: dict[str, Any] = {
            "token": to,
            "notification": {"title": title, "body": body},
        }
        if data:
            message["data"] = {k: str(v) for k, v in data.items()}

        payload = {"message": message}
        url = f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"

        try:
            token = await self._get_access_token()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()
                return {
                    "success": True,
                    "message_id": result.get("name", ""),
                    "to": to,
                }
        except Exception as exc:
            warning("FCM", "send_push to={} error: {}", to, exc)
            return {"success": False, "message_id": "", "error": str(exc), "to": to}

    async def send_webhook(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = await post_json_webhook(url, payload)
        if not result.get("success"):
            warning("FCM", "send_webhook to={} error: {}", url, result.get("error"))
        return result

    def list_public_push_config(self) -> dict[str, Any] | None:
        if not self._config or not self._config.get("web_api_key"):
            return None
        config: dict[str, Any] = {
            "apiKey": self._config.get("web_api_key"),
            "projectId": self._project_id or self._config.get("project_id"),
            "messagingSenderId": self._config.get("web_messaging_sender_id"),
            "appId": self._config.get("web_app_id"),
            "vapidKey": self._config.get("web_vapid_key"),
        }
        auth_domain = self._config.get("web_auth_domain")
        if auth_domain:
            config["authDomain"] = auth_domain
        return {"provider": self.addon_id, "config": config}

    def get_routers(self) -> List[APIRouter]:
        return []

    def get_admin_routes(self) -> List[APIRouter]:
        from app.addons.notifications.fcm.routes import admin_router

        return [admin_router]

    def get_admin_templates(self) -> str:
        from pathlib import Path

        return str(Path(__file__).resolve().parent / "templates")

    def get_admin_static(self) -> str:
        from pathlib import Path

        return str(Path(__file__).resolve().parent / "static")
