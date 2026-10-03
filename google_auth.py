"""Sign in with Google (Android Credential Manager, android_src/org/holo/auth/GoogleSignInBridge.java).

Only used for account recovery: the pilot is linked to a Google account on the server; after a reinstall (or on a
new phone) picking the same Google account brings the pilot back. The game never sees a password - Google's own
account chooser runs and the server checks the ID token it returns.

config.json "google_client_id" = the OAuth *Web application* client id (the audience the server accepts).
Off the phone (desktop, tests) GoogleAuth.available() is False unless a test backend is injected.
"""
import config


class GoogleAuth:
    def __init__(self):
        self.client_id = str(config.get("google_client_id", "") or "").strip()
        self._bridge = None
        self._busy = False
        self.error = ""                       # why sign-in is unavailable / the last request failed (shown small)
        if not self.client_id:
            self.error = "no client id"
            return
        try:
            from jnius import autoclass   # python-for-android only
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            self._bridge = autoclass("org.holo.auth.GoogleSignInBridge")(activity)
        except Exception as e:
            print("Google sign-in unavailable:", e)
            self.error = type(e).__name__ + ": " + str(e)
            self._bridge = None

    def available(self):
        return self._bridge is not None

    @property
    def busy(self):
        return self._busy

    def request(self, only_authorized=False):
        """Opens Google's account chooser; the answer comes from poll()."""
        if not self.available() or self._busy:
            return False
        try:
            self._bridge.signIn(self.client_id, bool(only_authorized))
            self._busy = True
            return True
        except Exception as e:
            print("Google sign-in error:", e)
            self.error = type(e).__name__ + ": " + str(e)
            return False

    def poll(self):
        """None while waiting; ("ok", id_token) or ("fail", reason) once."""
        if not self._busy or self._bridge is None:
            return None
        try:
            raw = str(self._bridge.pollResult() or "")
        except Exception:
            raw = "FAIL|bridge"
        if not raw:
            return None
        self._busy = False
        kind, _, rest = raw.partition("|")
        return ("ok", rest) if kind == "OK" else ("fail", rest or "error")
