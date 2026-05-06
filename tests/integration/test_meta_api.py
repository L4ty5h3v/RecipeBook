"""Тесты справочных и route-level API сценариев."""

from __future__ import annotations

from tests.integration.live_api_test_case import LiveApiTestCase


class MetaApiTest(LiveApiTestCase):
    """Проверяет справочные endpoint'ы и общие API-маршруты."""

    def test_get_meta_returns_all_reference_values(self) -> None:
        """API метаданных должно возвращать все справочники для UI и валидации."""
        meta = self._request("GET", "/api/meta")
        self.assertIn("Овощи", meta["product_categories"])
        self.assertIn("Требует приготовления", meta["cooking_states"])
        self.assertIn("Суп", meta["dish_categories"])
        self.assertIn("Веган", meta["flags"])

    def test_unknown_api_route_returns_json_not_found(self) -> None:
        """Неизвестный API route должен возвращать JSON-ошибку 404."""
        response = self._request("POST", "/api/unknown", payload={}, expected_status=404)
        self.assertEqual("Маршрут не найден.", response["error"])
