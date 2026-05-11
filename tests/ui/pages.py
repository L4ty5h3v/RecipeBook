"""Page objects for Recipe Book UI system tests."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.ui.ui_selectors import CommonSelectors, DishSelectors, ProductSelectors
from tests.ui.test_data import ProductCase


class RecipeBookPage:
    """High-level actions and assertions for the Recipe Book single page UI."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    def open(self) -> None:
        """Open the app and wait for dictionaries and initial lists to load."""
        self.page.goto(self.base_url)
        self.page.wait_for_function(
            """
            () => document.querySelector('#product-category')?.options.length > 0
              && document.querySelector('#dish-category')?.options.length > 1
              && document.querySelector('#product-list')?.textContent !== ''
              && document.querySelector('#dish-list')?.textContent !== ''
            """
        )

    def create_product(self, product: ProductCase) -> None:
        """Create a product through the visible product form."""
        self.fill_product(product)
        self.page.locator(ProductSelectors.SAVE).click()
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Продукт создан.")
        expect(self.product_card(product.name)).to_have_count(1)

    def fill_product(self, product: ProductCase) -> None:
        """Fill product form fields with a complete product case."""
        self.page.locator(ProductSelectors.NAME).fill(product.name)
        self.page.locator(ProductSelectors.CATEGORY).select_option(value=product.category)
        self.page.locator(ProductSelectors.COOKING_STATE).select_option(value=product.cooking_state)
        self.page.locator(ProductSelectors.CALORIES).fill(product.calories)
        self.page.locator(ProductSelectors.PROTEIN).fill(product.protein)
        self.page.locator(ProductSelectors.FAT).fill(product.fat)
        self.page.locator(ProductSelectors.CARBS).fill(product.carbs)
        self.page.locator(ProductSelectors.COMPOSITION).fill(product.composition)
        self.page.locator(ProductSelectors.PHOTOS).fill("\n".join(product.photos))
        self.set_checkboxes(ProductSelectors.FLAG, product.flags)

    def product_card(self, name: str):
        """Return a locator for a product card by visible name."""
        return self.page.locator(ProductSelectors.CARD, has_text=name)

    def product_names(self) -> list[str]:
        """Return product card titles in their current UI order."""
        return self.page.locator(f"{ProductSelectors.CARD} h3").all_text_contents()

    def delete_product(self, name: str) -> None:
        """Delete a product from its card action button."""
        self.product_card(name).locator(ProductSelectors.DELETE_BUTTON).click()

    def filter_products(
        self,
        *,
        query: str = "",
        category: str = "",
        cooking_state: str = "",
        sort_by: str = "name",
        flags: tuple[str, ...] = (),
    ) -> None:
        """Apply product filters through the UI."""
        self.page.locator(ProductSelectors.SEARCH).fill(query)
        self.page.locator(ProductSelectors.FILTER_CATEGORY).select_option(value=category)
        self.page.locator(ProductSelectors.FILTER_COOKING).select_option(value=cooking_state)
        self.page.locator(ProductSelectors.SORT).select_option(value=sort_by)
        self.set_checkboxes(ProductSelectors.FILTER_FLAG, flags)

    def create_dish(
        self,
        *,
        name: str,
        category: str = "Суп",
        portion_size: str = "200",
        ingredients: tuple[tuple[str, str], ...],
        flags: tuple[str, ...] = ("Веган", "Без глютена", "Без сахара"),
    ) -> None:
        """Create a dish through the visible dish form."""
        self.fill_dish(
            name=name,
            category=category,
            portion_size=portion_size,
            ingredients=ingredients,
            flags=flags,
        )
        self.page.locator(DishSelectors.SAVE).click()
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Блюдо создано.")
        expected_name = self._name_without_macro(name)
        expect(self.dish_card(expected_name)).to_have_count(1)

    def fill_dish(
        self,
        *,
        name: str,
        category: str = "Суп",
        portion_size: str = "200",
        ingredients: tuple[tuple[str, str], ...],
        flags: tuple[str, ...] = ("Веган", "Без глютена", "Без сахара"),
    ) -> None:
        """Fill dish form fields with ingredients selected by visible product name."""
        self.page.locator(DishSelectors.NAME).fill(name)
        self.page.locator(DishSelectors.CATEGORY).select_option(value=category)
        self.page.locator(DishSelectors.PORTION_SIZE).fill(portion_size)
        for index, (product_name, quantity) in enumerate(ingredients):
            if index > 0:
                self.page.locator(DishSelectors.ADD_INGREDIENT).click()
            row = self.page.locator(DishSelectors.INGREDIENT_ROW).nth(index)
            row.locator(DishSelectors.INGREDIENT_PRODUCT).select_option(label=product_name)
            row.locator(DishSelectors.INGREDIENT_QUANTITY).fill(quantity)
        self.set_checkboxes(DishSelectors.FLAG, flags)

    def dish_card(self, name: str):
        """Return a locator for a dish card by visible name."""
        return self.page.locator(DishSelectors.CARD, has_text=name)

    def delete_dish(self, name: str) -> None:
        """Delete a dish from its card action button."""
        self.dish_card(name).locator(DishSelectors.DELETE_BUTTON).click()

    def set_checkboxes(self, selector: str, values: tuple[str, ...]) -> None:
        """Set a checkbox group to exactly the supplied values."""
        checkboxes = self.page.locator(selector)
        for index in range(checkboxes.count()):
            checkbox = checkboxes.nth(index)
            checkbox.set_checked(checkbox.input_value() in values)

    def is_valid(self, selector: str) -> bool:
        """Return native HTML validity for a form control."""
        return bool(self.page.locator(selector).evaluate("element => element.checkValidity()"))

    @staticmethod
    def _name_without_macro(name: str) -> str:
        macros = ("!десерт", "!первое", "!второе", "!напиток", "!салат", "!суп", "!перекус")
        result = name
        for macro in macros:
            result = result.replace(macro, "").replace(macro.upper(), "")
        return " ".join(result.split())
