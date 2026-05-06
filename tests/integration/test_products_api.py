"""Интеграционные тесты product API."""

from __future__ import annotations

from urllib.parse import urlencode

from tests.integration.live_api_test_case import LiveApiTestCase
from tests.integration.payloads import build_product_payload


class ProductsApiTest(LiveApiTestCase):
    """Проверяет CRUD, фильтрацию, сортировку и валидацию продуктов."""

    def _create_and_fetch_product(self, **payload_overrides: object) -> dict:
        """Создаёт продукт и перечитывает его через GET /api/products/{id}."""
        created = self._request(
            "POST",
            "/api/products",
            build_product_payload(**payload_overrides),
            expected_status=201,
        )
        return self._request("GET", f"/api/products/{created['id']}")

    def _update_sample_product(self) -> dict:
        """Обновляет тестовый продукт и возвращает ответ API."""
        product = self._create_product(name=self.make_test_name("морковь"))
        return self._request(
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

    def _delete_conflicted_product(self) -> dict:
        """Пытается удалить продукт, используемый в блюде, и возвращает ответ конфликта."""
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
        response["expected_dish_id"] = dish["id"]
        return response

    def _list_filtered_products(self) -> list[dict]:
        """Готовит тестовые продукты и возвращает результат комбинированной фильтрации."""
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
        return self._request("GET", path)

    def _reloaded_dish_after_product_flag_change(self) -> dict:
        """Возвращает блюдо после пересинхронизации флагов продукта."""
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
        return self._request("GET", f"/api/dishes/{dish['id']}")

    def test_create_water_product_keeps_name(self) -> None:
        """Эквивалентное разбиение: продукт класса 'жидкость' сохраняет имя."""
        product = self._create_and_fetch_product(
            name=self.make_test_name("вода"),
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self.assertEqual(self.make_test_name("вода"), product["name"])

    def test_create_water_product_keeps_category(self) -> None:
        """Эквивалентное разбиение: продукт класса 'жидкость' сохраняет категорию."""
        product = self._create_and_fetch_product(
            name=self.make_test_name("вода"),
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self.assertEqual("Жидкость", product["category"])

    def test_create_water_product_keeps_flags(self) -> None:
        """Эквивалентное разбиение: продукт класса 'жидкость' сохраняет флаги."""
        product = self._create_and_fetch_product(
            name=self.make_test_name("вода"),
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self.assertEqual(["Веган", "Без глютена", "Без сахара"], product["flags"])

    def test_create_turkey_product_keeps_name(self) -> None:
        """Эквивалентное разбиение: мясной продукт сохраняет имя."""
        product = self._create_and_fetch_product(
            name=self.make_test_name("индейка"),
            calories=110,
            protein=23,
            fat=1,
            carbs=1,
            composition="Индейка",
            category="Мясной",
            cooking_state="Требует приготовления",
            flags=["Без глютена", "Без сахара"],
        )
        self.assertEqual(self.make_test_name("индейка"), product["name"])

    def test_create_turkey_product_keeps_category(self) -> None:
        """Эквивалентное разбиение: мясной продукт сохраняет категорию."""
        product = self._create_and_fetch_product(
            name=self.make_test_name("индейка"),
            calories=110,
            protein=23,
            fat=1,
            carbs=1,
            composition="Индейка",
            category="Мясной",
            cooking_state="Требует приготовления",
            flags=["Без глютена", "Без сахара"],
        )
        self.assertEqual("Мясной", product["category"])

    def test_create_turkey_product_keeps_flags(self) -> None:
        """Эквивалентное разбиение: мясной продукт сохраняет флаги."""
        product = self._create_and_fetch_product(
            name=self.make_test_name("индейка"),
            calories=110,
            protein=23,
            fat=1,
            carbs=1,
            composition="Индейка",
            category="Мясной",
            cooking_state="Требует приготовления",
            flags=["Без глютена", "Без сахара"],
        )
        self.assertEqual(["Без глютена", "Без сахара"], product["flags"])

    def test_create_product_accepts_name_at_min_boundary(self) -> None:
        """Анализ граничных значений: имя длиной 2 символа валидно."""
        product = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("ай"),
                calories=0,
                protein=0,
                fat=0,
                carbs=0,
                composition="",
                category="Жидкость",
                flags=[],
            ),
            expected_status=201,
        )
        self.assertEqual(self.make_test_name("ай"), product["name"])

    def test_create_product_rejects_name_below_min_boundary(self) -> None:
        """Анализ граничных значений: имя длиной 1 символ невалидно."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name="A",
                calories=0,
                protein=0,
                fat=0,
                carbs=0,
                composition="",
                category="Жидкость",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("минимум 2 символа", response["error"])

    def test_create_product_accepts_five_photos(self) -> None:
        """Анализ граничных значений: пять фотографий должны быть допустимы."""
        valid_photos = [f"/pictures/{index}.png" for index in range(5)]
        created = self._create_product(name=self.make_test_name("тыква"), photos=valid_photos)
        self.assertEqual(5, len(created["photos"]))

    def test_create_product_rejects_six_photos(self) -> None:
        """Анализ граничных значений: шесть фотографий должны быть отклонены."""
        invalid_photos = [f"/pictures/{index}.png" for index in range(6)]
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

    def test_create_product_accepts_macro_value_at_max_boundary(self) -> None:
        """Анализ граничных значений: значение БЖУ 100 должно быть допустимо."""
        product = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("белок-100"),
                calories=400.04,
                protein=100,
                fat=0,
                carbs=0,
                composition="",
                category="Мясной",
                flags=[],
            ),
            expected_status=201,
        )
        self.assertEqual(100.0, product["protein"])

    def test_create_product_rejects_macro_value_above_max_boundary(self) -> None:
        """Анализ граничных значений: значение БЖУ выше 100 должно быть отклонено."""
        response = self._request(
            "POST",
            "/api/products",
            build_product_payload(
                name=self.make_test_name("белок-100.01"),
                calories=400.04,
                protein=100.01,
                fat=0,
                carbs=0,
                composition="",
                category="Мясной",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("не может превышать 100", response["error"])

    def test_get_product_returns_not_found_for_unknown_id(self) -> None:
        """Получение продукта по неизвестному id возвращает 404."""
        response = self._request("GET", "/api/products/missing-id", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_update_product_changes_name(self) -> None:
        """Обновление продукта должно менять имя."""
        updated = self._update_sample_product()
        self.assertEqual(self.make_test_name("молодая морковь"), updated["name"])

    def test_update_product_changes_cooking_state(self) -> None:
        """Обновление продукта должно менять состояние готовности."""
        updated = self._update_sample_product()
        self.assertEqual("Полуфабрикат", updated["cooking_state"])

    def test_update_product_changes_flags(self) -> None:
        """Обновление продукта должно менять набор флагов."""
        updated = self._update_sample_product()
        self.assertEqual(["Веган", "Без глютена"], updated["flags"])

    def test_update_product_sets_updated_at(self) -> None:
        """Обновление продукта должно проставлять updated_at."""
        updated = self._update_sample_product()
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

    def test_delete_product_makes_entity_unavailable(self) -> None:
        """Продукт без зависимых блюд после удаления должен стать недоступным."""
        product = self._create_product(name=self.make_test_name("перец"))
        self._request("DELETE", f"/api/products/{product['id']}", expected_status=204)
        response = self._request("GET", f"/api/products/{product['id']}", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_returns_not_found_for_unknown_id(self) -> None:
        """Удаление отсутствующего продукта должно вернуть 404."""
        response = self._request("DELETE", "/api/products/missing-id", expected_status=404)
        self.assertIn("Продукт не найден", response["error"])

    def test_delete_product_conflict_contains_error_message(self) -> None:
        """Удаление зависимого продукта должно возвращать сообщение о конфликте."""
        response = self._delete_conflicted_product()
        self.assertIn("Нельзя удалить продукт", response["error"])

    def test_delete_product_conflict_contains_dependent_dish_reference(self) -> None:
        """Удаление зависимого продукта должно возвращать ссылку на блокирующее блюдо."""
        response = self._delete_conflicted_product()
        self.assertEqual(response["expected_dish_id"], response["used_by"][0]["id"])

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

    def test_list_products_combined_filter_returns_single_result(self) -> None:
        """Эквивалентное разбиение: комбинированный фильтр должен сужать выборку до одного продукта."""
        products = self._list_filtered_products()
        self.assertEqual(1, len(products))

    def test_list_products_combined_filter_returns_expected_product(self) -> None:
        """Эквивалентное разбиение: комбинированный фильтр должен возвращать нужный продукт."""
        products = self._list_filtered_products()
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

    def test_update_product_syncs_dish_flags(self) -> None:
        """Изменение флагов продукта должно обновлять флаги блюда."""
        reloaded = self._reloaded_dish_after_product_flag_change()
        self.assertEqual(["Без глютена"], reloaded["flags"])

    def test_update_product_syncs_available_flags(self) -> None:
        """Изменение флагов продукта должно обновлять доступные флаги блюда."""
        reloaded = self._reloaded_dish_after_product_flag_change()
        self.assertEqual(["Без глютена"], reloaded["available_flags"])
