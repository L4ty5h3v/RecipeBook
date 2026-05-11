"""Centralized UI selectors used by Playwright page objects.

Selectors are intentionally kept outside tests so markup changes affect one
module instead of scattering CSS strings across the suite.
"""


class CommonSelectors:
    """Shared selectors for global UI elements."""

    TOAST = "#toast"
    MODAL = "#details-modal"
    MODAL_TITLE = "#modal-title"
    MODAL_CONTENT = "#modal-content"


class ProductSelectors:
    """Selectors for product form, filters and cards."""

    FORM = "#product-form"
    ID = "#product-id"
    NAME = "#product-name"
    CATEGORY = "#product-category"
    COOKING_STATE = "#product-cooking-state"
    CALORIES = "#product-calories"
    PROTEIN = "#product-protein"
    FAT = "#product-fat"
    CARBS = "#product-carbs"
    COMPOSITION = "#product-composition"
    PHOTOS = "#product-photos"
    SAVE = '#product-form button[type="submit"]'
    RESET = "#reset-product"

    SEARCH = "#product-search"
    FILTER_CATEGORY = "#product-filter-category"
    FILTER_COOKING = "#product-filter-cooking"
    SORT = "#product-sort"
    LIST = "#product-list"
    CARD = "#product-list article.card"
    EMPTY_HINT = "#product-list .hint-card"

    FLAG = 'input[name="product-flag"]'
    FILTER_FLAG = 'input[name="product-filter-flag"]'
    DELETE_BUTTON = 'button[data-action="delete-product"]'


class DishSelectors:
    """Selectors for dish form, preview, filters and cards."""

    FORM = "#dish-form"
    ID = "#dish-id"
    NAME = "#dish-name"
    CATEGORY = "#dish-category"
    PORTION_SIZE = "#dish-portion-size"
    PHOTOS = "#dish-photos"
    INGREDIENTS = "#dish-ingredients"
    INGREDIENT_ROW = ".ingredient-entry"
    INGREDIENT_PRODUCT = ".ingredient-product"
    INGREDIENT_QUANTITY = ".ingredient-quantity"
    ADD_INGREDIENT = "#add-ingredient"
    CALORIES = "#dish-calories"
    PROTEIN = "#dish-protein"
    FAT = "#dish-fat"
    CARBS = "#dish-carbs"
    PREVIEW = "#dish-preview"
    SAVE = '#dish-form button[type="submit"]'
    RESET = "#reset-dish"

    SEARCH = "#dish-search"
    FILTER_CATEGORY = "#dish-filter-category"
    LIST = "#dish-list"
    CARD = "#dish-list article.card"
    EMPTY_HINT = "#dish-list .hint-card"

    FLAG = 'input[name="dish-flag"]'
    FILTER_FLAG = 'input[name="dish-filter-flag"]'
    DELETE_BUTTON = 'button[data-action="delete-dish"]'
