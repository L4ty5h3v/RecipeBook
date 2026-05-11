"""Вспомогательный клиент для UI-тестов против уже запущенного приложения."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class LiveAppClient:
    """Мини-клиент публичного API для setup/teardown UI-тестов."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def require_available(self) -> None:
        """Проверяет, что приложение запущено и отдаёт справочники."""
        try:
            self.request("GET", "/api/meta")
        except URLError as exc:
            raise RuntimeError(
                "UI-тесты требуют запущенное приложение. "
                "Запустите `python run.py` или задайте RECIPEBOOK_UI_BASE_URL."
            ) from exc

    def cleanup_entities(self, prefix: str) -> None:
        """Удаляет блюда и продукты, созданные UI-тестами с указанным префиксом."""
        dishes = self.request("GET", f"/api/dishes?{urlencode({'query': prefix})}")
        for dish in dishes:
            if dish["name"].startswith(prefix):
                self.request("DELETE", f"/api/dishes/{dish['id']}", expected_status=204)

        products = self.request("GET", f"/api/products?{urlencode({'query': prefix})}")
        for product in products:
            if product["name"].startswith(prefix):
                self.request("DELETE", f"/api/products/{product['id']}", expected_status=204)

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        expected_status: int = 200,
    ) -> dict | list | None:
        """Выполняет JSON-запрос к API и возвращает разобранный ответ."""
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = Request(
            url=f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return self._read_response(response.status, response.read(), expected_status)
        except HTTPError as error:
            try:
                return self._read_response(error.code, error.read(), expected_status)
            finally:
                error.close()

    @staticmethod
    def _read_response(
        actual_status: int,
        raw_body: bytes,
        expected_status: int,
    ) -> dict | list | None:
        if actual_status != expected_status:
            raise AssertionError(
                f"Ожидался HTTP {expected_status}, получен HTTP {actual_status}. "
                f"Ответ: {raw_body.decode('utf-8')}"
            )
        if not raw_body:
            return None
        return json.loads(raw_body.decode("utf-8"))
