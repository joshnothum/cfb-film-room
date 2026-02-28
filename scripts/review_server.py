#!/usr/bin/env python3
import argparse
import json
import mimetypes
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "web" / "review"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON ({exc})") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def backup_jsonl(source: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = out_dir / f"{source.stem}.{stamp}{source.suffix}"
    target.write_bytes(source.read_bytes())
    return target


class ReviewState:
    def __init__(self, *, data_file: Path, backups_dir: Path):
        self.data_file = data_file
        self.backups_dir = backups_dir
        self.lock = threading.Lock()
        self.rows = load_jsonl(data_file)
        self.index_by_play_id: dict[str, int] = {}
        self._reindex()

    def _reindex(self) -> None:
        self.index_by_play_id = {}
        for idx, row in enumerate(self.rows):
            play_id = row.get("play_id")
            if play_id is not None:
                self.index_by_play_id[str(play_id)] = idx

    def get_rows(self) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.rows]

    def update_row(self, play_id: str, payload: dict) -> dict:
        with self.lock:
            idx = self.index_by_play_id.get(play_id)
            if idx is None:
                raise KeyError(play_id)

            current = dict(self.rows[idx])
            incoming = dict(payload)
            incoming["play_id"] = current.get("play_id")
            incoming["game_id"] = current.get("game_id")
            self.rows[idx] = incoming

            backup_jsonl(self.data_file, self.backups_dir)
            write_jsonl(self.data_file, self.rows)
            return dict(self.rows[idx])


class ReviewHandler(BaseHTTPRequestHandler):
    server: "ReviewHTTPServer"

    def _json_response(self, payload: dict | list, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        data = path.read_bytes()
        ctype = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_clip(self, clip_path: Path) -> None:
        if not clip_path.exists() or not clip_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Clip not found")
            return

        file_size = clip_path.stat().st_size
        content_type = mimetypes.guess_type(str(clip_path))[0] or "video/mp4"
        range_header = self.headers.get("Range")

        if not range_header:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with clip_path.open("rb") as handle:
                self.wfile.write(handle.read())
            return

        try:
            units, byte_range = range_header.split("=", 1)
            if units.strip().lower() != "bytes":
                raise ValueError("unsupported range units")
            start_str, end_str = byte_range.split("-", 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            if start < 0 or end >= file_size or start > end:
                raise ValueError("invalid range")
        except Exception:
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "Bad range")
            return

        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        with clip_path.open("rb") as handle:
            handle.seek(start)
            self.wfile.write(handle.read(length))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path

        if route in {"/", "/index.html"}:
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if route == "/app.js":
            self._serve_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if route == "/style.css":
            self._serve_file(STATIC_DIR / "style.css", "text/css; charset=utf-8")
            return

        if route == "/api/plays":
            rows = self.server.state.get_rows()
            self._json_response({"rows": rows, "count": len(rows)})
            return

        if route == "/api/clip":
            qs = parse_qs(parsed.query)
            raw = qs.get("path", [None])[0]
            if not raw:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing path")
                return
            clip = Path(unquote(raw)).resolve()
            if ROOT not in clip.parents and clip != ROOT:
                self.send_error(HTTPStatus.FORBIDDEN, "Clip path outside workspace")
                return
            self._serve_clip(clip)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        if not route.startswith("/api/play/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        play_id = unquote(route.removeprefix("/api/play/"))
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing body")
            return

        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        if not isinstance(payload, dict):
            self.send_error(HTTPStatus.BAD_REQUEST, "Payload must be JSON object")
            return

        try:
            updated = self.server.state.update_row(play_id, payload)
        except KeyError:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown play_id")
            return

        self._json_response({"status": "ok", "row": updated})


class ReviewHTTPServer(ThreadingHTTPServer):
    def __init__(self, addr: tuple[str, int], state: ReviewState):
        super().__init__(addr, ReviewHandler)
        self.state = state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local play review web app.")
    parser.add_argument(
        "--data-file",
        default="data/qa/ocr_gold_batch_20260227.jsonl",
        help="Path to OCR gold JSONL file to review/edit.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8787, help="Bind port (default: 8787).")
    parser.add_argument(
        "--backups-dir",
        default="data/qa/backups",
        help="Directory for auto-backups before save.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_file = Path(args.data_file).resolve()
    backups_dir = Path(args.backups_dir).resolve()

    if not data_file.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}")

    try:
        state = ReviewState(data_file=data_file, backups_dir=backups_dir)
    except ValueError as exc:
        print(f"Cannot start review app: {exc}")
        print("Tip: run scripts/format_jsonl.py + scripts/check_ocr_gold.py on the file first.")
        return 1
    server = ReviewHTTPServer((args.host, args.port), state)

    print(f"Review app running at http://{args.host}:{args.port}")
    print(f"Editing file: {data_file}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping review app.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
