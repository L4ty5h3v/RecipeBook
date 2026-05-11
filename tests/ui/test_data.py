"""Тестовые данные, подобранные по EP и BVA."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductCase:
    """Данные продукта для заполнения UI-формы."""

    label: str
    name: str
    calories: str
    protein: str
    fat: str
    carbs: str
    category: str
    cooking_state: str = "Готовый к употреблению"
    composition: str = ""
    photos: tuple[str, ...] = ()
    flags: tuple[str, ...] = field(default_factory=tuple)


EQUIVALENCE_PRODUCTS = (
    ProductCase(
        label="valid_liquid_zero_macro_class",
        name="Вода UI",
        calories="0",
        protein="0",
        fat="0",
        carbs="0",
        category="Жидкость",
        composition="",
        photos=("/pictures/water.png",),
        flags=("Веган", "Без глютена", "Без сахара"),
    ),
    ProductCase(
        label="valid_meat_non_vegan_class",
        name="Индейка UI",
        calories="109",
        protein="23",
        fat="1",
        carbs="1",
        category="Мясной",
        cooking_state="Требует приготовления",
        composition="Индейка 100%",
        flags=("Без глютена", "Без сахара"),
    ),
)


FIVE_PHOTOS = tuple(f"/pictures/ui-photo-{index}.png" for index in range(1, 6))
SIX_PHOTOS = tuple(f"/pictures/ui-photo-{index}.png" for index in range(1, 7))
