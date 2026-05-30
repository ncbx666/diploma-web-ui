from __future__ import annotations

import html
import mimetypes
import os
import re
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

from .inference import get_profile, predict_workbook, result_to_excel_bytes


APP_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_ROOT / "app" / "static"
TEMPLATE_PATH = APP_ROOT / "app" / "templates" / "index.html"
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


class DiseaseForecastHandler(BaseHTTPRequestHandler):
    server_version = "DiseaseForecastWeb/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(TEMPLATE_PATH.read_text(encoding="utf-8"))
            return
        if path == "/health":
            self._send_text("ok")
            return
        if path.startswith("/static/"):
            self._send_static(path.removeprefix("/static/"))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/predict":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            filename, payload, profile_key = self._read_form()
            profile = get_profile(profile_key)
            result = predict_workbook(BytesIO(payload), profile.key)
            output = result_to_excel_bytes(result)
        except Exception as exc:
            self._send_upload_error(str(exc))
            return

        safe_name = _safe_filename(filename)
        response_name = f"marked_{profile.key}_{safe_name}"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Length", str(len(output)))
        self.send_header("Content-Disposition", f'attachment; filename="{response_name}"')
        self.end_headers()
        self.wfile.write(output)

    def log_message(self, format: str, *args) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _read_form(self) -> tuple[str, bytes, str]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Файл не был передан.")
        if content_length > MAX_UPLOAD_BYTES:
            raise ValueError("Файл слишком большой. Максимальный размер: 30 МБ.")

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("Ожидается multipart/form-data загрузка.")

        body = self.rfile.read(content_length)
        message_bytes = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + body
        )
        message = BytesParser(policy=default).parsebytes(message_bytes)

        filename = ""
        payload = b""
        profile_key = "krasnodar_rice_blast"

        for part in message.iter_parts():
            disposition = part.get_content_disposition()
            field_name = part.get_param("name", header="content-disposition")
            if disposition != "form-data":
                continue

            if field_name == "disease":
                value = part.get_payload(decode=True) or b""
                profile_key = value.decode("utf-8", errors="ignore").strip() or profile_key
            elif field_name == "file":
                filename = part.get_filename() or "data.xlsx"
                payload = part.get_payload(decode=True) or b""

        if not filename:
            raise ValueError("Поле file не найдено в запросе.")
        if not filename.lower().endswith(".xlsx"):
            raise ValueError("Загрузите файл формата .xlsx.")
        if not payload:
            raise ValueError("Загруженный файл пустой.")
        return filename, payload, profile_key

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, relative_path: str) -> None:
        clean_path = unquote(relative_path).lstrip("/")
        if ".." in Path(clean_path).parts:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        file_path = STATIC_DIR / clean_path
        if not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_upload_error(self, message: str) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        escaped = html.escape(message)
        content = template.replace("<!--ERROR-->", f'<div class="notice error">{escaped}</div>')
        self._send_html(content, HTTPStatus.BAD_REQUEST)


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    if not name.lower().endswith(".xlsx"):
        name = f"{name}.xlsx"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def run() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), DiseaseForecastHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
