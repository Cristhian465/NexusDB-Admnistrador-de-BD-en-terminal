#!/usr/bin/env python3
"""Mini servidor web para la landing de DBAdmin.

Sirve la pagina, el .exe, el contador de descargas y el panel admin.
Usa SQLite local para guardar las descargas y las IPs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
PRIMARY_EXE_FILE = BASE_DIR / "DB-CLI.exe"
LEGACY_EXE_FILE = BASE_DIR / "DBAdmin.exe"
DB_FILE = BASE_DIR / "analytics.sqlite3"
LOCK = threading.Lock()
ADMIN_KEY = os.environ.get("DBADMIN_ADMIN_KEY", "upt-admin")


def exe_file() -> Path | None:
    if PRIMARY_EXE_FILE.exists():
        return PRIMARY_EXE_FILE
    if LEGACY_EXE_FILE.exists():
        return LEGACY_EXE_FILE
    return None


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                downloaded_at TEXT NOT NULL,
                file_name TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    forwarded = handler.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = handler.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    return handler.client_address[0]


class DBAdminHandler(BaseHTTPRequestHandler):
    server_version = "DBAdminLanding/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status=status)

    def _serve_file(self, path: Path, content_type: str | None = None, download_name: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_json({"error": f"Archivo no encontrado: {path.name}"}, status=HTTPStatus.NOT_FOUND)
            return

        data = path.read_bytes()
        guessed_type = content_type or "application/octet-stream"
        headers = {}
        if download_name:
            headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        self._send_bytes(data, guessed_type, headers=headers)

    def _record_download(self) -> int:
        ip = client_ip(self)
        user_agent = self.headers.get("User-Agent", "desconocido")
        current_exe = exe_file()
        if current_exe is None:
            raise FileNotFoundError("No se encontro DB-CLI.exe dentro de media/.")
        with LOCK, get_db_connection() as conn:
            conn.execute(
                "INSERT INTO downloads (ip, user_agent, downloaded_at, file_name) VALUES (?, ?, ?, ?)",
                (ip, user_agent, now_iso(), current_exe.name),
            )
            conn.commit()
            row = conn.execute("SELECT COUNT(*) AS total FROM downloads").fetchone()
            return int(row["total"] if row else 0)

    def _get_stats(self) -> dict:
        with LOCK, get_db_connection() as conn:
            total_row = conn.execute("SELECT COUNT(*) AS total FROM downloads").fetchone()
            return {
                "total_downloads": int(total_row["total"] if total_row else 0),
            }

    def _get_downloads(self, limit: int = 100) -> list[dict]:
        safe_limit = max(1, min(limit, 500))
        with LOCK, get_db_connection() as conn:
            rows = conn.execute(
                "SELECT ip, user_agent, downloaded_at, file_name FROM downloads ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route in {"/", "/index.html"}:
            self._serve_file(INDEX_FILE, "text/html; charset=utf-8")
            return

        if route == "/download":
            current_exe = exe_file()
            if current_exe is None:
                self._send_json(
                    {
                        "error": "No se encontro DB-CLI.exe dentro de media/.",
                        "hint": "Coloca el ejecutable generado en media/DB-CLI.exe.",
                    },
                    status=HTTPStatus.NOT_FOUND,
                )
                return

            total = self._record_download()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{current_exe.name}"')
            self.send_header("X-DBAdmin-Downloads", str(total))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(current_exe.stat().st_size))
            self.end_headers()
            with current_exe.open("rb") as file_handle:
                self.wfile.write(file_handle.read())
            return

        if route == "/api/stats":
            self._send_json(self._get_stats())
            return

        if route == "/api/admin/downloads":
            if query.get("key", [""])[0] != ADMIN_KEY:
                self._send_json({"error": "Acceso denegado"}, status=HTTPStatus.FORBIDDEN)
                return
            try:
                limit = int(query.get("limit", [100])[0])
            except (TypeError, ValueError):
                limit = 100
            self._send_json({"downloads": self._get_downloads(limit=limit), "total": self._get_stats()["total_downloads"]})
            return

        if route == "/logo-upt.png":
            self._serve_file(BASE_DIR / "logo-upt.png", "image/png")
            return

        candidate = (BASE_DIR / route.lstrip("/")).resolve()
        if candidate.is_file() and str(candidate).startswith(str(BASE_DIR.resolve())):
            self._serve_file(candidate)
            return

        self._send_json({"error": "Recurso no encontrado"}, status=HTTPStatus.NOT_FOUND)


def main() -> None:
    init_db()
    host = os.environ.get("DBADMIN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("DBADMIN_PORT", "8000")))
    server = ThreadingHTTPServer((host, port), DBAdminHandler)
    print(f"DBAdmin landing en http://{host}:{port}")
    print("Usa /download para el .exe y /api/admin/downloads para el panel admin.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
