import json, os, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "state.json")
ATTENDANCE_PATH = os.path.join(BASE_DIR, "attendance.json")

DEFAULT_STATE = {
    "selected_guest_code": "000",
    "selected_guest_at": None,
    "last_scan": None,
    "last_scan_at": None
}

def load_json(path, default):
    if not os.path.exists(path):
        return default.copy() if isinstance(default, dict) else default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(default, dict):
            merged = default.copy()
            merged.update(data or {})
            return merged
        return data
    except Exception:
        return default.copy() if isinstance(default, dict) else default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_state():
    return load_json(STATE_PATH, DEFAULT_STATE)

def save_state(state):
    save_json(STATE_PATH, state)

def load_attendance():
    return load_json(ATTENDANCE_PATH, {})

def save_attendance(data):
    save_json(ATTENDANCE_PATH, data)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def _json_response(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/state"):
            return self._json_response(load_state())
        if self.path.startswith("/api/attendance"):
            return self._json_response(load_attendance())
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError:
            return self._json_response({"error": "invalid_json"}, 400)

        if self.path == "/api/scan":
            code = str(data.get("code", "")).strip()
            if not code:
                return self._json_response({"error": "missing_code"}, 400)
            if len(code) < 3:
                code = code.zfill(3)
            state = load_state()
            state["last_scan"] = code
            state["last_scan_at"] = int(time.time() * 1000)
            save_state(state)
            return self._json_response({"ok": True, "last_scan": code})

        if self.path == "/api/select":
            code = str(data.get("code", "")).strip()
            if not code:
                return self._json_response({"error": "missing_code"}, 400)
            if len(code) < 3:
                code = code.zfill(3)
            state = load_state()
            state["selected_guest_code"] = code
            state["selected_guest_at"] = int(time.time() * 1000)
            save_state(state)
            return self._json_response({"ok": True, "selected_guest_code": code})

        if self.path == "/api/mark_attendance":
            code = str(data.get("code", "")).strip()
            if not code:
                return self._json_response({"error": "missing_code"}, 400)
            if len(code) < 3:
                code = code.zfill(3)
            attendance = load_attendance()
            already_marked = code in attendance
            if not already_marked:
                attendance[code] = time.strftime("%Y-%m-%d %H:%M:%S")
                save_attendance(attendance)
            return self._json_response({
                "ok": True,
                "code": code,
                "already_marked": already_marked,
                "shown_at": attendance.get(code)
            })

        if self.path == "/api/reset_attendance":
            save_attendance({})
            return self._json_response({"ok": True})

        self.send_error(404)

if __name__ == "__main__":
    save_state(load_state())
    save_attendance(load_attendance())
    port = int(os.environ.get("PORT", 8000))
    print(f"Server running on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
