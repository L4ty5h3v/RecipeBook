"""Базовая инфраструктура для integration-тестов против живого backend."""

from __future__ import annotations

import json
import os
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tests.integration.payloads import build_dish_payload, build_product_payload


class LiveApiTestCase(unittest.TestCase):
    """Общий базовый класс для тестов, работающих с реальным HTTP API."""

    base_url = os.environ.get("RECIPEBOOK_TEST_BASE_URL", "http://127.0.0.1:8080")
    test_prefix = "__api_test__"

    def setUp(self) -> None:
        """Удаляет только тестовые сущности, не затрагивая пользовательские данные."""
        self._cleanup_test_entities()

    def tearDown(self) -> None:
        """Удаляет тестовые сущности после выполнения теста."""
        self._cleanup_test_entities()

    @classmethod
    def _request_static(
        cls,
        method: str,
        path: str,
        payload: dict | None = None,
        expected_status: int = 200,
    ) -> dict | list | None:
        """Отправляет JSON-запрос к живому backend и возвращает JSON-ответ."""
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = Request(
            url=f"{cls.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request) as response:
                response_body = response.read().decode("utf-8")
                if response.status != expected_status:
                    raise AssertionError(
                        f"Expected status {expected_status}, got {response.status} for {method} {path}"
                    )
                if not response_body:
                    return None
                return json.loads(response_body)
        except HTTPError as error:
            try:
                response_body = error.read().decode("utf-8")
                if error.code != expected_status:
                    raise AssertionError(
                        f"Expected status {expected_status}, got {error.code} for {method} {path}. "
                        f"Body: {response_body}"
                    ) from error
                if not response_body:
                    return None
                return json.loads(response_body)
            finally:
                error.close()

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        expected_status: int = 200,
    ) -> dict | list | None:
        """Отправляет JSON-запрос к API и возвращает JSON-ответ."""
        return self._request_static(
            method=method,
            path=path,
            payload=payload,
            expected_status=expected_status,
        )

    def _request_raw(
        self,
        method: str,
        path: str,
        body: str,
        expected_status: int,
        content_type: str = "application/json; charset=utf-8",
    ) -> dict | list | None:
        """Отправляет сырой HTTP body для проверок ошибок JSON-парсинга."""
        request = Request(
            url=f"{self.base_url}{path}",
            data=body.encode("utf-8"),
            headers={"Content-Type": content_type},
            method=method,
        )
        try:
            with urlopen(request) as response:
                response_body = response.read().decode("utf-8")
                self.assertEqual(expected_status, response.status)
                if not response_body:
                    return None
                return json.loads(response_body)
        except HTTPError as error:
            try:
                response_body = error.read().decode("utf-8")
                self.assertEqual(expected_status, error.code)
                if not response_body:
                    return None
                return json.loads(response_body)
            finally:
                error.close()

    def make_test_name(self, label: str) -> str:
        """Возвращает имя тестовой сущности с безопасным префиксом."""
        return f"{self.test_prefix}{label}"

    def _test_query(self, label: str = "") -> str:
        """Возвращает строку поиска, ограничивающую выборку тестовыми данными."""
        return self.make_test_name(label)

    def _cleanup_test_entities(self) -> None:
        """Удаляет только сущности, созданные integration-тестами."""
        dishes = self._request("GET", f"/api/dishes?{urlencode({'query': self.test_prefix})}")
        for dish in dishes:
            if dish["name"].startswith(self.test_prefix):
                self._request("DELETE", f"/api/dishes/{dish['id']}", expected_status=204)

        products = self._request("GET", f"/api/products?{urlencode({'query': self.test_prefix})}")
        for product in products:
            if product["name"].startswith(self.test_prefix):
                self._request("DELETE", f"/api/products/{product['id']}", expected_status=204)

    def _create_product(self, **overrides: object) -> dict:
        """Создаёт тестовый продукт через публичный API."""
        name = str(overrides.pop("name", self.make_test_name("морковь")))
        payload = build_product_payload(name=name, **overrides)
        return self._request("POST", "/api/products", payload, expected_status=201)

    def _create_dish(self, **overrides: object) -> dict:
        """Создаёт тестовое блюдо через публичный API."""
        name = str(overrides.pop("name", self.make_test_name("овощной суп")))
        ingredients = overrides.pop("ingredients", None)
        if ingredients is None:
            product = self._create_product()
            ingredients = [{"product_id": product["id"], "quantity": 100}]
        payload = build_dish_payload(name=name, ingredients=ingredients, **overrides)
        return self._request("POST", "/api/dishes", payload, expected_status=201)
