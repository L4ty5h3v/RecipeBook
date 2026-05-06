"""Интеграционные тесты dish API."""

from __future__ import annotations

from urllib.parse import urlencode

from tests.integration.live_api_test_case import LiveApiTestCase
from tests.integration.payloads import build_dish_payload


class DishesApiTest(LiveApiTestCase):
    """Проверяет CRUD, фильтрацию, расчёты и валидацию блюд."""

    def _create_sample_dish(self) -> dict:
        """Создаёт базовое тестовое блюдо для последующих проверок."""
        product = self._create_product()
        return self._create_dish(
            name=self.make_test_name("суп"),
            ingredients=[{"product_id": product["id"], "quantity": 100}],
        )

    def _update_sample_dish(self) -> dict:
        """Обновляет тестовое блюдо и возвращает ответ API."""
        product = self._create_product()
        dish = self._create_dish(
            name=self.make_test_name("суп"),
            ingredients=[{"product_id": product["id"], "quantity": 100}],
        )
        return self._request(
            "PUT",
            f"/api/dishes/{dish['id']}",
            build_dish_payload(
                name=self.make_test_name("обновлённый суп"),
                ingredients=[{"product_id": product["id"], "quantity": 150}],
                photos=["/pictures/soup.png"],
                portion_size=300,
                category="Первое",
            ),
        )

    def _create_macro_dish(self) -> dict:
        """Создаёт блюдо с макросом категории в названии."""
        product = self._create_product()
        return self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=f"!суп {self.make_test_name('тыквенный крем')}",
                ingredients=[{"product_id": product["id"], "quantity": 100}],
            ),
            expected_status=201,
        )

    def test_get_dish_returns_not_found_for_unknown_id(self) -> None:
        """Получение блюда по неизвестному id возвращает 404."""
        response = self._request("GET", "/api/dishes/missing-id", expected_status=404)
        self.assertIn("Блюдо не найдено", response["error"])

    def test_create_dish_returns_computed_nutrition(self) -> None:
        """Создание блюда должно возвращать расчётную пищевую ценность."""
        carrot = self._create_product(name=self.make_test_name("морковь"))
        water = self._create_product(
            name=self.make_test_name("вода"),
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
        )
        dish = self._create_dish(
            name=self.make_test_name("суп"),
            ingredients=[
                {"product_id": carrot["id"], "quantity": 100},
                {"product_id": water["id"], "quantity": 100},
            ],
            portion_size=200,
        )
        self.assertEqual(41.0, dish["suggested_nutrition"]["calories"])

    def test_create_dish_returns_available_flags(self) -> None:
        """Создание блюда должно возвращать список доступных флагов."""
        carrot = self._create_product(name=self.make_test_name("морковь"))
        water = self._create_product(
            name=self.make_test_name("вода"),
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            composition="",
            category="Жидкость",
        )
        dish = self._create_dish(
            name=self.make_test_name("суп"),
            ingredients=[
                {"product_id": carrot["id"], "quantity": 100},
                {"product_id": water["id"], "quantity": 100},
            ],
            portion_size=200,
        )
        self.assertEqual(["Веган", "Без глютена", "Без сахара"], dish["available_flags"])

    def test_create_dish_rejects_empty_ingredients(self) -> None:
        """Эквивалентное разбиение: пустой состав относится к невалидному классу."""
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("пустое блюдо"),
                ingredients=[],
                portion_size=200,
                category="Суп",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("хотя бы один ингредиент", response["error"])

    def test_create_dish_rejects_missing_product_in_ingredients(self) -> None:
        """Эквивалентное разбиение: несуществующий продукт относится к невалидному классу."""
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("секретное блюдо"),
                ingredients=[{"product_id": "missing-id", "quantity": 100}],
                portion_size=200,
                category="Суп",
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("несуществующий продукт", response["error"])

    def test_create_dish_rejects_unavailable_flag(self) -> None:
        """Эквивалентное разбиение: недоступный флаг относится к невалидному классу."""
        product = self._create_product(
            name=self.make_test_name("курица"),
            calories=168,
            protein=24,
            fat=8,
            carbs=0,
            category="Мясной",
            flags=["Без глютена"],
        )
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("куриный суп"),
                ingredients=[{"product_id": product["id"], "quantity": 100}],
                portion_size=200,
                category="Суп",
                flags=["Веган"],
            ),
            expected_status=400,
        )
        self.assertIn("недоступны флаги", response["error"])

    def test_create_dish_normalizes_name_from_macro(self) -> None:
        """Макрос в названии должен очищаться в сохранённом имени блюда."""
        dish = self._create_macro_dish()
        self.assertEqual(self.make_test_name("тыквенный крем"), dish["name"])

    def test_create_dish_uses_category_from_macro(self) -> None:
        """Макрос в названии должен подставлять категорию блюда."""
        dish = self._create_macro_dish()
        self.assertEqual("Суп", dish["category"])

    def test_create_dish_accepts_minimum_positive_portion_boundary(self) -> None:
        """Анализ граничных значений: порция 0.01 должна оставаться валидной."""
        product = self._create_product()
        dish = self._create_dish(
            name=self.make_test_name("микро порция"),
            portion_size=0.01,
            ingredients=[{"product_id": product["id"], "quantity": 0.01}],
        )
        self.assertEqual(0.01, dish["portion_size"])

    def test_create_dish_rejects_zero_portion_boundary(self) -> None:
        """Анализ граничных значений: размер порции 0 относится к невалидному классу."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("нулевая порция"),
                ingredients=[{"product_id": product["id"], "quantity": 100}],
                portion_size=0,
                category="Суп",
            ),
            expected_status=400,
        )
        self.assertIn("Размер порции должно быть больше 0", response["error"])

    def test_create_dish_rejects_macros_per_100_over_limit(self) -> None:
        """Блюдо не должно иметь сумму БЖУ выше 100 г на 100 г порции."""
        product = self._create_product(
            name=self.make_test_name("белковый концентрат"),
            calories=400,
            protein=100,
            fat=0,
            carbs=0,
            flags=[],
        )
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("слишком плотное блюдо"),
                ingredients=[{"product_id": product["id"], "quantity": 100}],
                portion_size=50,
                category="Перекус",
                protein=100,
                fat=0,
                carbs=0,
                flags=[],
            ),
            expected_status=400,
        )
        self.assertIn("Сумма БЖУ блюда", response["error"])

    def test_create_dish_rejects_invalid_category(self) -> None:
        """Категория блюда должна быть из разрешённого набора."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("фруктовая тарелка"),
                ingredients=[{"product_id": product["id"], "quantity": 100}],
                portion_size=200,
                category="Гарнир",
            ),
            expected_status=400,
        )
        self.assertIn("Категория блюда", response["error"])

    def test_create_dish_rejects_non_array_flags(self) -> None:
        """Флаги блюда должны передаваться массивом."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("салат"),
                ingredients=[{"product_id": product["id"], "quantity": 100}],
                category="Салат",
                flags="Веган",
            ),
            expected_status=400,
        )
        self.assertIn("Флаги должны быть массивом", response["error"])

    def test_create_dish_rejects_unknown_flag(self) -> None:
        """Неизвестный флаг блюда должен быть отклонён валидатором."""
        product = self._create_product()
        response = self._request(
            "POST",
            "/api/dishes",
            build_dish_payload(
                name=self.make_test_name("салат"),
                ingredients=[{"product_id": product["id"], "quantity": 100}],
                category="Салат",
                flags=["Кето"],
            ),
            expected_status=400,
        )
        self.assertIn("Неизвестный флаг", response["error"])

    def test_update_dish_changes_name(self) -> None:
        """Обновление блюда должно менять имя."""
        updated = self._update_sample_dish()
        self.assertEqual(self.make_test_name("обновлённый суп"), updated["name"])

    def test_update_dish_changes_portion_size(self) -> None:
        """Обновление блюда должно менять размер порции."""
        updated = self._update_sample_dish()
        self.assertEqual(300.0, updated["portion_size"])

    def test_update_dish_changes_category(self) -> None:
        """Обновление блюда должно менять категорию."""
        updated = self._update_sample_dish()
        self.assertEqual("Первое", updated["category"])

    def test_update_dish_sets_updated_at(self) -> None:
        """Обновление блюда должно проставлять updated_at."""
        updated = self._update_sample_dish()
        self.assertIsNotNone(updated["updated_at"])

    def test_update_dish_returns_not_found_for_unknown_id(self) -> None:
        """Обновление отсутствующего блюда должно вернуть 404."""
        response = self._request(
            "PUT",
            "/api/dishes/missing-id",
            build_dish_payload(
                name=self.make_test_name("призрачный суп"),
                ingredients=[],
                portion_size=200,
                category="Суп",
                flags=[],
            ),
            expected_status=404,
        )
        self.assertIn("Блюдо не найдено", response["error"])

    def test_delete_dish_makes_entity_unavailable(self) -> None:
        """Удаление блюда должно делать его недоступным для последующего чтения."""
        dish = self._create_dish(name=self.make_test_name("удаляемый суп"))
        self._request("DELETE", f"/api/dishes/{dish['id']}", expected_status=204)
        response = self._request("GET", f"/api/dishes/{dish['id']}", expected_status=404)
        self.assertIn("Блюдо не найдено", response["error"])

    def test_delete_dish_returns_not_found_for_unknown_id(self) -> None:
        """Удаление отсутствующего блюда должно вернуть 404."""
        response = self._request("DELETE", "/api/dishes/missing-id", expected_status=404)
        self.assertIn("Блюдо не найдено", response["error"])

    def test_list_dishes_filters_by_query_category_and_flags(self) -> None:
        """Эквивалентное разбиение: комбинированные фильтры должны выделять нужный класс блюд."""
        vegan = self._create_product(
            name=self.make_test_name("огурец"),
            calories=15,
            protein=0.8,
            fat=0.1,
            carbs=2.8,
        )
        meat = self._create_product(
            name=self.make_test_name("курица"),
            calories=168,
            protein=24,
            fat=8,
            carbs=0,
            category="Мясной",
            flags=["Без глютена"],
        )
        self._create_dish(
            name=self.make_test_name("лёгкий салат"),
            category="Салат",
            ingredients=[{"product_id": vegan["id"], "quantity": 100}],
            flags=["Веган", "Без глютена", "Без сахара"],
        )
        self._create_dish(
            name=self.make_test_name("куриный салат"),
            category="Салат",
            ingredients=[{"product_id": meat["id"], "quantity": 100}],
            flags=["Без глютена"],
        )

        dishes = self._request(
            "GET",
            "/api/dishes?"
            + urlencode(
                [("query", self._test_query("лёг")), ("category", "Салат"), ("flag", "Веган")],
                doseq=True,
            ),
        )
        self.assertEqual([self.make_test_name("лёгкий салат")], [item["name"] for item in dishes])

    def test_list_dishes_is_sorted_by_name(self) -> None:
        """Список блюд должен сортироваться по имени по умолчанию."""
        product = self._create_product()
        self._create_dish(
            name=self.make_test_name("суп"),
            ingredients=[{"product_id": product["id"], "quantity": 100}],
        )
        self._create_dish(
            name=self.make_test_name("борщ"),
            ingredients=[{"product_id": product["id"], "quantity": 100}],
        )
        dishes = self._request(
            "GET",
            "/api/dishes?" + urlencode({"query": self.test_prefix}),
        )
        self.assertEqual(
            [self.make_test_name("борщ"), self.make_test_name("суп")],
            [item["name"] for item in dishes if item["name"].startswith(self.test_prefix)],
        )
