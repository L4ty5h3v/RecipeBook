from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class ProductCategory(StrEnum):
    FROZEN = "Замороженный"
    MEAT = "Мясной"
    VEGETABLES = "Овощи"
    GREENS = "Зелень"
    SPICES = "Специи"
    GRAINS = "Крупы"
    CANNED = "Консервы"
    LIQUID = "Жидкость"
    SWEETS = "Сладости"


class CookingState(StrEnum):
    READY = "Готовый к употреблению"
    SEMI_FINISHED = "Полуфабрикат"
    NEEDS_COOKING = "Требует приготовления"


class DishCategory(StrEnum):
    DESSERT = "Десерт"
    FIRST = "Первое"
    SECOND = "Второе"
    DRINK = "Напиток"
    SALAD = "Салат"
    SOUP = "Суп"
    SNACK = "Перекус"


class Flag(StrEnum):
    VEGAN = "Веган"
    GLUTEN_FREE = "Без глютена"
    SUGAR_FREE = "Без сахара"


MACRO_TO_CATEGORY = {
    "!десерт": DishCategory.DESSERT.value,
    "!первое": DishCategory.FIRST.value,
    "!второе": DishCategory.SECOND.value,
    "!напиток": DishCategory.DRINK.value,
    "!салат": DishCategory.SALAD.value,
    "!суп": DishCategory.SOUP.value,
    "!перекус": DishCategory.SNACK.value,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Nutrition:
    calories: float
    protein: float
    fat: float
    carbs: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Product:
    id: str
    name: str
    photos: list[str]
    calories: float
    protein: float
    fat: float
    carbs: float
    composition: str | None
    category: str
    cooking_state: str
    flags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DishIngredient:
    product_id: str
    quantity: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Dish:
    id: str
    name: str
    photos: list[str]
    calories: float
    protein: float
    fat: float
    carbs: float
    ingredients: list[DishIngredient]
    portion_size: float
    category: str
    flags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ingredients"] = [ingredient.to_dict() for ingredient in self.ingredients]
        return data
