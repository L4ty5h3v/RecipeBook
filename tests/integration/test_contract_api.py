"""Тесты транспортного контракта и ошибок тела запроса."""

from __future__ import annotations

from tests.integration.live_api_test_case import LiveApiTestCase


class ContractApiTest(LiveApiTestCase):
    """Проверяет поведение API при невалидном JSON и неверном формате тела."""

    def test_post_product_rejects_invalid_json_body(self) -> None:
        """POST /api/products должен отклонять невалидный JSON."""
        response = self._request_raw(
            "POST",
            "/api/products",
            "{bad json",
            expected_status=400,
        )
        self.assertIn("валидным JSON", response["error"])

    def test_post_product_rejects_non_object_json_body(self) -> None:
        """POST /api/products должен принимать только JSON object."""
        response = self._request_raw(
            "POST",
            "/api/products",
            '["not", "an", "object"]',
            expected_status=400,
        )
        self.assertIn("должно быть объектом", response["error"])

    def test_post_dish_rejects_invalid_json_body(self) -> None:
        """POST /api/dishes должен отклонять невалидный JSON."""
        response = self._request_raw(
            "POST",
            "/api/dishes",
            "{bad json",
            expected_status=400,
        )
        self.assertIn("валидным JSON", response["error"])

    def test_put_product_rejects_invalid_json_body(self) -> None:
        """PUT /api/products/{id} должен валидировать JSON-тело."""
        product = self._create_product()
        response = self._request_raw(
            "PUT",
            f"/api/products/{product['id']}",
            "{bad json",
            expected_status=400,
        )
        self.assertIn("валидным JSON", response["error"])
