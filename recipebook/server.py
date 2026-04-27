from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recipebook.service import (
    ConflictError,
    NotFoundError,
    RecipeBookService,
    ValidationError,
)
from recipebook.store import JsonStore


def run(base_dir: Path, host: str = "127.0.0.1", port: int = 8080) -> None:
    service = RecipeBookService(JsonStore(base_dir / "data" / "db.json"))
    static_dir = base_dir / "static"
    pictures_dir = base_dir / "pictures"

    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/meta":
                return self._handle_api(lambda: service.get_meta())
            if parsed.path == "/api/products":
                params = self._query_params(parsed.query)
                return self._handle_api(lambda: service.list_products(params))
            if parsed.path == "/api/dishes":
                params = self._query_params(parsed.query)
                return self._handle_api(lambda: service.list_dishes(params))
            if parsed.path == "/api/dishes/preview":
                params = self._query_params(parsed.query)
                payload = self._query_payload(params)
                return self._handle_api(lambda: service.preview_dish(payload))
            if parsed.path.startswith("/api/products/"):
                product_id = parsed.path.rsplit("/", 1)[-1]
                return self._handle_api(lambda: service.get_product(product_id))
            if parsed.path.startswith("/api/dishes/"):
                dish_id = parsed.path.rsplit("/", 1)[-1]
                return self._handle_api(lambda: service.get_dish(dish_id))
            self._serve_file(parsed.path)

        def do_POST(self) -> None:
            if self.path == "/api/products":
                return self._handle_api(
                    lambda: service.create_product(self._read_json()),
                    status=HTTPStatus.CREATED,
                )
            if self.path == "/api/dishes":
                return self._handle_api(
                    lambda: service.create_dish(self._read_json()),
                    status=HTTPStatus.CREATED,
                )
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})

        def do_PUT(self) -> None:
            if self.path.startswith("/api/products/"):
                product_id = self.path.rsplit("/", 1)[-1]
                return self._handle_api(
                    lambda: service.update_product(product_id, self._read_json())
                )
            if self.path.startswith("/api/dishes/"):
                dish_id = self.path.rsplit("/", 1)[-1]
                return self._handle_api(
                    lambda: service.update_dish(dish_id, self._read_json())
                )
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})

        def do_DELETE(self) -> None:
            if self.path.startswith("/api/products/"):
                product_id = self.path.rsplit("/", 1)[-1]
                return self._handle_api(
                    lambda: service.delete_product(product_id),
                    status=HTTPStatus.NO_CONTENT,
                )
            if self.path.startswith("/api/dishes/"):
                dish_id = self.path.rsplit("/", 1)[-1]
                return self._handle_api(
                    lambda: service.delete_dish(dish_id),
                    status=HTTPStatus.NO_CONTENT,
                )
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})

        def log_message(self, fmt: str, *args) -> None:
            return

        def _handle_api(self, handler, status: HTTPStatus = HTTPStatus.OK) -> None:
            try:
                payload = handler()
            except ValidationError as error:
                self._json_response(
                    HTTPStatus.BAD_REQUEST, {"error": str(error)}
                )
                return
            except NotFoundError as error:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except ConflictError as error:
                body = {"error": str(error), **error.payload}
                self._json_response(HTTPStatus.CONFLICT, body)
                return

            if status == HTTPStatus.NO_CONTENT:
                self.send_response(status)
                self.end_headers()
                return
            self._json_response(status, payload)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(raw or "{}")
            except json.JSONDecodeError as exc:
                raise ValidationError("Тело запроса должно быть валидным JSON.") from exc
            if not isinstance(payload, dict):
                raise ValidationError("Тело запроса должно быть объектом.")
            return payload

        def _json_response(self, status: HTTPStatus, payload: dict | list) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_file(self, raw_path: str) -> None:
            path = "/" if raw_path == "" else raw_path
            if path == "/":
                file_path = static_dir / "index.html"
            elif path.startswith("/pictures/"):
                file_path = pictures_dir / path.removeprefix("/pictures/")
            else:
                file_path = static_dir / path.lstrip("/")
            if not file_path.exists() or not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            content = file_path.read_bytes()
            content_type, _ = mimetypes.guess_type(str(file_path))
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8"
            )
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _query_params(self, query: str) -> dict:
            raw = parse_qs(query, keep_blank_values=True)
            return {
                "query": raw.get("query", [""])[0],
                "category": raw.get("category", [None])[0],
                "cooking_state": raw.get("cooking_state", [None])[0],
                "flags": raw.get("flag", []),
                "sort_by": raw.get("sort_by", ["name"])[0],
            }

        def _query_payload(self, params: dict) -> dict:
            ingredients = []
            ingredients_raw = parse_qs(urlparse(self.path).query).get("ingredient", [])
            for item in ingredients_raw:
                product_id, quantity = item.split(":", 1)
                ingredients.append({"product_id": product_id, "quantity": quantity})
            return {
                "name": params.get("query") or "",
                "category": params.get("category"),
                "ingredients": ingredients,
            }

    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"Recipe Book is running at http://{host}:{port}")
    server.serve_forever()
