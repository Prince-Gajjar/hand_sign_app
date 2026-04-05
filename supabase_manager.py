import os
import json

# Detect platform early — Kivy's platform util is the most reliable way
try:
    from kivy.utils import platform as _kivy_platform  # pyre-ignore
    _IS_ANDROID = (_kivy_platform == 'android')
except Exception:
    _IS_ANDROID = False


def _get_writable_dir() -> str:
    """Return a writable directory that works on both Android and Desktop."""
    if _IS_ANDROID:
        # On Android, the app source dir is read-only inside the APK.
        # user_data_dir (e.g. /data/data/org.accessibility.handsignai/files/) is writable.
        try:
            from kivy.app import App  # pyre-ignore
            app = App.get_running_app()
            if app and hasattr(app, 'user_data_dir'):
                return str(app.user_data_dir)
        except Exception:
            pass
        # Fallback: Android internal storage
        return '/data/data/org.accessibility.handsignai/files'
    # Desktop: write next to main.py
    return os.path.dirname(os.path.abspath(__file__))


# Lazy import supabase so the app doesn't crash if it's unavailable
try:
    from supabase import create_client, Client as _SupabaseClient  # type: ignore
    _SUPABASE_AVAILABLE = True
except Exception:
    _SUPABASE_AVAILABLE = False
    _SupabaseClient = object  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore


def _load_env_files() -> None:
    """Load .env from common runtime locations (desktop + packaged app)."""
    if load_dotenv is None:
        return

    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
        os.path.join(os.getcwd(), '.env'),
    ]

    # Avoid duplicates while preserving order
    seen = set()
    for path in candidates:
        norm = os.path.normpath(path)
        if norm in seen:
            continue
        seen.add(norm)
        try:
            if os.path.exists(path):
                load_dotenv(path, override=False)
        except Exception:
            pass


_load_env_files()


class SupabaseManager:
    """Singleton manager for all Supabase auth and database operations."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Session file in a writable location
        self._session_filename = 'session_data.json'
        # Resolve the actual path lazily (ensures Kivy app is running first)
        self._session_file_path: str = ''
        self._available = False
        self._status_reason = "Supabase client not initialized"

        if _SUPABASE_AVAILABLE:
            url = (os.environ.get("SUPABASE_URL", "") or "").strip()
            key = (
                os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
                or os.environ.get("SUPABASE_ANON_KEY", "")
                or os.environ.get("SUPABASE_KEY", "")
                or ""
            ).strip()
            if url and key and "your-project" not in url:
                try:
                    self.client = create_client(url, key)  # type: ignore
                    self._available = True
                    self._status_reason = "OK"
                    print("Supabase: Client initialised successfully")
                except Exception as e:
                    print(f"Supabase: Failed to create client: {e}")
                    self.client = None  # type: ignore
                    self._available = False
                    self._status_reason = f"Client initialization failed: {e}"
            else:
                print("Supabase: SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY not set in environment — running offline")
                self.client = None  # type: ignore
                self._available = False
                self._status_reason = "Missing SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY/SUPABASE_ANON_KEY/SUPABASE_KEY"
        else:
            print("Supabase: supabase-py not available — running offline")
            self.client = None  # type: ignore
            self._available = False
            self._status_reason = "Package 'supabase' is not installed"

    def _get_session_file(self) -> str:
        """Resolve (and cache) the writable session file path."""
        if not self._session_file_path:
            self._session_file_path = os.path.join(
                _get_writable_dir(), self._session_filename
            )
        return self._session_file_path

    def _extract_session(self, response):
        if response is None:
            return None
        if isinstance(response, dict):
            session = response.get("session")
            if session:
                return session
            data = response.get("data")
            if isinstance(data, dict):
                return data.get("session")
            return None
        session = getattr(response, "session", None)
        if session:
            return session
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            return data.get("session")
        return None

    def is_available(self) -> bool:
        return bool(self._available and self.client is not None)

    def availability_reason(self) -> str:
        return self._status_reason

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def _save_session(self, session) -> None:
        try:
            path = self._get_session_file()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump({
                    "access_token": session.access_token,
                    "refresh_token": session.refresh_token
                }, f)
        except Exception as e:
            print(f"Supabase: Failed to save session: {e}")

    def load_session(self):
        if not self.is_available():
            return None, self.availability_reason()
        path = self._get_session_file()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                access_token = data.get("access_token") if isinstance(data, dict) else None
                refresh_token = data.get("refresh_token") if isinstance(data, dict) else None
                if not access_token or not refresh_token:
                    self._clear_session()
                    return None, "Invalid local session format"
                res = self.client.auth.set_session(access_token, refresh_token)
                return res, None
            except Exception as e:
                self._clear_session()
                return None, str(e)
        return None, "No local session found"

    def _clear_session(self) -> None:
        path = self._get_session_file()
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Auth operations
    # ------------------------------------------------------------------
    def sign_up(self, email, password):
        if not self.is_available():
            return None, self.availability_reason()
        try:
            response = self.client.auth.sign_up({"email": email, "password": password})
            session = self._extract_session(response)
            if session:
                self._save_session(session)
            return response, None
        except Exception as e:
            return None, str(e)

    def sign_in(self, email, password):
        if not self.is_available():
            return None, self.availability_reason()
        try:
            response = self.client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            session = self._extract_session(response)
            if session:
                self._save_session(session)
            return response, None
        except Exception as e:
            return None, str(e)

    def sign_out(self):
        if not self.is_available():
            self._clear_session()
            return True, None  # Already "signed out" locally
        try:
            self.client.auth.sign_out()
            self._clear_session()
            return True, None
        except Exception as e:
            self._clear_session()  # Clear locally even if server call fails
            return False, str(e)

    def get_user(self):
        if not self.is_available():
            return None, self.availability_reason()
        try:
            return self.client.auth.get_user(), None
        except Exception as e:
            return None, str(e)

    # ------------------------------------------------------------------
    # Custom gestures database
    # ------------------------------------------------------------------
    def save_custom_gesture(self, user_id, phrase, features):
        if not self.is_available():
            return None, self.availability_reason()
        try:
            response = self.client.table("custom_gestures").insert({
                "user_id": user_id,
                "phrase": phrase,
                "features": features
            }).execute()
            return response.data, None
        except Exception as e:
            return None, str(e)

    def get_custom_gestures(self, user_id):
        if not self.is_available():
            return None, self.availability_reason()
        try:
            response = (
                self.client.table("custom_gestures")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            return response.data, None
        except Exception as e:
            return None, str(e)
