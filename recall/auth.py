import json
from pathlib import Path

from supabase import Client

SESSION_FILE = Path.home() / ".recall" / "session.json"


def save_session(session_data: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(session_data, f)


def load_session() -> dict | None:
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink(missing_ok=True)


def restore_session(client: Client) -> tuple[str, str] | None:
    """Try to restore a saved session onto the Supabase client.

    Returns (user_id, email) if successful, None otherwise.
    """
    session_data = load_session()
    if not session_data:
        return None

    try:
        client.auth.set_session(
            session_data["access_token"],
            session_data["refresh_token"],
        )
        refresh_res = client.auth.refresh_session()
        user = refresh_res.user
        if not user:
            clear_session()
            return None
        current = client.auth.get_session()
        if current:
            save_session({
                "access_token": current.access_token,
                "refresh_token": current.refresh_token,
                "user": {"id": user.id, "email": user.email},
            })
        return user.id, user.email
    except Exception:
        clear_session()
        return None


def sign_in(client: Client, email: str, password: str) -> tuple[str, str]:
    """Sign in with email and password. Returns (user_id, email)."""
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    user = res.user
    current = client.auth.get_session()
    save_session({
        "access_token": current.access_token,
        "refresh_token": current.refresh_token,
        "user": {"id": user.id, "email": user.email},
    })
    return user.id, user.email


def sign_up(client: Client, email: str, password: str) -> tuple[str, str] | None:
    """Sign up with email and password.

    Returns (user_id, email) or None if email confirmation is required.
    """
    res = client.auth.sign_up({"email": email, "password": password})
    user = res.user
    if not user:
        return None
    if res.session:
        current = client.auth.get_session()
        save_session({
            "access_token": current.access_token,
            "refresh_token": current.refresh_token,
            "user": {"id": user.id, "email": user.email},
        })
        return user.id, user.email
    return None


def sign_out(client: Client) -> None:
    """Sign out and clear the saved session."""
    try:
        client.auth.sign_out()
    except Exception:
        pass
    clear_session()
