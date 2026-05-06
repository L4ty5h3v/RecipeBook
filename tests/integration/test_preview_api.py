"""Интеграционные тесты preview endpoint."""

from __future__ import annotations

from urllib.parse import urlencode

from tests.integration.live_api_test_case import LiveApiTestCase


class PreviewApiTest(LiveApiTestCase):
    """Проверяет превью блюда и связанные сценарии расчёта."""

    def test_preview_dish_supports_valid_equivalence_classes(self) -> None:
        """Эквивалентное разбиение: preview работает для одного и нескольких ингредиентов."""
        carrot = self._create_product(
            name=self.make_test_name("морковь"),
            calories=41,
            protein=0.9,
            fat=0.2,
            carbs=9.6,
        )
        water = self._create_product(
            name=self.make_test_name("вода"),
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
            flags=["Веган", "Без глютена", "Без сахара"],
        )

        cases = [
            {
                "query": self.make_test_name("суп дня"),
                "ingredients": [f"{carrot['id']}:100"],
                "expected_calories": 41.0,
            },
            {
                "query": f"!суп {self.make_test_name('овощной бульон')}",
                "ingredients": [f"{carrot['id']}:100", f"{water['id']}:200"],
                "expected_calories": 41.0,
            },
        ]

        for case in cases:
            with self.subTest(query=case["query"]):
                path = "/api/dishes/preview?" + urlencode(
                    [("query", case["query"]), *[("ingredient", item) for item in case["ingredients"]]],
                    doseq=True,
                )
                preview = self._request("GET", path)
                self.assertEqual(case["expected_calories"], preview["suggested_nutrition"]["calories"])
                self.assertIn("Веган", preview["available_flags"])
                if case["query"].startswith("!суп"):
                    self.assertEqual(self.make_test_name("овощной бульон"), preview["normalized_name"])
                    self.assertEqual("Суп", preview["effective_category"])

    def test_preview_dish_enforces_quantity_boundaries(self) -> None:
        """Анализ граничных значений: количество 0.01 валидно, 0 невалидно."""
        product = self._create_product(
            name=self.make_test_name("тыква"),
            calories=26,
            protein=1,
            fat=0.1,
            carbs=6.5,
        )
        cases = [
            {"quantity": 0.01, "expected_status": 200},
            {"quantity": 0, "expected_status": 400},
        ]

        for case in cases:
            with self.subTest(quantity=case["quantity"]):
                path = "/api/dishes/preview?" + urlencode(
                    {
                        "query": self.make_test_name("тыквенный суп"),
                        "ingredient": f"{product['id']}:{case['quantity']}",
                    }
                )
                preview = self._request("GET", path, expected_status=case["expected_status"])
                if case["expected_status"] == 200:
                    self.assertEqual(0.0, preview["suggested_nutrition"]["calories"])
                else:
                    self.assertIn("должно быть больше 0", preview["error"])

    def test_preview_dish_returns_macro_category_without_explicit_category(self) -> None:
        """Preview должен выводить категорию из макроса, если category не передана."""
        product = self._create_product()
        preview = self._request(
            "GET",
            "/api/dishes/preview?"
            + urlencode(
                [("query", f"!напиток {self.make_test_name('морс')}"), ("ingredient", f"{product['id']}:100")],
                doseq=True,
            ),
        )
        self.assertEqual(self.make_test_name("морс"), preview["normalized_name"])
        self.assertEqual("Напиток", preview["category_from_macro"])
        self.assertEqual("Напиток", preview["effective_category"])

    def test_preview_dish_rejects_missing_ingredients(self) -> None:
        """Preview блюда требует хотя бы один ингредиент."""
        response = self._request(
            "GET",
            "/api/dishes/preview?" + urlencode({"query": self.make_test_name("пустой суп")}),
            expected_status=400,
        )
        self.assertIn("хотя бы один ингредиент", response["error"])

    def test_preview_dish_rejects_unknown_product(self) -> None:
        """Preview блюда отвергает несуществующий product_id."""
        response = self._request(
            "GET",
            "/api/dishes/preview?"
            + urlencode([("query", self.make_test_name("суп")), ("ingredient", "missing-id:100")], doseq=True),
            expected_status=400,
        )
        self.assertIn("несуществующий продукт", response["error"])
