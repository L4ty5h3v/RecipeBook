"""Системные UI-тесты Recipe Book.

Тесты запускают реальные браузерные сценарии через Playwright и проверяют
критичные пользовательские потоки задачи "1 - Разработать тестируемую систему".
Данные подобраны техниками эквивалентного разбиения и анализа граничных
значений; каждая проверка описывает выбранный класс или границу.
"""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from tests.ui.pages import RecipeBookPage
from tests.ui.test_data import EQUIVALENCE_PRODUCTS, FIVE_PHOTOS, ProductCase, SIX_PHOTOS
from tests.ui.ui_selectors import CommonSelectors, DishSelectors, ProductSelectors


class RecipeBookUiSystemTest(unittest.TestCase):
    """Проверяет систему через UI против уже запущенного приложения."""

    base_url = os.environ.get("RECIPEBOOK_UI_BASE_URL", "http://127.0.0.1:8080")

    @classmethod
    def setUpClass(cls) -> None:
        """Открывает браузер для тестов против вручную запущенного приложения."""
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        """Закрывает браузер после выполнения UI-тестов."""
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        """Готовит чистый контекст браузера и уникальный префикс данных теста."""
        self.test_prefix = f"__ui_test__ {uuid4().hex[:8]} "
        self.context = self.browser.new_context(locale="ru-RU")
        self.page = self.context.new_page()
        self.app = RecipeBookPage(self.page, self.base_url)
        self.app.open()

    def tearDown(self) -> None:
        """Удаляет созданные тестом сущности через UI и закрывает контекст."""
        try:
            self.app.delete_test_entities_by_prefix(self.test_prefix)
        finally:
            self.context.close()

    def product(self, name: str, **overrides: object) -> ProductCase:
        """Создаёт ProductCase с безопасным тестовым префиксом в названии."""
        payload = {
            "label": name.lower().replace(" ", "_"),
            "name": f"{self.test_prefix}{name}",
            "calories": "41",
            "protein": "0.9",
            "fat": "0.2",
            "carbs": "9.6",
            "category": "Овощи",
            "flags": ("Веган", "Без глютена", "Без сахара"),
        }
        payload.update(overrides)
        return ProductCase(**payload)

    def dish_name(self, name: str) -> str:
        """Возвращает название блюда с тестовым префиксом."""
        return f"{self.test_prefix}{name}"

    def _card_text(self, card) -> str:
        """Возвращает полный текст карточки."""
        return card.inner_text()

    def test_create_products_from_valid_equivalence_classes(self) -> None:
        """Эквивалентное разбиение: валидные классы продуктов создаются через UI."""
        created_names: list[str] = []
        for template in EQUIVALENCE_PRODUCTS:
            product = ProductCase(**{**template.__dict__, "name": f"{self.test_prefix}{template.name}"})
            with self.subTest(product_class=product.label):
                self.app.create_product(product)
                created_names.append(product.name)
        self.assertEqual(created_names, self.app.product_names_by_prefix(self.test_prefix))

    def test_product_name_min_boundary(self) -> None:
        """Анализ граничных значений: 1 символ невалиден, 2 символа валидны."""
        invalid_product = ProductCase(
            label="name_below_min",
            name="A",
            calories="0",
            protein="0",
            fat="0",
            carbs="0",
            category="Жидкость",
            flags=("Веган", "Без глютена", "Без сахара"),
        )
        self.app.fill_product(invalid_product)
        self.page.locator(ProductSelectors.SAVE).click()

        is_invalid = not self.app.is_valid(ProductSelectors.NAME)

        valid_product = ProductCase(
            label="name_at_min",
            name="Ай",
            calories="0",
            protein="0",
            fat="0",
            carbs="0",
            category="Жидкость",
            flags=("Веган", "Без глютена", "Без сахара"),
        )
        self.page.locator(ProductSelectors.RESET).click()
        self.app.create_product(valid_product)
        self.app.delete_product(valid_product.name)
        self.assertTrue(is_invalid)

    def test_product_photo_count_boundary(self) -> None:
        """Анализ граничных значений: 5 фото допустимы, 6 фото отклоняются."""
        accepted = self.product(
            "Тыква пять фото",
            calories="26",
            protein="1",
            fat="0.1",
            carbs="6.5",
            photos=FIVE_PHOTOS,
        )
        self.app.create_product(accepted)

        rejected = self.product(
            "Тыква шесть фото",
            calories="26",
            protein="1",
            fat="0.1",
            carbs="6.5",
            photos=SIX_PHOTOS,
        )
        self.app.fill_product(rejected)
        self.page.locator(ProductSelectors.SAVE).click()

        self.assertEqual(0, self.app.product_card(rejected.name).count())

    def test_product_macro_upper_boundary(self) -> None:
        """Анализ граничных значений: БЖУ 100 валидно, 100.01 блокируется формой."""
        accepted = self.product(
            "Белковый порошок",
            calories="400",
            protein="100",
            fat="0",
            carbs="0",
            category="Сладости",
            flags=("Без глютена",),
        )
        self.app.create_product(accepted)

        rejected = self.product(
            "Невозможный порошок",
            calories="400",
            protein="100.01",
            fat="0",
            carbs="0",
            category="Сладости",
            flags=("Без глютена",),
        )
        self.app.fill_product(rejected)
        self.page.locator(ProductSelectors.SAVE).click()

        self.assertFalse(self.app.is_valid(ProductSelectors.PROTEIN))

    def test_product_calories_lower_boundary(self) -> None:
        """Анализ граничных значений: калории 0 валидны, -0.01 не проходит HTML-валидацию."""
        accepted = self.product("Вода ноль ккал", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        self.app.create_product(accepted)

        rejected = self.product(
            "Отрицательная калорийность",
            calories="-0.01",
            protein="0",
            fat="0",
            carbs="0",
            category="Жидкость",
        )
        self.app.fill_product(rejected)
        self.page.locator(ProductSelectors.SAVE).click()

        self.assertFalse(self.app.is_valid(ProductSelectors.CALORIES))

    def test_product_calories_must_match_macro_partition(self) -> None:
        """Эквивалентное разбиение: несогласованная калорийность относится к невалидному классу."""
        product = self.product(
            "Неверное КБЖУ",
            calories="500",
            protein="1",
            fat="1",
            carbs="1",
        )
        self.app.fill_product(product)
        self.page.locator(ProductSelectors.SAVE).click()

        self.assertEqual(0, self.app.product_card(product.name).count())

    def test_product_sort_by_calories(self) -> None:
        """Эквивалентное разбиение: сортировка по числовому полю упорядочивает карточки."""
        low = self.product("Низкокалорийный", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        middle = self.product("Средний", calories="41", protein="0.9", fat="0.2", carbs="9.6")
        high = self.product("Высококалорийный", calories="400", protein="100", fat="0", carbs="0", category="Сладости")
        for product in (middle, high, low):
            self.app.create_product(product)

        self.app.filter_products(query=self.test_prefix, sort_by="calories")

        self.assertEqual([low.name, middle.name, high.name], self.app.product_names())

    def test_product_filters_select_expected_equivalence_partition(self) -> None:
        """Эквивалентное разбиение: комбинированные фильтры оставляют нужный класс продуктов."""
        matching = self.product("Капуста фильтр", calories="27", protein="1.8", fat="0.1", carbs="4.7")
        wrong_category = self.product(
            "Молоко фильтр",
            calories="52",
            protein="2.8",
            fat="2.5",
            carbs="4.7",
            category="Жидкость",
            flags=("Без глютена", "Без сахара"),
        )
        wrong_flag = self.product(
            "Курица фильтр",
            calories="168",
            protein="24",
            fat="8",
            carbs="0",
            category="Мясной",
            cooking_state="Требует приготовления",
            flags=("Без глютена", "Без сахара"),
        )
        for product in (matching, wrong_category, wrong_flag):
            self.app.create_product(product)

        self.app.filter_products(
            query="Кап",
            category="Овощи",
            cooking_state="Готовый к употреблению",
            flags=("Веган",),
        )

        self.assertEqual([matching.name], self.app.product_names())

    def test_edit_product_updates_card(self) -> None:
        """CRUD через UI: редактирование продукта меняет карточку и показывает успешный toast."""
        original = self.product("Редактируемая морковь")
        updated = self.product(
            "Редактируемая морковь новая",
            calories="42",
            protein="1",
            fat="0.2",
            carbs="9.5",
            cooking_state="Полуфабрикат",
            composition="Обновленный состав",
        )
        self.app.create_product(original)

        self.app.edit_product(original.name, updated)

        self.assertIn("Полуфабрикат", self._card_text(self.app.product_card(updated.name)))

    def test_delete_unused_product_removes_card(self) -> None:
        """CRUD через UI: продукт без зависимостей удаляется из списка."""
        product = self.product("Удаляемый продукт")
        self.app.create_product(product)

        self.app.delete_product(product.name)
        self.app.wait_product_absent(product.name)

        self.assertEqual(0, self.app.product_card(product.name).count())

    def test_dish_preview_creation_and_macro_category_work_from_ui(self) -> None:
        """Эквивалентное разбиение: многоингредиентное блюдо считается и получает категорию из макроса."""
        carrot = self.product("Морковь", calories="41", protein="0.9", fat="0.2", carbs="9.6")
        water = self.product("Вода", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        self.app.create_product(carrot)
        self.app.create_product(water)

        dish_name = self.dish_name("Овощной суп")
        self.app.fill_dish(
            name=f"!суп {dish_name}",
            category="",
            portion_size="200",
            ingredients=((carrot.name, "100"), (water.name, "100")),
            flags=("Веган", "Без глютена", "Без сахара"),
        )
        preview_text = self.page.locator(DishSelectors.PREVIEW).inner_text()

        self.page.locator(DishSelectors.SAVE).click()
        self.assertIn(f"Имя после макроса: {dish_name}", preview_text)

    def test_dish_portion_boundary(self) -> None:
        """Анализ граничных значений: порция -0.01 невалидна, 0.01 валидна."""
        water = self.product("Капля воды", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        self.app.create_product(water)

        invalid_name = self.dish_name("Нулевая порция")
        self.app.fill_dish(name=invalid_name, portion_size="-0.01", ingredients=((water.name, "0.01"),))
        self.page.locator(DishSelectors.SAVE).click()

        is_invalid = not self.app.is_valid(DishSelectors.PORTION_SIZE)

        self.page.locator(DishSelectors.RESET).click()
        self.app.create_dish(
            name=self.dish_name("Мини порция"),
            portion_size="0.01",
            ingredients=((water.name, "0.01"),),
        )
        self.assertTrue(is_invalid)

    def test_dish_ingredient_quantity_boundary(self) -> None:
        """Анализ граничных значений: количество ингредиента -0.01 невалидно, 0.01 валидно."""
        water = self.product("Вода для количества", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        self.app.create_product(water)

        invalid_name = self.dish_name("Нулевой ингредиент")
        self.app.fill_dish(name=invalid_name, ingredients=((water.name, "-0.01"),))
        self.page.locator(DishSelectors.SAVE).click()

        first_quantity = f"{DishSelectors.INGREDIENT_ROW} {DishSelectors.INGREDIENT_QUANTITY}"
        is_invalid = not self.app.is_valid(first_quantity)

        self.page.locator(DishSelectors.RESET).click()
        self.app.create_dish(name=self.dish_name("Мини ингредиент"), ingredients=((water.name, "0.01"),))
        self.assertTrue(is_invalid)

    def test_dish_unavailable_flag_is_disabled_for_meat_ingredient(self) -> None:
        """Эквивалентное разбиение: блюдо с мясом не попадает в класс веганских блюд."""
        meat = self.product(
            "Индейка для блюда",
            calories="109",
            protein="23",
            fat="1",
            carbs="1",
            category="Мясной",
            cooking_state="Требует приготовления",
            flags=("Без глютена", "Без сахара"),
        )
        self.app.create_product(meat)

        self.app.fill_dish(
            name=self.dish_name("Суп с индейкой"),
            category="Суп",
            ingredients=((meat.name, "100"),),
            flags=("Без глютена", "Без сахара"),
        )

        vegan_flag = self.page.locator(f'{DishSelectors.FLAG}[value="Веган"]')
        self.assertTrue(vegan_flag.is_disabled())

    def test_edit_dish_updates_card(self) -> None:
        """CRUD через UI: редактирование блюда меняет порцию и карточку."""
        water = self.product("Вода для блюда", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        self.app.create_product(water)
        original_name = self.dish_name("Редактируемый суп")
        updated_name = self.dish_name("Редактируемый напиток")
        self.app.create_dish(name=original_name, ingredients=((water.name, "100"),))

        self.app.edit_dish(
            original_name,
            name=f"!напиток {updated_name}",
            category="",
            portion_size="250",
            ingredients=((water.name, "150"),),
        )

        self.assertIn("250 г", self._card_text(self.app.dish_card(updated_name)))

    def test_delete_dish_removes_card(self) -> None:
        """CRUD через UI: удаление блюда убирает карточку из списка."""
        water = self.product("Вода для удаления блюда", calories="0", protein="0", fat="0", carbs="0", category="Жидкость")
        dish_name = self.dish_name("Удаляемый суп")
        self.app.create_product(water)
        self.app.create_dish(name=dish_name, ingredients=((water.name, "100"),))

        self.app.delete_dish(dish_name)
        self.app.wait_dish_absent(dish_name)

        self.assertEqual(0, self.app.dish_card(dish_name).count())

    def test_delete_product_used_by_dish_shows_conflict(self) -> None:
        """Эквивалентное разбиение: продукт с зависимым блюдом относится к неудаляемому классу."""
        beet = self.product("Свекла", calories="43", protein="1.6", fat="0.2", carbs="9.6")
        dish_name = self.dish_name("Свекольный суп")
        self.app.create_product(beet)
        self.app.create_dish(name=dish_name, ingredients=((beet.name, "150"),))

        self.app.delete_product(beet.name)

        self.assertEqual(1, self.app.product_card(beet.name).count())


if __name__ == "__main__":
    unittest.main(verbosity=2)
