"""System UI tests for Recipe Book.

The suite covers end-to-end browser scenarios for the task "1 - Разработать
тестируемую систему". Test data is selected with equivalence partitioning (EP)
and boundary value analysis (BVA), while the browser exercises the same forms,
filters and action buttons that a user sees.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from playwright.sync_api import expect, sync_playwright

from tests.ui.pages import RecipeBookPage
from tests.ui.ui_selectors import CommonSelectors, DishSelectors, ProductSelectors
from tests.ui.server import RecipeBookUiServer
from tests.ui.test_data import EQUIVALENCE_PRODUCTS, FIVE_PHOTOS, ProductCase, SIX_PHOTOS


class RecipeBookUiSystemTest(unittest.TestCase):
    """System tests that drive the application through its browser UI."""

    @classmethod
    def setUpClass(cls) -> None:
        """Start an isolated backend and a Chromium browser once for the suite."""
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.server = RecipeBookUiServer(cls.repo_root)
        cls.server.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        """Close browser resources and stop the isolated backend."""
        cls.browser.close()
        cls.playwright.stop()
        cls.server.stop()

    def setUp(self) -> None:
        """Reset data and open a fresh browser context before every test."""
        self.server.reset_data()
        self.context = self.browser.new_context(locale="ru-RU")
        self.page = self.context.new_page()
        self.app = RecipeBookPage(self.page, self.server.base_url)
        self.app.open()

    def tearDown(self) -> None:
        """Close the browser context after each test for UI isolation."""
        self.context.close()

    def test_create_products_from_valid_equivalence_classes(self) -> None:
        """EP: liquid zero-macro and meat non-vegan classes are accepted via UI."""
        for product in EQUIVALENCE_PRODUCTS:
            with self.subTest(product_class=product.label):
                self.app.create_product(product)
                card = self.app.product_card(product.name)
                expect(card).to_contain_text(product.category)
                expect(card).to_contain_text(product.cooking_state)
                for flag in product.flags:
                    expect(card).to_contain_text(flag)

    def test_product_name_boundary_is_enforced_by_visible_form(self) -> None:
        """BVA: name length 1 is invalid, while minimum length 2 is accepted."""
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

        self.assertFalse(self.app.is_valid(ProductSelectors.NAME))
        expect(self.page.locator(ProductSelectors.EMPTY_HINT)).to_contain_text("Пока нет продуктов.")

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

    def test_product_photo_count_boundary_is_checked_after_submit(self) -> None:
        """BVA: five photo links are accepted, six links are rejected by server validation."""
        accepted = ProductCase(
            label="five_photos_boundary",
            name="Тыква пять фото",
            calories="26",
            protein="1",
            fat="0.1",
            carbs="6.5",
            category="Овощи",
            photos=FIVE_PHOTOS,
            flags=("Веган", "Без глютена", "Без сахара"),
        )
        self.app.create_product(accepted)

        rejected = ProductCase(
            label="six_photos_boundary",
            name="Тыква шесть фото",
            calories="26",
            protein="1",
            fat="0.1",
            carbs="6.5",
            category="Овощи",
            photos=SIX_PHOTOS,
            flags=("Веган", "Без глютена", "Без сахара"),
        )
        self.app.fill_product(rejected)
        self.page.locator(ProductSelectors.SAVE).click()

        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text(
            "Можно указать не более 5 фотографий."
        )
        expect(self.app.product_card(rejected.name)).to_have_count(0)

    def test_product_macro_upper_boundary_is_enforced_by_visible_form(self) -> None:
        """BVA: macro value 100 is valid and 100.01 violates the input boundary."""
        accepted = ProductCase(
            label="protein_at_max",
            name="Белковый порошок",
            calories="400",
            protein="100",
            fat="0",
            carbs="0",
            category="Сладости",
            flags=("Без глютена",),
        )
        self.app.create_product(accepted)

        rejected = ProductCase(
            label="protein_above_max",
            name="Невозможный порошок",
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
        expect(self.app.product_card(rejected.name)).to_have_count(0)

    def test_dish_preview_creation_and_macro_category_work_from_ui(self) -> None:
        """EP: multi-ingredient dish preview calculates nutrition and applies macro category."""
        self.app.create_product(
            ProductCase(
                label="vegetable_ingredient",
                name="Морковь",
                calories="41",
                protein="0.9",
                fat="0.2",
                carbs="9.6",
                category="Овощи",
                flags=("Веган", "Без глютена", "Без сахара"),
            )
        )
        self.app.create_product(
            ProductCase(
                label="liquid_ingredient",
                name="Вода",
                calories="0",
                protein="0",
                fat="0",
                carbs="0",
                category="Жидкость",
                flags=("Веган", "Без глютена", "Без сахара"),
            )
        )

        self.app.fill_dish(
            name="!суп Овощной суп",
            category="",
            portion_size="200",
            ingredients=(("Морковь", "100"), ("Вода", "100")),
            flags=("Веган", "Без глютена", "Без сахара"),
        )
        expect(self.page.locator(DishSelectors.PREVIEW)).to_contain_text("Авторасчёт: 41")
        expect(self.page.locator(DishSelectors.PREVIEW)).to_contain_text(
            "Имя после макроса: Овощной суп"
        )
        expect(self.page.locator(DishSelectors.CATEGORY)).to_have_value("Суп")

        self.page.locator(DishSelectors.SAVE).click()
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Блюдо создано.")
        expect(self.app.dish_card("Овощной суп")).to_contain_text("Авторасчёт: 41")

    def test_dish_portion_boundary_is_enforced_by_visible_form(self) -> None:
        """BVA: portion 0 is invalid, while the minimum positive 0.01 is accepted."""
        self.app.create_product(
            ProductCase(
                label="boundary_ingredient",
                name="Капля воды",
                calories="0",
                protein="0",
                fat="0",
                carbs="0",
                category="Жидкость",
                flags=("Веган", "Без глютена", "Без сахара"),
            )
        )

        self.app.fill_dish(
            name="Нулевая порция",
            portion_size="0",
            ingredients=(("Капля воды", "0.01"),),
        )
        self.page.locator(DishSelectors.SAVE).click()

        self.assertFalse(self.app.is_valid(DishSelectors.PORTION_SIZE))
        expect(self.app.dish_card("Нулевая порция")).to_have_count(0)

        self.page.locator(DishSelectors.RESET).click()
        self.app.create_dish(
            name="Мини порция",
            portion_size="0.01",
            ingredients=(("Капля воды", "0.01"),),
        )

    def test_product_filters_select_expected_equivalence_partition(self) -> None:
        """EP: combined filters leave only products in the matching UI partition."""
        for product in (
            ProductCase(
                label="matching_partition",
                name="Капуста фильтр",
                calories="27",
                protein="1.8",
                fat="0.1",
                carbs="4.7",
                category="Овощи",
                flags=("Веган", "Без глютена", "Без сахара"),
            ),
            ProductCase(
                label="wrong_category_partition",
                name="Молоко фильтр",
                calories="52",
                protein="2.8",
                fat="2.5",
                carbs="4.7",
                category="Жидкость",
                flags=("Без глютена", "Без сахара"),
            ),
            ProductCase(
                label="wrong_flag_partition",
                name="Курица фильтр",
                calories="168",
                protein="24",
                fat="8",
                carbs="0",
                category="Мясной",
                cooking_state="Требует приготовления",
                flags=("Без глютена", "Без сахара"),
            ),
        ):
            self.app.create_product(product)

        self.app.filter_products(
            query="Кап",
            category="Овощи",
            cooking_state="Готовый к употреблению",
            flags=("Веган",),
        )

        expect(self.page.locator(ProductSelectors.CARD)).to_have_count(1)
        self.assertEqual(["Капуста фильтр"], self.app.product_names())

    def test_deleting_product_used_by_dish_shows_conflict_in_ui(self) -> None:
        """EP: product with dependent dish belongs to non-deletable partition."""
        self.app.create_product(
            ProductCase(
                label="used_product",
                name="Свекла",
                calories="43",
                protein="1.6",
                fat="0.2",
                carbs="9.6",
                category="Овощи",
                flags=("Веган", "Без глютена", "Без сахара"),
            )
        )
        self.app.create_dish(name="Свекольный суп", ingredients=(("Свекла", "150"),))

        self.app.delete_product("Свекла")

        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text(
            "Нельзя удалить продукт, который используется в блюдах."
        )
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Свекольный суп")
        expect(self.app.product_card("Свекла")).to_have_count(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
