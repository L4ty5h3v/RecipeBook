"""Интеграционные тесты preview endpoint."""

from __future__ import annotations

from urllib.parse import urlencode

from tests.integration.live_api_test_case import LiveApiTestCase


class PreviewApiTest(LiveApiTestCase):
    """Проверяет превью блюда и связанные сценарии расчёта."""

    def _preview(self, query: str, ingredients: list[str], expected_status: int = 200) -> dict:
        """Вызывает endpoint preview с подготовленными query-параметрами."""
        path = "/api/dishes/preview?" + urlencode(
            [("query", query), *[("ingredient", item) for item in ingredients]],
            doseq=True,
        )
        return self._request("GET", path, expected_status=expected_status)

    def _preview_single_carrot(self) -> dict:
        """Возвращает preview блюда с одной морковью."""
        carrot = self._create_product(
            name=self.make_test_name("морковь"),
            calories=41,
            protein=0.9,
            fat=0.2,
            carbs=9.6,
        )
        return self._preview(
            query=self.make_test_name("суп дня"),
            ingredients=[f"{carrot['id']}:100"],
        )

    def _preview_macro_soup(self) -> dict:
        """Возвращает preview блюда с макросом !суп."""
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
        return self._preview(
            query=f"!суп {self.make_test_name('овощной бульон')}",
            ingredients=[f"{carrot['id']}:100", f"{water['id']}:200"],
        )

    def _preview_macro_drink(self) -> dict:
        """Возвращает preview блюда с макросом !напиток."""
        product = self._create_product()
        return self._preview(
            query=f"!напиток {self.make_test_name('морс')}",
            ingredients=[f"{product['id']}:100"],
        )

    def test_preview_single_ingredient_calculates_calories(self) -> None:
        """Эквивалентное разбиение: одноингредиентное preview считает калории."""
        preview = self._preview_single_carrot()
        self.assertEqual(41.0, preview["suggested_nutrition"]["calories"])

    def test_preview_multiple_ingredients_calculates_calories(self) -> None:
        """Эквивалентное разбиение: многоингредиентное preview считает калории."""
        preview = self._preview_macro_soup()
        self.assertEqual(41.0, preview["suggested_nutrition"]["calories"])

    def test_preview_returns_available_vegan_flag(self) -> None:
        """Preview должно возвращать доступный флаг Веган для веганского состава."""
        preview = self._preview_single_carrot()
        self.assertIn("Веган", preview["available_flags"])

    def test_preview_normalizes_name_when_macro_is_used(self) -> None:
        """Preview должно очищать имя блюда от макроса категории."""
        preview = self._preview_macro_soup()
        self.assertEqual(self.make_test_name("овощной бульон"), preview["normalized_name"])

    def test_preview_uses_macro_category_as_effective_category(self) -> None:
        """Preview должно использовать категорию из макроса как effective_category."""
        preview = self._preview_macro_soup()
        self.assertEqual("Суп", preview["effective_category"])

    def test_preview_accepts_minimum_positive_quantity(self) -> None:
        """Анализ граничных значений: количество 0.01 должно оставаться валидным."""
        product = self._create_product(
            name=self.make_test_name("тыква"),
            calories=26,
            protein=1,
            fat=0.1,
            carbs=6.5,
        )
        preview = self._preview(
            query=self.make_test_name("тыквенный суп"),
            ingredients=[f"{product['id']}:0.01"],
        )
        self.assertEqual(0.0, preview["suggested_nutrition"]["calories"])

    def test_preview_rejects_zero_quantity(self) -> None:
        """Анализ граничных значений: количество 0 относится к невалидному классу."""
        product = self._create_product(
            name=self.make_test_name("тыква"),
            calories=26,
            protein=1,
            fat=0.1,
            carbs=6.5,
        )
        preview = self._preview(
            query=self.make_test_name("тыквенный суп"),
            ingredients=[f"{product['id']}:0"],
            expected_status=400,
        )
        self.assertIn("должно быть больше 0", preview["error"])

    def test_preview_drink_macro_normalizes_name(self) -> None:
        """Preview с макросом !напиток должно очищать имя от макроса."""
        preview = self._preview_macro_drink()
        self.assertEqual(self.make_test_name("морс"), preview["normalized_name"])

    def test_preview_drink_macro_returns_category_from_macro(self) -> None:
        """Preview должно возвращать category_from_macro для макроса !напиток."""
        preview = self._preview_macro_drink()
        self.assertEqual("Напиток", preview["category_from_macro"])

    def test_preview_drink_macro_returns_effective_category(self) -> None:
        """Preview должно возвращать effective_category из макроса !напиток."""
        preview = self._preview_macro_drink()
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
