"""
Thin HTTP client wrapping all backend API calls.
Raises no exceptions — always returns a dict with a 'success' key.
"""
import os
import pathlib
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
_TIMEOUT = 15  # seconds

# TLS verification:
#   - If SSL_CERTFILE env var points to our self-signed cert, trust it explicitly.
#   - If REQUESTS_CA_BUNDLE is set (system trust store), that takes precedence.
#   - Falls back to True (strict verification) for production HTTPS.
#   - Set REQUESTS_VERIFY=false ONLY for quick local testing (not recommended).
def _tls_verify():
    if os.getenv("REQUESTS_VERIFY", "").lower() == "false":
        return False  # developer override — suppresses SSL warnings
    cert = os.getenv("SSL_CERTFILE", "")
    if cert and pathlib.Path(cert).exists():
        return cert   # pin our own self-signed cert
    return True       # default: standard CA verification


def _post(path: str, json: dict = None, token: str = None) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=json, headers=headers,
                          timeout=_TIMEOUT, verify=_tls_verify())
        if r.status_code < 400:
            return r.json()
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        return {"success": False, "message": str(detail)}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Cannot reach the backend server. Is it running?"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _get(path: str, params: dict = None, token: str = None) -> dict | list:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=params, headers=headers,
                         timeout=_TIMEOUT, verify=_tls_verify())
        if r.status_code < 400:
            return r.json()
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        return {"success": False, "message": str(detail)}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Cannot reach the backend server. Is it running?"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _put(path: str, json: dict, token: str = None) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.put(f"{BACKEND_URL}{path}", json=json, headers=headers,
                         timeout=_TIMEOUT, verify=_tls_verify())
        if r.status_code < 400:
            return r.json()
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        return {"success": False, "message": str(detail)}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Cannot reach the backend server. Is it running?"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _get_bytes(path: str, token: str = None) -> bytes | None:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"{BACKEND_URL}{path}", headers=headers,
                         timeout=_TIMEOUT, verify=_tls_verify())
        if r.status_code < 400:
            return r.content
        return None
    except Exception:
        return None


# ─── Auth ─────────────────────────────────────────────────────────────────────

def register(name: str, apartment_number: str, phone_number: str) -> dict:
    return _post("/auth/register", {"name": name, "apartment_number": apartment_number, "phone_number": phone_number})


def verify_registration_otp(phone_number: str, otp: str) -> dict:
    return _post("/auth/register/verify-otp", {"phone_number": phone_number, "otp": otp, "purpose": "registration"})


def resend_otp(phone_number: str, purpose: str = "registration") -> dict:
    return _post("/auth/resend-otp", {"phone_number": phone_number, "purpose": purpose})


def login(password: str, phone_number: str = None, apartment_number: str = None, name: str = None) -> dict:
    payload = {"password": password}
    if phone_number:
        payload["phone_number"] = phone_number
    if apartment_number:
        payload["apartment_number"] = apartment_number
    if name:
        payload["name"] = name
    return _post("/auth/login", payload)


# ─── Voting ───────────────────────────────────────────────────────────────────

def get_active_topics(token: str) -> list:
    result = _get("/vote/topics", token=token)
    return result if isinstance(result, list) else []


def get_topic(topic_id: int, token: str) -> dict:
    return _get(f"/vote/topics/{topic_id}", token=token)


def initiate_vote(topic_id: int, option_id: int, token: str) -> dict:
    return _post("/vote/initiate", {"topic_id": topic_id, "option_id": option_id}, token=token)


def cast_vote(topic_id: int, option_id: int, otp: str, token: str) -> dict:
    return _post("/vote/cast", {"topic_id": topic_id, "option_id": option_id, "otp": otp}, token=token)


def get_vote_results(topic_id: int, token: str) -> dict:
    return _get(f"/vote/topics/{topic_id}/results", token=token)


def get_my_vote(topic_id: int, token: str) -> dict:
    """Return the current voter's own selection for a topic."""
    return _get(f"/vote/topics/{topic_id}/my-vote", token=token)


# ─── Admin ────────────────────────────────────────────────────────────────────

def admin_dashboard(token: str) -> dict:
    return _get("/admin/dashboard", token=token)


def admin_pending_users(token: str) -> list:
    result = _get("/admin/users/pending", token=token)
    return result if isinstance(result, list) else []


def admin_all_users(token: str, status_filter: str = None) -> list:
    params = {}
    if status_filter:
        params["status_filter"] = status_filter
    result = _get("/admin/users", params=params, token=token)
    return result if isinstance(result, list) else []


def admin_approve_user(user_id: int, token: str) -> dict:
    return _post("/admin/users/approve", {"user_id": user_id}, token=token)


def admin_reject_user(user_id: int, reason: str, token: str) -> dict:
    return _post("/admin/users/reject", {"user_id": user_id, "reason": reason}, token=token)


def admin_toggle_user(user_id: int, active: bool, token: str) -> dict:
    return _post("/admin/users/toggle", {"user_id": user_id, "active": active}, token=token)


def admin_list_apartments(token: str) -> list:
    result = _get("/admin/apartments", token=token)
    return result if isinstance(result, list) else []


def admin_create_apartment(apartment_number: str, max_voters: int, token: str) -> dict:
    return _post("/admin/apartments", {"apartment_number": apartment_number, "max_allowed_voters": max_voters}, token=token)


def admin_update_apartment(apt_id: int, max_voters: int, is_active: bool, token: str) -> dict:
    return _put(f"/admin/apartments/{apt_id}", {"max_allowed_voters": max_voters, "is_active": is_active}, token=token)


def admin_list_topics(token: str) -> list:
    result = _get("/admin/topics", token=token)
    return result if isinstance(result, list) else []


def admin_create_topic(title: str, description: str, mode: str, options: list,
                       start_time=None, end_time=None, observer_ids: list = None,
                       token: str = None) -> dict:
    payload = {
        "title": title,
        "description": description,
        "mode": mode,
        "options": [{"text": o, "order": i} for i, o in enumerate(options)],
        "observer_ids": observer_ids or [],
    }
    if start_time:
        payload["start_time"] = start_time.isoformat()
    if end_time:
        payload["end_time"] = end_time.isoformat()
    return _post("/admin/topics", payload, token=token)


def admin_update_topic_status(topic_id: int, status: str, token: str) -> dict:
    return _put(f"/admin/topics/{topic_id}/status", {"status": status}, token=token)


def admin_set_observers(topic_id: int, observer_ids: list, token: str) -> dict:
    return _put(f"/admin/topics/{topic_id}/observers", {"observer_ids": observer_ids}, token=token)


# ─── Reports ─────────────────────────────────────────────────────────────────

def get_all_topics_summary(token: str) -> list:
    result = _get("/reports/topics", token=token)
    return result if isinstance(result, list) else []


def get_topic_report(topic_id: int, token: str) -> dict:
    return _get(f"/reports/topics/{topic_id}", token=token)


def export_csv(topic_id: int, token: str) -> bytes | None:
    return _get_bytes(f"/reports/topics/{topic_id}/export/csv", token=token)


def export_excel(topic_id: int, token: str) -> bytes | None:
    return _get_bytes(f"/reports/topics/{topic_id}/export/excel", token=token)


def get_audit_logs(token: str, limit: int = 100, action_filter: str = None) -> list:
    params = {"limit": limit}
    if action_filter:
        params["action_filter"] = action_filter
    result = _get("/reports/audit-logs", params=params, token=token)
    return result if isinstance(result, list) else []


# ─── Admin bootstrap ──────────────────────────────────────────────────────────

def bootstrap_admin(name: str, apartment_number: str, phone_number: str, admin_key: str) -> dict:
    return _post("/admin/bootstrap", {
        "name": name,
        "apartment_number": apartment_number,
        "phone_number": phone_number,
        "admin_key": admin_key,
    })
