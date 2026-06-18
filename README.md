# Firebase Cloud Messaging (`fcm`)

Send push notifications via the FCM HTTP v1 API.

## Overview

| | |
|---|---|
| Addon ID | `fcm` |
| Category | notification |
| Channels | push |
| Version | 1.0.0 |
| Category guide | [../README.md](../README.md) |

Only **one** notification provider per channel can be active at a time.

## Enable and configure

1. Install this package under `app/addons/notifications/fcm/`
2. Open **Admin → Notifications → FCM** at `/admin/notifications/fcm`
3. Enter Firebase project ID and service account JSON
4. Enable the provider checkbox and save

## Configuration schema

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | string | Firebase / Google Cloud project ID |
| `service_account_json` | secret | Full service account key JSON with Firebase Messaging access |

Secrets are stored in `addon_configs`, not in `.env`.

## Routes

### Admin

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/notifications/fcm` | Config form |
| POST | `/admin/notifications/fcm/save` | Save config |

### Public API

None — core calls `send_push()` with a device registration token as `to`.

## Provider setup

1. In the [Firebase Console](https://console.firebase.google.com/), create or select a project.
2. Enable **Cloud Messaging** and note the **Project ID**.
3. Under **Project settings → Service accounts**, generate a new private key (JSON).
4. Grant the service account **Firebase Cloud Messaging API Admin** (or use the default Firebase Admin SDK service account).
5. Paste the project ID and entire JSON key into admin config.
6. Store FCM registration tokens from your mobile/web app; pass them as the `to` argument.

Uses OAuth2 service-account JWT exchange, then `POST https://fcm.googleapis.com/v1/projects/{project_id}/messages:send`.

Email and SMS are not supported.

## Package layout

```
fcm/
├── README.md
├── addon.py
├── routes.py
└── templates/
    └── fcm_config.html
```

## See also

- [Notification addon development](../README.md)
- [Oshkelosh addon guide](../../README.md)
