"""Интеграционные тесты product API."""

from __future__ import annotations

from urllib.parse import urlencode

from tests.integration.live_api_test_case import LiveApiTestCase
from tests.integration.payloads import build_product_payload


class ProductsApiTest(LiveApiTestCase):
    """Проверяет CRUD, фильтрацию, сортировку и валидацию продуктов."""

    def test_create_product_supports_valid_equivalence_classes(self) -> None:
        """Эквивалентное разбиение: API принимает продукты из разных валидных классов."""
        cases = [
            build_product_payload(
                name=self.make_test_name("вода"),
                calories=0,
                protein=0,
                fat=0,
                carbs=0,
                composition="",
                category="Жидкость",
                flags=["Веган", "Без глютена", "Без сахара"],
            ),
            build_product_payload(
                name=self.make_test_name("индейка"),
                calories=110,
                protein=23,
                fat=1,
                carbs=1,
                composition="Индейка",
                category="Мясной",
                cooking_state="Требует приготовления",
                flags=["Без глютена", "Без сахара"],
            ),
        ]

        for payload in cases:
            with self.subTest(name=payload["name"]):
                created = self._request("POST", "/api/products", payload, expected_status=201)
                fetched = self._request("GET", f"/api/products/{created['id']}")
                self.assertEqual(payload["name"], fetched["name"])
                self.assertEqual(payload["category"], fetched["category"])
                self.assertEqual(payload["flags"], fetched["flags"])

    def test_create_product_enforces_name_boundaries(self) -> None:
        """Анализ граничных значений: имя длиной 2 валидно, длиной 1 невалидно."""
        cases = [
            {"name": self.make_test_name("ай"), "expected_status": 201},
            {"name": "A", "expected_status": 400},
        ]

        for case in cases:
            with self.subTest(name=case["name"]):
                response = self._request(
                    "POST",
                    "/api/products",
                    build_product_payload(
                        name=case["name"],
                        calories=0,
                        protein=0,
                        fat=0,
                        carbs=0,
                        composition="",
                        category="Жидкость",
                        flags=[],
                    ),
                    expected_status=case["expected_status"],
                )
                if case["expected_status"] == 400:
                    self.assertIn("минимум 2 символа", response["error"])

    def test_create_product_enforces_photo_count_boundary(self) -> None:
        """Анализ граничных значений: 5 фотографий допустимы, 6 уже нет."""
        valid_photos = [f"/pictures/{index}.png" for index in range(5)]
        invalid_photos = [f"/pictures/{index}.png" for index in range(6)]

        created = self._create_product(name=self.make_test_name("тыква"), photos=valid_photos)
        self.assertEqual(5, len(created["photos"]))

        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("тыква extra"),
                photos=invalid_photos,
                calories=26,
                protein=1,
                fat=0.1,
                carbs=6.5,
                composition="",
                flags=["Веган"],
            ),
            expected_status=400,
        )
        self.assertIn("не более 5 фотографий", response["error"])

    def test_create_product_enforces_macro_boundary(self) -> None:
        """Анализ граничных значений: БЖУ 100 допустимо, значение выше 100 не допускается."""
        cases = [
            {"protein": 100, "expected_status": 201},
            {"protein": 100.01, "expected_status": 400},
        ]

        for case in cases:
            with self.subTest(protein=case["protein"]):
                response = self._request(
                    "POST",
                    "/api/products",
                    build_product_payload(
                        name=self.make_test_name(f"белок-{case['protein']}"),
                        calories=400.04,
                        protein=case["protein"],
                        fat=0,
                        carbs=0,
                        composition="",
                        category="Мясной",
                        flags=[],
                    ),
                    expected_status=case["expected_status"],
                )
                if case["expected_status"] == 400:
                    self.assertIn("не может превышать 100", response["error"])

    def test_get_product_returns_not_found_for_unknown_id(self) -> None:
        """Получение продукта по неизвестному id возвращает 404."""
        response = self._request("GET", "/api/products/missing-id", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_update_product_updates_fields_and_sets_updated_at(self) -> None:
        """PUT /api/products/{id} должен обновлять поля продукта и updated_at."""
        product = self._create_product(name=self.make_test_name("морковь"))
        updated = self._request(
            "PUT",
            f"/api/products/{product['id']}",
            build_product_payload(
                name=self.make_test_name("молодая морковь"),
                photos=["/pictures/carrot.png"],
                calories=42,
                protein=1,
                fat=0.2,
                carbs=9.4,
                composition="Новая",
                cooking_state="Полуфабрикат",
                flags=["Веган", "Без глютена"],
            ),
        )
        self.assertEqual(self.make_test_name("молодая морковь"), updated["name"])
        self.assertEqual("Полуфабрикат", updated["cooking_state"])
        self.assertEqual(["Веган", "Без глютена"], updated["flags"])
        self.assertIsNotNone(updated["updated_at"])

    def test_update_product_returns_not_found_for_unknown_id(self) -> None:
        """Обновление отсутствующего продукта должно вернуть 404."""
        response = self._request(
            "PUT",
            "/api/products/missing-id",
            build_product_payload(
                name=self.make_test_name("призрак"),
                calories=0,
                protein=0,
                fat=0,
                carbs=0,
                composition="",
                category="Жидкость",
                flags=[],
            ),
            expected_status=404,
        )
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_removes_independent_product(self) -> None:
        """Продукт без зависимых блюд удаляется успешно."""
        product = self._create_product(name=self.make_test_name("перец"))
        self.assertIsNone(
            self._request("DELETE", f"/api/products/{product['id']}", expected_status=204)
        )
        response = self._request("GET", f"/api/products/{product['id']}", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_returns_not_found_for_unknown_id(self) -> None:
        """Удаление отсутствующего продукта должно вернуть 404."""
        response = self._request("DELETE", "/api/products/missing-id", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_returns_conflict_when_dish_depends_on_it(self) -> None:
        """Эквивалентное разбиение: используемый в блюде продукт образует конфликтный класс удаления."""
        product = self._create_product(
            name=self.make_test_name("свекла"),
            calories=43,
            protein=1.6,
            fat=0.2,
            carbs=9.6,
        )
        dish = self._create_dish(
            name=self.make_test_name("борщ"),
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

    def test_create_product_accepts_legacy_flag_values(self) -> None:
        """API должно нормализовать legacy-значения флагов для обратной совместимости."""
        product = self._create_product(
            name=self.make_test_name("legacy"),
            flags=["vegan", "gluten_free", "sugar_free"],
        )
        self.assertEqual(["Веган", "Без глютена", "Без сахара"], product["flags"])

    def test_create_product_rejects_unknown_flag(self) -> None:
        """Неизвестный флаг продукта должен приводить к 400."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("соус"),
                calories=40,
                protein=1,
                fat=1,
                carbs=7,
                composition="",
                category="Жидкость",
                flags=["Кето"],
            ),
            expected_status=400,
        )
        self.assertIn("Неизвестный флаг", response["error"])

    def test_create_product_rejects_non_array_flags(self) -> None:
        """Флаги продукта должны передаваться массивом."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("соус"),
                calories=40,
                protein=1,
                fat=1,
                carbs=7,
                composition="",
                category="Жидкость",
                flags="Веган",
            ),
            expected_status=400,
        )
        self.assertIn("Флаги должны быть массивом", response["error"])

    def test_create_product_rejects_non_array_photos(self) -> None:
        """Фотографии продукта должны передаваться списком."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("яблоко"),
                photos="/pictures/apple.png",
                calories=59,
                protein=0.3,
                fat=0.2,
                carbs=14,
                composition="",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Фотографии должны быть массивом", response["error"])

    def test_create_product_rejects_non_string_photo_items(self) -> None:
        """Каждая фотография продукта должна быть строкой."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("яблоко"),
                photos=[123],
                calories=59,
                protein=0.3,
                fat=0.2,
                carbs=14,
                composition="",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Фотографии должны быть строками", response["error"])

    def test_create_product_rejects_non_numeric_calories(self) -> None:
        """Калорийность продукта должна быть числом."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("яблоко"),
                calories="много",
                protein=0.3,
                fat=0.2,
                carbs=14,
                composition="",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Калорийность должно быть числом", response["error"])

    def test_create_product_rejects_negative_calories(self) -> None:
        """Отрицательная калорийность продукта не допускается."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("яблоко"),
                calories=-1,
                protein=0.3,
                fat=0.2,
                carbs=14,
                composition="",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Калорийность не может быть меньше 0", response["error"])

    def test_create_product_rejects_invalid_category(self) -> None:
        """Категория продукта должна быть из разрешённого справочника."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("яблоко"),
                calories=59,
                protein=0.3,
                fat=0.2,
                carbs=14,
                composition="",
                category="Фрукты",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Категория продукта", response["error"])

    def test_create_product_rejects_invalid_cooking_state(self) -> None:
        """Состояние готовности продукта должно быть валидным enum."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("яблоко"),
                calories=59,
                protein=0.3,
                fat=0.2,
                carbs=14,
                composition="",
                cooking_state="Сырое",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Состояние готовности", response["error"])

    def test_create_product_rejects_macro_sum_over_100(self) -> None:
        """Сумма БЖУ продукта не должна превышать 100 на 100 грамм."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("концентрат"),
                calories=450,
                protein=40,
                fat=40,
                carbs=30,
                composition="",
                category="Сладости",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Сумма БЖУ не может превышать 100", response["error"])

    def test_create_product_rejects_calorie_inconsistency(self) -> None:
        """Калорийность продукта должна быть согласована с БЖУ."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("странный продукт"),
                calories=10,
                protein=10,
                fat=0,
                carbs=0,
                composition="",
                category="Мясной",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Калорийность продукта должна быть согласована", response["error"])

    def test_list_products_filters_by_combined_parameters(self) -> None:
        """Эквивалентное разбиение: комбинированные фильтры выделяют нужный класс продуктов."""
        self._create_product(
            name=self.make_test_name("картофель"),
            calories=77,
            protein=2,
            fat=0.4,
            carbs=16.3,
            category="Овощи",
            cooking_state="Требует приготовления",
        )
        self._create_product(
            name=self.make_test_name("молоко"),
            calories=52,
            protein=2.8,
            fat=2.5,
            carbs=4.7,
            category="Жидкость",
            flags=["Без глютена", "Без сахара"],
        )
        self._create_product(
            name=self.make_test_name("капуста"),
            calories=27,
            protein=1.8,
            fat=0.1,
            carbs=4.7,
            category="Овощи",
            flags=["Веган", "Без глютена", "Без сахара"],
        )

        path = "/api/products?" + urlencode(
            [
                ("query", self._test_query("кап")),
                ("category", "Овощи"),
                ("cooking_state", "Готовый к употреблению"),
                ("flag", "Веган"),
                ("sort_by", "name"),
            ],
            doseq=True,
        )
        products = self._request("GET", path)
        self.assertEqual(1, len(products))
        self.assertEqual(self.make_test_name("капуста"), products[0]["name"])

    def test_list_products_sorts_by_requested_numeric_field(self) -> None:
        """Список продуктов должен сортироваться по числовому полю."""
        self._create_product(name=self.make_test_name("ав"), calories=100, protein=10, fat=4, carbs=6)
        self._create_product(name=self.make_test_name("бв"), calories=50, protein=5, fat=2, carbs=3)
        self._create_product(name=self.make_test_name("вг"), calories=165, protein=20, fat=5, carbs=10)
        products = self._request(
            "GET",
            "/api/products?" + urlencode({"query": self.test_prefix, "sort_by": "calories"}),
        )
        self.assertEqual(
            [self.make_test_name("бв"), self.make_test_name("ав"), self.make_test_name("вг")],
            [item["name"] for item in products if item["name"].startswith(self.test_prefix)],
        )

    def test_list_products_uses_name_sort_for_unknown_sort_field(self) -> None:
        """Неизвестное поле сортировки должно давать fallback на сортировку по имени."""
        self._create_product(name=self.make_test_name("брокколи"))
        self._create_product(
            name=self.make_test_name("артишок"),
            calories=57,
            protein=3.3,
            fat=0.2,
            carbs=10.5,
        )
        products = self._request(
            "GET",
            "/api/products?" + urlencode({"query": self.test_prefix, "sort_by": "unknown"}),
        )
        self.assertEqual(
            [self.make_test_name("артишок"), self.make_test_name("брокколи")],
            [item["name"] for item in products if item["name"].startswith(self.test_prefix)],
        )

    def test_list_products_filters_by_multiple_flags(self) -> None:
        """Фильтр по нескольким флагам должен оставлять только полное совпадение подмножества."""
        self._create_product(
            name=self.make_test_name("тофу"),
            category="Мясной",
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self._create_product(
            name=self.make_test_name("соевый соус"),
            category="Жидкость",
            flags=["Веган"],
        )
        products = self._request(
            "GET",
            "/api/products?"
            + urlencode(
                [("query", self.test_prefix), ("flag", "Веган"), ("flag", "Без глютена")],
                doseq=True,
            ),
        )
        self.assertEqual([self.make_test_name("тофу")], [item["name"] for item in products])

    def test_update_product_syncs_dish_flags_after_flag_loss(self) -> None:
        """Изменение флагов продукта должно синхронизировать недоступные флаги блюда."""
        product = self._create_product(
            name=self.make_test_name("тыква"),
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        dish = self._create_dish(
            name=self.make_test_name("тыквенный суп"),
            ingredients=[{"product_id": product["id"], "quantity": 100}],
            flags=["Веган", "Без глютена", "Без сахара"],
        )

        self._request(
            "PUT",
            f"/api/products/{product['id']}",
            build_product_payload(
                name=self.make_test_name("тыква"),
                flags=["Без глютена"],
            ),
        )

        reloaded = self._request("GET", f"/api/dishes/{dish['id']}")
        self.assertEqual(["Без глютена"], reloaded["flags"])
        self.assertEqual(["Без глютена"], reloaded["available_flags"])
