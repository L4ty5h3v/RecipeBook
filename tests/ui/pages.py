"""Page Object для системных UI-тестов Recipe Book."""

from __future__ import annotations

import fcntl
import os
import re
import tempfile

from playwright.sync_api import Page, expect

from tests.ui.ui_selectors import CommonSelectors, DishSelectors, ProductSelectors
from tests.ui.test_data import ProductCase


class UiWriteLock:
    """Межпроцессная блокировка write-операций для pytest-xdist."""

    def __init__(self) -> None:
        self.path = os.environ.get(
            "RECIPEBOOK_UI_WRITE_LOCK",
            os.path.join(tempfile.gettempdir(), "recipebook-ui-write.lock"),
        )
        self._file = None

    def __enter__(self):
        self._file = open(self.path, "w", encoding="utf-8")
        fcntl.flock(self._file, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._file is None:
            return
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
        self._file = None


class RecipeBookPage:
    """Высокоуровневые действия пользователя на странице приложения."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        self.write_lock = UiWriteLock()

    def open(self) -> None:
        """Открывает приложение и ждёт загрузки справочников и списков."""
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
        """Создаёт продукт через видимую форму."""
        self.fill_product(product)
        self._submit_with_write_lock("POST", "/api/products", ProductSelectors.SAVE)
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Продукт создан.")
        expect(self.product_card(product.name)).to_have_count(1)

    def fill_product(self, product: ProductCase) -> None:
        """Заполняет поля формы продукта."""
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
        """Возвращает карточку продукта по видимому названию."""
        exact_title = self.page.locator("h3").filter(
            has_text=re.compile(f"^{re.escape(name)}$")
        )
        return self.page.locator(ProductSelectors.CARD).filter(has=exact_title)

    def product_names(self) -> list[str]:
        """Возвращает названия продуктов в текущем порядке карточек."""
        return self.page.locator(f"{ProductSelectors.CARD} h3").all_text_contents()

    def product_names_by_prefix(self, prefix: str) -> list[str]:
        """Возвращает названия только тестовых продуктов с указанным префиксом."""
        self.filter_products(query=prefix)
        self.page.wait_for_timeout(200)
        return self.product_names()

    def wait_product_absent(self, name: str) -> None:
        """Ждёт исчезновения карточки продукта после удаления."""
        expect(self.product_card(name)).to_have_count(0)

    def edit_product(self, old_name: str, new_product: ProductCase) -> None:
        """Открывает продукт на редактирование и сохраняет новые значения."""
        self.product_card(old_name).locator(ProductSelectors.EDIT_BUTTON).click()
        expect(self.page.locator(ProductSelectors.ID)).not_to_have_value("")
        self.fill_product(new_product)
        self._submit_with_write_lock("PUT", "/api/products/", ProductSelectors.SAVE)
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Продукт обновлён.")
        expect(self.product_card(new_product.name)).to_have_count(1)

    def delete_product(self, name: str) -> None:
        """Удаляет продукт кнопкой из карточки."""
        button = self.product_card(name).locator(ProductSelectors.DELETE_BUTTON)
        self._click_with_write_lock("DELETE", "/api/products/", button)

    def filter_products(
        self,
        *,
        query: str = "",
        category: str = "",
        cooking_state: str = "",
        sort_by: str = "name",
        flags: tuple[str, ...] = (),
    ) -> None:
        """Применяет фильтры продуктов через интерфейс."""
        self.page.locator(ProductSelectors.SEARCH).fill(query)
        self.page.locator(ProductSelectors.FILTER_CATEGORY).select_option(value=category)
        self.page.locator(ProductSelectors.FILTER_COOKING).select_option(value=cooking_state)
        self.page.locator(ProductSelectors.SORT).select_option(value=sort_by)
        self.set_checkboxes(ProductSelectors.FILTER_FLAG, flags)

    def delete_products_by_prefix(self, prefix: str) -> None:
        """Удаляет через UI все видимые продукты с указанным префиксом."""
        self.filter_products(query=prefix)
        self.page.wait_for_timeout(300)
        cards = self.page.locator(ProductSelectors.CARD)
        while cards.count() > 0:
            next_count = cards.count() - 1
            button = cards.first.locator(ProductSelectors.DELETE_BUTTON)
            self._click_with_write_lock("DELETE", "/api/products/", button, force=True)
            expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Продукт удалён.")
            expect(cards).to_have_count(next_count, timeout=5000)
        expect(cards).to_have_count(0)

    def create_dish(
        self,
        *,
        name: str,
        category: str = "Суп",
        portion_size: str = "200",
        ingredients: tuple[tuple[str, str], ...],
        flags: tuple[str, ...] = ("Веган", "Без глютена", "Без сахара"),
    ) -> None:
        """Создаёт блюдо через видимую форму."""
        self.fill_dish(
            name=name,
            category=category,
            portion_size=portion_size,
            ingredients=ingredients,
            flags=flags,
        )
        self._submit_with_write_lock("POST", "/api/dishes", DishSelectors.SAVE)
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
        """Заполняет форму блюда, выбирая ингредиенты по видимому названию."""
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
        """Возвращает карточку блюда по видимому названию."""
        exact_title = self.page.locator("h3").filter(
            has_text=re.compile(f"^{re.escape(name)}$")
        )
        return self.page.locator(DishSelectors.CARD).filter(has=exact_title)

    def dish_names(self) -> list[str]:
        """Возвращает названия блюд в текущем порядке карточек."""
        return self.page.locator(f"{DishSelectors.CARD} h3").all_text_contents()

    def wait_dish_absent(self, name: str) -> None:
        """Ждёт исчезновения карточки блюда после удаления."""
        expect(self.dish_card(name)).to_have_count(0)

    def filter_dishes(
        self,
        *,
        query: str = "",
        category: str = "",
        flags: tuple[str, ...] = (),
    ) -> None:
        """Применяет фильтры блюд через интерфейс."""
        self.page.locator(DishSelectors.SEARCH).fill(query)
        self.page.locator(DishSelectors.FILTER_CATEGORY).select_option(value=category)
        self.set_checkboxes(DishSelectors.FILTER_FLAG, flags)

    def delete_dishes_by_prefix(self, prefix: str) -> None:
        """Удаляет через UI все видимые блюда с указанным префиксом."""
        self.filter_dishes(query=prefix)
        self.page.wait_for_timeout(300)
        cards = self.page.locator(DishSelectors.CARD)
        while cards.count() > 0:
            next_count = cards.count() - 1
            button = cards.first.locator(DishSelectors.DELETE_BUTTON)
            self._click_with_write_lock("DELETE", "/api/dishes/", button, force=True)
            expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Блюдо удалено.")
            expect(cards).to_have_count(next_count, timeout=5000)
        expect(cards).to_have_count(0)

    def delete_test_entities_by_prefix(self, prefix: str) -> None:
        """Удаляет тестовые блюда и продукты через UI, не обращаясь напрямую к API."""
        self.open()
        self.delete_dishes_by_prefix(prefix)
        self.delete_products_by_prefix(prefix)

    def edit_dish(
        self,
        old_name: str,
        *,
        name: str,
        category: str = "Суп",
        portion_size: str = "200",
        ingredients: tuple[tuple[str, str], ...],
        flags: tuple[str, ...] = ("Веган", "Без глютена", "Без сахара"),
    ) -> None:
        """Открывает блюдо на редактирование и сохраняет новые значения."""
        self.dish_card(old_name).locator(DishSelectors.EDIT_BUTTON).click()
        expect(self.page.locator(DishSelectors.ID)).not_to_have_value("")
        self.fill_dish(
            name=name,
            category=category,
            portion_size=portion_size,
            ingredients=ingredients,
            flags=flags,
        )
        self._submit_with_write_lock("PUT", "/api/dishes/", DishSelectors.SAVE)
        expect(self.page.locator(CommonSelectors.TOAST)).to_contain_text("Блюдо обновлено.")
        expect(self.dish_card(self._name_without_macro(name))).to_have_count(1)

    def delete_dish(self, name: str) -> None:
        """Удаляет блюдо кнопкой из карточки."""
        button = self.dish_card(name).locator(DishSelectors.DELETE_BUTTON)
        self._click_with_write_lock("DELETE", "/api/dishes/", button)

    def set_checkboxes(self, selector: str, values: tuple[str, ...]) -> None:
        """Выставляет группу чекбоксов ровно в переданные значения."""
        checkboxes = self.page.locator(selector)
        for index in range(checkboxes.count()):
            checkbox = checkboxes.nth(index)
            should_check = checkbox.input_value() in values
            if checkbox.is_disabled() and not should_check:
                continue
            checkbox.set_checked(should_check)

    def is_valid(self, selector: str) -> bool:
        """Возвращает результат native HTML-валидации элемента формы."""
        return bool(self.page.locator(selector).evaluate("element => element.checkValidity()"))

    def _submit_with_write_lock(self, method: str, url_part: str, button_selector: str) -> None:
        """Жмёт submit под lock и ждёт write-ответ backend."""
        button = self.page.locator(button_selector)
        self._click_with_write_lock(method, url_part, button)

    def _click_with_write_lock(
        self,
        method: str,
        url_part: str,
        locator,
        *,
        force: bool = False,
    ) -> None:
        """Сериализует write-запросы, чтобы xdist workers не перетирали db.json."""
        with self.write_lock:
            with self.page.expect_response(
                lambda response: url_part in response.url
                and response.request.method == method
            ):
                locator.click(force=force, timeout=5000)

    @staticmethod
    def _name_without_macro(name: str) -> str:
        macros = ("!десерт", "!первое", "!второе", "!напиток", "!салат", "!суп", "!перекус")
        result = name
        for macro in macros:
            result = result.replace(macro, "").replace(macro.upper(), "")
        return " ".join(result.split())
