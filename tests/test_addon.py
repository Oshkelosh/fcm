"""Minimal unit tests for the fcm addon."""

from app.addons.notifications.fcm.addon import FcmAddon


def test_addon_identity():
    assert FcmAddon.addon_id == "fcm"
    assert FcmAddon.addon_category == "notification"
