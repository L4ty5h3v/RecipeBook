"""Интеграционные тесты HTTP API Recipe Book.

Тесты поднимают настоящий HTTP-сервер на временной JSON-базе и проверяют
backend через публичные API без изоляции бизнес-слоя. Для генерации тестовых
данных используются техники эквивалентного разбиения и анализа граничных
значений.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from recipebook.server import build_server


class RecipeBookApiIntegrationTest(unittest.TestCase):
    """Проверяет поведение backend через HTTP API без моков и заглушек."""

    @classmethod
    def setUpClass(cls) -> None:
        """Поднимает реальный HTTP-сервер один раз на весь test suite."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.base_dir = Path(cls.temp_dir.name)
        (cls.base_dir / "data").mkdir(parents=True, exist_ok=True)
        (cls.base_dir / "static").mkdir(parents=True, exist_ok=True)
        (cls.base_dir / "pictures").mkdir(parents=True, exist_ok=True)
        cls._reset_store()

        cls.server = build_server(cls.base_dir, host="127.0.0.1", port=0)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.server_thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        """Останавливает сервер и удаляет временные данные."""
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        cls.temp_dir.cleanup()

    @classmethod
    def _reset_store(cls) -> None:
        """Возвращает базу в пустое состояние перед каждым тестом."""
        db_path = cls.base_dir / "data" / "db.json"
        db_path.write_text(
            json.dumps({"products": [], "dishes": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def setUp(self) -> None:
        """Очищает временную базу, сохраняя поднятый HTTP-сервер."""
        self._reset_store()

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        expected_status: int = 200,
    ) -> dict | list | None:
        """Отправляет JSON-запрос к API и возвращает JSON-ответ."""
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

    def _create_product(self, **overrides: object) -> dict:
        """Создаёт продукт с валидными значениями по умолчанию."""
        payload = {
            "name": "Морковь",
            "photos": [],
            "calories": 41,
            "protein": 0.9,
            "fat": 0.2,
            "carbs": 9.6,
            "composition": "Морковь 100%",
            "category": "Овощи",
            "cooking_state": "Готовый к употреблению",
            "flags": ["Веган", "Без глютена", "Без сахара"],
        }
        payload.update(overrides)
        return self._request("POST", "/api/products", payload, expected_status=201)

    def _create_dish(self, **overrides: object) -> dict:
        """Создаёт блюдо с валидными значениями по умолчанию."""
        if "ingredients" not in overrides:
            product = self._create_product()
            overrides["ingredients"] = [{"product_id": product["id"], "quantity": 100}]

        payload = {
            "name": "Овощной суп",
            "photos": [],
            "portion_size": 250,
            "category": "Суп",
            "flags": ["Веган", "Без глютена", "Без сахара"],
        }
        payload.update(overrides)
        return self._request("POST", "/api/dishes", payload, expected_status=201)

    def test_create_product_supports_valid_equivalence_classes(self) -> None:
        """Эквивалентное разбиение: API принимает продукты из разных валидных классов."""
        cases = [
            {
                "name": "Вода",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "composition": "",
                "category": "Жидкость",
                "cooking_state": "Готовый к употреблению",
                "flags": ["Веган", "Без глютена", "Без сахара"],
            },
            {
                "name": "Филе индейки",
                "calories": 110,
                "protein": 23,
                "fat": 1,
                "carbs": 1,
                "composition": "Индейка",
                "category": "Мясной",
                "cooking_state": "Требует приготовления",
                "flags": ["Без глютена", "Без сахара"],
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                created = self._create_product(**case)
                fetched = self._request("GET", f"/api/products/{created['id']}")
                self.assertEqual(case["name"], fetched["name"])
                self.assertEqual(case["category"], fetched["category"])
                self.assertEqual(case["flags"], fetched["flags"])

    def test_create_product_enforces_name_boundaries(self) -> None:
        """Граничные значения: имя длиной 2 валидно, длиной 1 невалидно."""
        cases = [
            {"name": "Ай", "expected_status": 201},
            {"name": "A", "expected_status": 400},
        ]

        for case in cases:
            with self.subTest(name=case["name"]):
                response = self._request(
                    "POST",
                    "/api/products",
                    {
                        "name": case["name"],
                        "photos": [],
                        "calories": 0,
                        "protein": 0,
                        "fat": 0,
                        "carbs": 0,
                        "composition": "",
                        "category": "Жидкость",
                        "cooking_state": "Готовый к употреблению",
                        "flags": [],
                    },
                    expected_status=case["expected_status"],
                )
                if case["expected_status"] == 400:
                    self.assertIn("минимум 2 символа", response["error"])

    def test_create_product_enforces_photo_count_boundary(self) -> None:
        """Граничные значения: 5 фотографий допустимы, 6 уже нет."""
        valid_photos = [f"/pictures/{index}.png" for index in range(5)]
        invalid_photos = [f"/pictures/{index}.png" for index in range(6)]

        created = self._create_product(name="Тыква", photos=valid_photos)
        self.assertEqual(5, len(created["photos"]))

        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Тыква extra",
                "photos": invalid_photos,
                "calories": 26,
                "protein": 1,
                "fat": 0.1,
                "carbs": 6.5,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": ["Веган"],
            },
            expected_status=400,
        )
        self.assertIn("не более 5 фотографий", response["error"])

    def test_create_product_enforces_macro_boundary(self) -> None:
        """Граничные значения: БЖУ 100 допустимо, значение выше 100 не допускается."""
        cases = [
            {"protein": 100, "fat": 0, "carbs": 0, "expected_status": 201},
            {"protein": 100.01, "fat": 0, "carbs": 0, "expected_status": 400},
        ]

        for case in cases:
            with self.subTest(protein=case["protein"]):
                response = self._request(
                    "POST",
                    "/api/products",
                    {
                        "name": f"Белковый продукт {case['protein']}",
                        "photos": [],
                        "calories": 400.04,
                        "protein": case["protein"],
                        "fat": case["fat"],
                        "carbs": case["carbs"],
                        "composition": "",
                        "category": "Мясной",
                        "cooking_state": "Готовый к употреблению",
                        "flags": [],
                    },
                    expected_status=case["expected_status"],
                )
                if case["expected_status"] == 400:
                    self.assertIn("не может превышать 100", response["error"])

    def test_preview_dish_supports_valid_equivalence_classes(self) -> None:
        """Эквивалентное разбиение: preview работает для блюда из одного и нескольких ингредиентов."""
        carrot = self._create_product(name="Морковь", calories=41, protein=0.9, fat=0.2, carbs=9.6)
        water = self._create_product(
            name="Вода",
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
                "query": "Суп дня",
                "ingredients": [f"{carrot['id']}:100"],
                "expected_calories": 41.0,
            },
            {
                "query": "!суп Овощной бульон",
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
                    self.assertEqual("Овощной бульон", preview["normalized_name"])
                    self.assertEqual("Суп", preview["effective_category"])

    def test_preview_dish_enforces_quantity_boundaries(self) -> None:
        """Граничные значения: количество 0.01 валидно, 0 невалидно."""
        product = self._create_product(name="Тыква", calories=26, protein=1, fat=0.1, carbs=6.5)
        cases = [
            {"quantity": 0.01, "expected_status": 200},
            {"quantity": 0, "expected_status": 400},
        ]

        for case in cases:
            with self.subTest(quantity=case["quantity"]):
                path = "/api/dishes/preview?" + urlencode(
                    {
                        "query": "Тыквенный суп",
                        "ingredient": f"{product['id']}:{case['quantity']}",
                    }
                )
                preview = self._request("GET", path, expected_status=case["expected_status"])
                if case["expected_status"] == 200:
                    self.assertEqual(0.0, preview["suggested_nutrition"]["calories"])
                else:
                    self.assertIn("должно быть больше 0", preview["error"])

    def test_create_dish_rejects_invalid_equivalence_classes(self) -> None:
        """Эквивалентное разбиение: API отвергает пустой состав, неизвестный продукт и недоступный флаг."""
        product = self._create_product(name="Курица", calories=168, protein=24, fat=8, carbs=0, flags=["Без глютена"])
        cases = [
            {
                "name": "Без ингредиентов",
                "payload": {
                    "name": "Пустое блюдо",
                    "photos": [],
                    "portion_size": 200,
                    "category": "Суп",
                    "ingredients": [],
                    "flags": [],
                },
                "expected_error": "хотя бы один ингредиент",
            },
            {
                "name": "Несуществующий продукт",
                "payload": {
                    "name": "Секретное блюдо",
                    "photos": [],
                    "portion_size": 200,
                    "category": "Суп",
                    "ingredients": [{"product_id": "missing-id", "quantity": 100}],
                    "flags": [],
                },
                "expected_error": "несуществующий продукт",
            },
            {
                "name": "Недоступный флаг",
                "payload": {
                    "name": "Куриный суп",
                    "photos": [],
                    "portion_size": 200,
                    "category": "Суп",
                    "ingredients": [{"product_id": product["id"], "quantity": 100}],
                    "flags": ["Веган"],
                },
                "expected_error": "недоступны флаги",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                response = self._request(
                    "POST",
                    "/api/dishes",
                    case["payload"],
                    expected_status=400,
                )
                self.assertIn(case["expected_error"], response["error"])

    def test_delete_product_returns_conflict_when_dish_depends_on_it(self) -> None:
        """Эквивалентное разбиение: продукт из блюда попадает в конфликтный класс удаления."""
        product = self._create_product(name="Свекла", calories=43, protein=1.6, fat=0.2, carbs=9.6)
        dish = self._create_dish(
            name="Борщ",
            ingredients=[{"product_id": product["id"], "quantity": 150}],
            portion_size=300,
            category="Суп",
            flags=["Веган", "Без глютена", "Без сахара"],
        )

        response = self._request(
            "DELETE",
            f"/api/products/{product['id']}",
            expected_status=409,
        )
        self.assertIn("Нельзя удалить продукт", response["error"])
        self.assertEqual(dish["id"], response["used_by"][0]["id"])

    def test_list_products_filters_by_combined_parameters(self) -> None:
        """Эквивалентное разбиение: комбинированные фильтры оставляют только релевантный класс продуктов."""
        self._create_product(
            name="Картофель",
            calories=77,
            protein=2,
            fat=0.4,
            carbs=16.3,
            category="Овощи",
            cooking_state="Требует приготовления",
        )
        self._create_product(
            name="Молоко",
            calories=52,
            protein=2.8,
            fat=2.5,
            carbs=4.7,
            category="Жидкость",
            cooking_state="Готовый к употреблению",
            flags=["Без глютена", "Без сахара"],
        )
        self._create_product(
            name="Капуста",
            calories=27,
            protein=1.8,
            fat=0.1,
            carbs=4.7,
            category="Овощи",
            cooking_state="Готовый к употреблению",
            flags=["Веган", "Без глютена", "Без сахара"],
        )

        path = "/api/products?" + urlencode(
            [
                ("query", "кап"),
                ("category", "Овощи"),
                ("cooking_state", "Готовый к употреблению"),
                ("flag", "Веган"),
                ("sort_by", "name"),
            ],
            doseq=True,
        )
        products = self._request("GET", path)
        self.assertEqual(1, len(products))
        self.assertEqual("Капуста", products[0]["name"])


if __name__ == "__main__":
    unittest.main()
