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

    def _request_raw(
        self,
        method: str,
        path: str,
        body: str,
        expected_status: int,
        content_type: str = "application/json; charset=utf-8",
    ) -> dict | list | None:
        """Отправляет сырой HTTP body для проверок ошибок парсинга JSON."""
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

    def test_get_meta_returns_all_reference_values(self) -> None:
        """Справочник API возвращает все перечисления для UI и валидации."""
        meta = self._request("GET", "/api/meta")
        self.assertIn("Овощи", meta["product_categories"])
        self.assertIn("Требует приготовления", meta["cooking_states"])
        self.assertIn("Суп", meta["dish_categories"])
        self.assertIn("Веган", meta["flags"])

    def test_list_products_returns_empty_list_for_fresh_store(self) -> None:
        """Пустая база должна отдавать пустой список продуктов."""
        self.assertEqual([], self._request("GET", "/api/products"))

    def test_get_product_returns_not_found_for_unknown_id(self) -> None:
        """Получение продукта по неизвестному id возвращает 404."""
        response = self._request("GET", "/api/products/missing-id", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_update_product_updates_fields_and_sets_updated_at(self) -> None:
        """PUT /api/products/{id} обновляет поля и пишет updated_at."""
        product = self._create_product(name="Морковь", composition="Старая")
        updated = self._request(
            "PUT",
            f"/api/products/{product['id']}",
            {
                "name": "Молодая морковь",
                "photos": ["/pictures/carrot.png"],
                "calories": 42,
                "protein": 1,
                "fat": 0.2,
                "carbs": 9.4,
                "composition": "Новая",
                "category": "Овощи",
                "cooking_state": "Полуфабрикат",
                "flags": ["Веган", "Без глютена"],
            },
        )
        self.assertEqual("Молодая морковь", updated["name"])
        self.assertEqual("Полуфабрикат", updated["cooking_state"])
        self.assertEqual(["Веган", "Без глютена"], updated["flags"])
        self.assertIsNotNone(updated["updated_at"])

    def test_update_product_returns_not_found_for_unknown_id(self) -> None:
        """Обновление отсутствующего продукта должно вернуть 404."""
        response = self._request(
            "PUT",
            "/api/products/missing-id",
            {
                "name": "Призрак",
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
            expected_status=404,
        )
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_returns_not_found_for_unknown_id(self) -> None:
        """Удаление отсутствующего продукта должно вернуть 404."""
        response = self._request("DELETE", "/api/products/missing-id", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_removes_independent_product(self) -> None:
        """Продукт без зависимых блюд удаляется успешно."""
        product = self._create_product(name="Перец")
        self.assertIsNone(
            self._request("DELETE", f"/api/products/{product['id']}", expected_status=204)
        )
        response = self._request("GET", f"/api/products/{product['id']}", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_create_product_accepts_legacy_flag_values(self) -> None:
        """API нормализует legacy-флаги для обратной совместимости."""
        product = self._create_product(flags=["vegan", "gluten_free", "sugar_free"])
        self.assertEqual(["Веган", "Без глютена", "Без сахара"], product["flags"])

    def test_create_product_rejects_unknown_flag(self) -> None:
        """Неизвестный флаг продукта должен приводить к 400."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Соус",
                "photos": [],
                "calories": 40,
                "protein": 1,
                "fat": 1,
                "carbs": 7,
                "composition": "",
                "category": "Жидкость",
                "cooking_state": "Готовый к употреблению",
                "flags": ["Кето"],
            },
            expected_status=400,
        )
        self.assertIn("Неизвестный флаг", response["error"])

    def test_create_product_rejects_non_array_flags(self) -> None:
        """Флаги продукта должны передаваться массивом."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Соус",
                "photos": [],
                "calories": 40,
                "protein": 1,
                "fat": 1,
                "carbs": 7,
                "composition": "",
                "category": "Жидкость",
                "cooking_state": "Готовый к употреблению",
                "flags": "Веган",
            },
            expected_status=400,
        )
        self.assertIn("Флаги должны быть массивом", response["error"])

    def test_create_product_rejects_non_array_photos(self) -> None:
        """Фотографии продукта должны передаваться списком."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Яблоко",
                "photos": "/pictures/apple.png",
                "calories": 52,
                "protein": 0.3,
                "fat": 0.2,
                "carbs": 14,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Фотографии должны быть массивом", response["error"])

    def test_create_product_rejects_non_string_photo_items(self) -> None:
        """Каждая фотография продукта должна быть строкой."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Яблоко",
                "photos": [123],
                "calories": 52,
                "protein": 0.3,
                "fat": 0.2,
                "carbs": 14,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Фотографии должны быть строками", response["error"])

    def test_create_product_rejects_non_numeric_calories(self) -> None:
        """Калорийность продукта должна быть числом."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Яблоко",
                "photos": [],
                "calories": "много",
                "protein": 0.3,
                "fat": 0.2,
                "carbs": 14,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Калорийность должно быть числом", response["error"])

    def test_create_product_rejects_negative_calories(self) -> None:
        """Отрицательная калорийность продукта не допускается."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Яблоко",
                "photos": [],
                "calories": -1,
                "protein": 0.3,
                "fat": 0.2,
                "carbs": 14,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Калорийность не может быть меньше 0", response["error"])

    def test_create_product_rejects_invalid_category(self) -> None:
        """Категория продукта должна быть из разрешённого справочника."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Яблоко",
                "photos": [],
                "calories": 59,
                "protein": 0.3,
                "fat": 0.2,
                "carbs": 14,
                "composition": "",
                "category": "Фрукты",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Категория продукта должно быть одним из", response["error"])

    def test_create_product_rejects_invalid_cooking_state(self) -> None:
        """Состояние готовности продукта должно быть валидным enum."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Яблоко",
                "photos": [],
                "calories": 59,
                "protein": 0.3,
                "fat": 0.2,
                "carbs": 14,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Сырое",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Состояние готовности", response["error"])

    def test_create_product_rejects_macro_sum_over_100(self) -> None:
        """Сумма БЖУ продукта не должна превышать 100 на 100 грамм."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Концентрат",
                "photos": [],
                "calories": 450,
                "protein": 40,
                "fat": 40,
                "carbs": 30,
                "composition": "",
                "category": "Сладости",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Сумма БЖУ не может превышать 100", response["error"])

    def test_create_product_rejects_calorie_inconsistency(self) -> None:
        """Калорийность продукта должна быть согласована с БЖУ."""
        response = self._request(
            "POST",
            "/api/products",
            {
                "name": "Странный продукт",
                "photos": [],
                "calories": 10,
                "protein": 10,
                "fat": 0,
                "carbs": 0,
                "composition": "",
                "category": "Мясной",
                "cooking_state": "Готовый к употреблению",
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Калорийность продукта должна быть согласована", response["error"])

    def test_list_products_sorts_by_requested_numeric_field(self) -> None:
        """Список продуктов поддерживает сортировку по числовому полю."""
        self._create_product(name="Ав", calories=100, protein=10, fat=4, carbs=6)
        self._create_product(name="Бв", calories=50, protein=5, fat=2, carbs=3)
        self._create_product(name="Вг", calories=165, protein=20, fat=5, carbs=10)
        products = self._request("GET", "/api/products?sort_by=calories")
        self.assertEqual(["Бв", "Ав", "Вг"], [item["name"] for item in products])

    def test_list_products_uses_name_sort_for_unknown_sort_field(self) -> None:
        """Неизвестное поле сортировки должно fallback-нуться на имя."""
        self._create_product(name="Брокколи")
        self._create_product(name="Артишок", calories=57, protein=3.3, fat=0.2, carbs=10.5)
        products = self._request("GET", "/api/products?sort_by=unknown")
        self.assertEqual(["Артишок", "Брокколи"], [item["name"] for item in products])

    def test_list_products_filters_by_multiple_flags(self) -> None:
        """Фильтр по нескольким флагам оставляет только полное совпадение подмножества."""
        self._create_product(name="Тофу", category="Мясной", flags=["Веган", "Без глютена", "Без сахара"])
        self._create_product(name="Соевый соус", category="Жидкость", flags=["Веган"])
        products = self._request(
            "GET",
            "/api/products?" + urlencode([("flag", "Веган"), ("flag", "Без глютена")], doseq=True),
        )
        self.assertEqual(["Тофу"], [item["name"] for item in products])

    def test_list_dishes_returns_empty_list_for_fresh_store(self) -> None:
        """Пустая база должна отдавать пустой список блюд."""
        self.assertEqual([], self._request("GET", "/api/dishes"))

    def test_get_dish_returns_not_found_for_unknown_id(self) -> None:
        """Получение блюда по неизвестному id возвращает 404."""
        response = self._request("GET", "/api/dishes/missing-id", expected_status=404)
        self.assertIn("Блюдо не найдено", response["error"])

    def test_create_dish_returns_computed_nutrition_and_flags(self) -> None:
        """Создание блюда возвращает расчётное питание и доступные флаги."""
        carrot = self._create_product(name="Морковь")
        water = self._create_product(
            name="Вода",
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
        )
        dish = self._create_dish(
            name="Суп",
            ingredients=[
                {"product_id": carrot["id"], "quantity": 100},
                {"product_id": water["id"], "quantity": 100},
            ],
            portion_size=200,
        )
        self.assertEqual(41.0, dish["suggested_nutrition"]["calories"])
        self.assertEqual(["Веган", "Без глютена", "Без сахара"], dish["available_flags"])

    def test_create_dish_uses_macro_to_fill_category(self) -> None:
        """Макрос в названии блюда должен подставлять категорию по умолчанию."""
        product = self._create_product()
        dish = self._request(
            "POST",
            "/api/dishes",
            {
                "name": "!суп Тыквенный крем",
                "photos": [],
                "portion_size": 250,
                "ingredients": [{"product_id": product["id"], "quantity": 100}],
                "flags": ["Веган", "Без глютена", "Без сахара"],
            },
            expected_status=201,
        )
        self.assertEqual("Тыквенный крем", dish["name"])
        self.assertEqual("Суп", dish["category"])

    def test_create_dish_accepts_minimum_positive_portion_boundary(self) -> None:
        """Граница 0.01 для размера порции должна оставаться валидной."""
        product = self._create_product()
        dish = self._create_dish(
            portion_size=0.01,
            ingredients=[{"product_id": product["id"], "quantity": 0.01}],
        )
        self.assertEqual(0.01, dish["portion_size"])

    def test_create_dish_rejects_zero_portion_boundary(self) -> None:
        """Размер порции 0 относится к невалидному граничному значению."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            {
                "name": "Нулевая порция",
                "photos": [],
                "portion_size": 0,
                "category": "Суп",
                "ingredients": [{"product_id": product["id"], "quantity": 100}],
                "flags": ["Веган", "Без глютена", "Без сахара"],
            },
            expected_status=400,
        )
        self.assertIn("Размер порции должно быть больше 0", response["error"])

    def test_create_dish_rejects_macros_per_100_over_limit(self) -> None:
        """Блюдо не должно иметь сумму БЖУ выше 100 г на 100 г порции."""
        product = self._create_product(name="Белковый концентрат", calories=400, protein=100, fat=0, carbs=0, flags=[])
        response = self._request(
            "POST",
            "/api/dishes",
            {
                "name": "Слишком плотное блюдо",
                "photos": [],
                "portion_size": 50,
                "category": "Перекус",
                "ingredients": [{"product_id": product["id"], "quantity": 100}],
                "protein": 100,
                "fat": 0,
                "carbs": 0,
                "flags": [],
            },
            expected_status=400,
        )
        self.assertIn("Сумма БЖУ блюда", response["error"])

    def test_create_dish_rejects_invalid_category(self) -> None:
        """Категория блюда должна быть из разрешённого набора."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            {
                "name": "Фруктовая тарелка",
                "photos": [],
                "portion_size": 200,
                "category": "Гарнир",
                "ingredients": [{"product_id": product["id"], "quantity": 100}],
                "flags": ["Веган", "Без глютена", "Без сахара"],
            },
            expected_status=400,
        )
        self.assertIn("Категория блюда должно быть одним из", response["error"])

    def test_create_dish_rejects_non_array_flags(self) -> None:
        """Флаги блюда должны передаваться массивом."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            {
                "name": "Салат",
                "photos": [],
                "portion_size": 200,
                "category": "Салат",
                "ingredients": [{"product_id": product["id"], "quantity": 100}],
                "flags": "Веган",
            },
            expected_status=400,
        )
        self.assertIn("Флаги должны быть массивом", response["error"])

    def test_create_dish_rejects_unknown_flag(self) -> None:
        """Неизвестный флаг блюда должен быть отклонён валидатором."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            {
                "name": "Салат",
                "photos": [],
                "portion_size": 200,
                "category": "Салат",
                "ingredients": [{"product_id": product["id"], "quantity": 100}],
                "flags": ["Кето"],
            },
            expected_status=400,
        )
        self.assertIn("Неизвестный флаг", response["error"])

    def test_update_dish_updates_fields_and_sets_updated_at(self) -> None:
        """PUT /api/dishes/{id} должен обновлять блюдо и метку обновления."""
        product = self._create_product()
        dish = self._create_dish(ingredients=[{"product_id": product["id"], "quantity": 100}])
        updated = self._request(
            "PUT",
            f"/api/dishes/{dish['id']}",
            {
                "name": "Обновлённый суп",
                "photos": ["/pictures/soup.png"],
                "portion_size": 300,
                "category": "Первое",
                "ingredients": [{"product_id": product["id"], "quantity": 150}],
                "flags": ["Веган", "Без глютена", "Без сахара"],
            },
        )
        self.assertEqual("Обновлённый суп", updated["name"])
        self.assertEqual(300.0, updated["portion_size"])
        self.assertEqual("Первое", updated["category"])
        self.assertIsNotNone(updated["updated_at"])

    def test_update_dish_returns_not_found_for_unknown_id(self) -> None:
        """Обновление отсутствующего блюда должно вернуть 404."""
        response = self._request(
            "PUT",
            "/api/dishes/missing-id",
            {
                "name": "Призрачный суп",
                "photos": [],
                "portion_size": 200,
                "category": "Суп",
                "ingredients": [],
                "flags": [],
            },
            expected_status=404,
        )
        self.assertIn("Блюдо не найдено", response["error"])

    def test_delete_dish_removes_entity(self) -> None:
        """Удаление блюда должно делать его недоступным для дальнейшего чтения."""
        dish = self._create_dish()
        self.assertIsNone(self._request("DELETE", f"/api/dishes/{dish['id']}", expected_status=204))
        response = self._request("GET", f"/api/dishes/{dish['id']}", expected_status=404)
        self.assertIn("Блюдо не найдено", response["error"])

    def test_delete_dish_returns_not_found_for_unknown_id(self) -> None:
        """Удаление отсутствующего блюда должно вернуть 404."""
        response = self._request("DELETE", "/api/dishes/missing-id", expected_status=404)
        self.assertIn("Блюдо не найдено", response["error"])

    def test_list_dishes_filters_by_query_category_and_flags(self) -> None:
        """Список блюд поддерживает комбинированную фильтрацию."""
        vegan = self._create_product(name="Огурец", calories=15, protein=0.8, fat=0.1, carbs=2.8)
        meat = self._create_product(name="Курица", calories=168, protein=24, fat=8, carbs=0, category="Мясной", flags=["Без глютена"])
        self._create_dish(
            name="Лёгкий салат",
            category="Салат",
            ingredients=[{"product_id": vegan["id"], "quantity": 100}],
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self._create_dish(
            name="Куриный салат",
            category="Салат",
            ingredients=[{"product_id": meat["id"], "quantity": 100}],
            flags=["Без глютена"],
        )
        dishes = self._request(
            "GET",
            "/api/dishes?"
            + urlencode([("query", "лёг"), ("category", "Салат"), ("flag", "Веган")], doseq=True),
        )
        self.assertEqual(["Лёгкий салат"], [item["name"] for item in dishes])

    def test_list_dishes_is_sorted_by_name(self) -> None:
        """Список блюд сортируется по имени по умолчанию."""
        product = self._create_product()
        self._create_dish(name="Суп", ingredients=[{"product_id": product["id"], "quantity": 100}])
        self._create_dish(name="Борщ", ingredients=[{"product_id": product["id"], "quantity": 100}])
        dishes = self._request("GET", "/api/dishes")
        self.assertEqual(["Борщ", "Суп"], [item["name"] for item in dishes])

    def test_preview_dish_returns_macro_category_without_explicit_category(self) -> None:
        """Preview должен выводить категорию из макроса, если category не передана."""
        product = self._create_product()
        preview = self._request(
            "GET",
            "/api/dishes/preview?"
            + urlencode(
                [("query", "!напиток Морс"), ("ingredient", f"{product['id']}:100")],
                doseq=True,
            ),
        )
        self.assertEqual("Морс", preview["normalized_name"])
        self.assertEqual("Напиток", preview["category_from_macro"])
        self.assertEqual("Напиток", preview["effective_category"])

    def test_preview_dish_rejects_missing_ingredients(self) -> None:
        """Preview блюда требует хотя бы один ингредиент."""
        response = self._request(
            "GET",
            "/api/dishes/preview?" + urlencode({"query": "Пустой суп"}),
            expected_status=400,
        )
        self.assertIn("хотя бы один ингредиент", response["error"])

    def test_preview_dish_rejects_unknown_product(self) -> None:
        """Preview блюда отвергает несуществующий product_id."""
        response = self._request(
            "GET",
            "/api/dishes/preview?"
            + urlencode([("query", "Суп"), ("ingredient", "missing-id:100")], doseq=True),
            expected_status=400,
        )
        self.assertIn("несуществующий продукт", response["error"])

    def test_update_product_syncs_dish_flags_after_flag_loss(self) -> None:
        """При обновлении продукта API должно синхронизировать недоступные флаги блюда."""
        product = self._create_product(name="Тыква", flags=["Веган", "Без глютена", "Без сахара"])
        dish = self._create_dish(
            name="Тыквенный суп",
            ingredients=[{"product_id": product["id"], "quantity": 100}],
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self._request(
            "PUT",
            f"/api/products/{product['id']}",
            {
                "name": "Тыква",
                "photos": [],
                "calories": 41,
                "protein": 0.9,
                "fat": 0.2,
                "carbs": 9.6,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": ["Без глютена"],
            },
        )
        reloaded = self._request("GET", f"/api/dishes/{dish['id']}")
        self.assertEqual(["Без глютена"], reloaded["flags"])
        self.assertEqual(["Без глютена"], reloaded["available_flags"])

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
        """POST /api/products принимает только JSON object."""
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

    def test_unknown_api_route_returns_not_found_json(self) -> None:
        """Неизвестный API route должен возвращать JSON-ошибку 404."""
        response = self._request("POST", "/api/unknown", payload={}, expected_status=404)
        self.assertEqual("Маршрут не найден.", response["error"])


if __name__ == "__main__":
    unittest.main()
