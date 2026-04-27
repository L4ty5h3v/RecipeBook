from __future__ import annotations

from dataclasses import replace
import re
from typing import Iterable
from uuid import uuid4

from recipebook.models import (
    MACRO_TO_CATEGORY,
    CookingState,
    Dish,
    DishCategory,
    DishIngredient,
    Flag,
    Nutrition,
    Product,
    ProductCategory,
    now_iso,
)
from recipebook.store import JsonStore


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    def __init__(self, message: str, payload: dict | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class RecipeBookService:
    LEGACY_FLAG_MAP = {
        "vegan": Flag.VEGAN.value,
        "gluten_free": Flag.GLUTEN_FREE.value,
        "sugar_free": Flag.SUGAR_FREE.value,
    }

    SORT_FIELDS = {
        "name": "name",
        "calories": "calories",
        "protein": "protein",
        "fat": "fat",
        "carbs": "carbs",
    }

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def get_meta(self) -> dict:
        return {
            "product_categories": [item.value for item in ProductCategory],
            "cooking_states": [item.value for item in CookingState],
            "dish_categories": [item.value for item in DishCategory],
            "flags": [item.value for item in Flag],
        }

    def list_products(self, filters: dict) -> list[dict]:
        data = self.store.load()
        products = [self._product_from_dict(item) for item in data["products"]]
        query = filters.get("query", "").strip().lower()
        category = filters.get("category")
        cooking_state = filters.get("cooking_state")
        flags = set(filters.get("flags", []))
        sort_by = filters.get("sort_by", "name")

        if category:
            products = [product for product in products if product.category == category]
        if cooking_state:
            products = [
                product for product in products if product.cooking_state == cooking_state
            ]
        if flags:
            products = [
                product for product in products if flags.issubset(set(product.flags))
            ]
        if query:
            products = [
                product for product in products if query in product.name.lower()
            ]

        sort_attr = self.SORT_FIELDS.get(sort_by, "name")
        products.sort(
            key=lambda product: getattr(product, sort_attr)
            if sort_attr != "name"
            else product.name.lower()
        )
        return [product.to_dict() for product in products]

    def create_product(self, payload: dict) -> dict:
        data = self.store.load()
        product = self._build_product(payload)
        data["products"].append(product.to_dict())
        self.store.save(data)
        return product.to_dict()

    def get_product(self, product_id: str) -> dict:
        return self._find_product(product_id).to_dict()

    def update_product(self, product_id: str, payload: dict) -> dict:
        data = self.store.load()
        products = [self._product_from_dict(item) for item in data["products"]]
        index = self._find_index(products, product_id, "Продукт не найден.")
        updated = self._build_product(payload, product_id=product_id, created_at=products[index].created_at)
        updated.updated_at = now_iso()
        products[index] = updated
        dishes = [self._dish_from_dict(item) for item in data["dishes"]]
        products_map = {product.id: product for product in products}
        dishes = self._sync_dish_flags(dishes, products_map)
        data["products"] = [product.to_dict() for product in products]
        data["dishes"] = [dish.to_dict() for dish in dishes]
        self.store.save(data)
        return updated.to_dict()

    def delete_product(self, product_id: str) -> None:
        data = self.store.load()
        dishes = [self._dish_from_dict(item) for item in data["dishes"]]
        used_by = [
            {"id": dish.id, "name": dish.name}
            for dish in dishes
            if any(ingredient.product_id == product_id for ingredient in dish.ingredients)
        ]
        if used_by:
            raise ConflictError(
                "Нельзя удалить продукт, который используется в блюдах.",
                {"used_by": used_by},
            )

        products = [self._product_from_dict(item) for item in data["products"]]
        index = self._find_index(products, product_id, "Продукт не найден.")
        products.pop(index)
        data["products"] = [product.to_dict() for product in products]
        self.store.save(data)

    def list_dishes(self, filters: dict) -> list[dict]:
        data = self.store.load()
        dishes = [self._dish_from_dict(item) for item in data["dishes"]]
        query = filters.get("query", "").strip().lower()
        category = filters.get("category")
        flags = set(filters.get("flags", []))

        if category:
            dishes = [dish for dish in dishes if dish.category == category]
        if flags:
            dishes = [dish for dish in dishes if flags.issubset(set(dish.flags))]
        if query:
            dishes = [dish for dish in dishes if query in dish.name.lower()]

        dishes.sort(key=lambda dish: dish.name.lower())
        products = {
            product["id"]: product for product in self.list_products({"sort_by": "name"})
        }
        return [self._dish_view(dish, products) for dish in dishes]

    def create_dish(self, payload: dict) -> dict:
        data = self.store.load()
        dish = self._build_dish(payload)
        data["dishes"].append(dish.to_dict())
        self.store.save(data)
        products = {item["id"]: item for item in data["products"]}
        return self._dish_view(dish, products)

    def get_dish(self, dish_id: str) -> dict:
        data = self.store.load()
        dishes = [self._dish_from_dict(item) for item in data["dishes"]]
        index = self._find_index(dishes, dish_id, "Блюдо не найдено.")
        products = {item["id"]: item for item in data["products"]}
        return self._dish_view(dishes[index], products)

    def update_dish(self, dish_id: str, payload: dict) -> dict:
        data = self.store.load()
        dishes = [self._dish_from_dict(item) for item in data["dishes"]]
        index = self._find_index(dishes, dish_id, "Блюдо не найдено.")
        updated = self._build_dish(payload, dish_id=dish_id, created_at=dishes[index].created_at)
        updated.updated_at = now_iso()
        dishes[index] = updated
        data["dishes"] = [dish.to_dict() for dish in dishes]
        self.store.save(data)
        products = {item["id"]: item for item in data["products"]}
        return self._dish_view(updated, products)

    def delete_dish(self, dish_id: str) -> None:
        data = self.store.load()
        dishes = [self._dish_from_dict(item) for item in data["dishes"]]
        index = self._find_index(dishes, dish_id, "Блюдо не найдено.")
        dishes.pop(index)
        data["dishes"] = [dish.to_dict() for dish in dishes]
        self.store.save(data)

    def preview_dish(self, payload: dict) -> dict:
        name, macro_category = self._normalize_dish_name(payload.get("name", ""))
        products_map = self._products_map()
        ingredients = self._validate_ingredients(payload.get("ingredients"), products_map)
        suggested = self._calculate_dish_nutrition(ingredients, products_map)
        available_flags = self._available_flags(ingredients, products_map)
        category = payload.get("category") or macro_category
        return {
            "normalized_name": name,
            "suggested_nutrition": suggested.to_dict(),
            "available_flags": available_flags,
            "category_from_macro": macro_category,
            "effective_category": category,
        }

    def _build_product(
        self, payload: dict, product_id: str | None = None, created_at: str | None = None
    ) -> Product:
        name = self._require_name(payload.get("name"), "Название продукта")
        photos = self._validate_photos(payload.get("photos", []))
        calories = self._require_non_negative(payload.get("calories"), "Калорийность")
        protein = self._bounded_macro(payload.get("protein"), "Белки")
        fat = self._bounded_macro(payload.get("fat"), "Жиры")
        carbs = self._bounded_macro(payload.get("carbs"), "Углеводы")
        self._validate_macro_sum(protein, fat, carbs)
        self._validate_calories_consistency(
            calories, protein, fat, carbs, "продукта", per_100_grams=True
        )
        category = self._validate_enum(
            payload.get("category"),
            {item.value for item in ProductCategory},
            "Категория продукта",
        )
        cooking_state = self._validate_enum(
            payload.get("cooking_state"),
            {item.value for item in CookingState},
            "Состояние готовности",
        )
        flags = self._validate_flags(payload.get("flags", []))
        composition = payload.get("composition") or None

        return Product(
            id=product_id or str(uuid4()),
            name=name,
            photos=photos,
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs,
            composition=composition,
            category=category,
            cooking_state=cooking_state,
            flags=flags,
            created_at=created_at or now_iso(),
        )

    def _build_dish(
        self, payload: dict, dish_id: str | None = None, created_at: str | None = None
    ) -> Dish:
        raw_name = payload.get("name")
        normalized_name, macro_category = self._normalize_dish_name(raw_name or "")
        name = self._require_name(normalized_name, "Название блюда")
        photos = self._validate_photos(payload.get("photos", []))
        portion_size = self._require_positive(payload.get("portion_size"), "Размер порции")
        products_map = self._products_map()
        ingredients = self._validate_ingredients(payload.get("ingredients"), products_map)
        suggested = self._calculate_dish_nutrition(ingredients, products_map)
        calories = self._optional_non_negative(
            payload.get("calories"), "Калорийность", suggested.calories
        )
        protein = self._optional_non_negative(
            payload.get("protein"), "Белки", suggested.protein
        )
        fat = self._optional_non_negative(payload.get("fat"), "Жиры", suggested.fat)
        carbs = self._optional_non_negative(payload.get("carbs"), "Углеводы", suggested.carbs)
        self._validate_dish_macro_sum(protein, fat, carbs, portion_size)
        category = self._validate_enum(
            payload.get("category") or macro_category,
            {item.value for item in DishCategory},
            "Категория блюда",
        )
        available_flags = self._available_flags(ingredients, products_map)
        flags = self._validate_flags(payload.get("flags", []))
        unavailable = sorted(set(flags) - set(available_flags))
        if unavailable:
            raise ValidationError(
                "Для блюда недоступны флаги: " + ", ".join(unavailable)
            )

        return Dish(
            id=dish_id or str(uuid4()),
            name=name,
            photos=photos,
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs,
            ingredients=ingredients,
            portion_size=portion_size,
            category=category,
            flags=[flag for flag in flags if flag in available_flags],
            created_at=created_at or now_iso(),
        )

    def _product_from_dict(self, payload: dict) -> Product:
        normalized = {
            **payload,
            "flags": self._normalize_flag_values(payload.get("flags", [])),
        }
        return Product(**normalized)

    def _dish_from_dict(self, payload: dict) -> Dish:
        return Dish(
            **{
                **payload,
                "flags": self._normalize_flag_values(payload.get("flags", [])),
                "ingredients": [
                    DishIngredient(**ingredient) for ingredient in payload["ingredients"]
                ],
            }
        )

    def _find_product(self, product_id: str) -> Product:
        data = self.store.load()
        products = [self._product_from_dict(item) for item in data["products"]]
        index = self._find_index(products, product_id, "Продукт не найден.")
        return products[index]

    def _find_index(self, items: Iterable, entity_id: str, message: str) -> int:
        for index, item in enumerate(items):
            if item.id == entity_id:
                return index
        raise NotFoundError(message)

    def _products_map(self) -> dict[str, Product]:
        data = self.store.load()
        return {
            item["id"]: self._product_from_dict(item)
            for item in data["products"]
        }

    def _sync_dish_flags(
        self, dishes: list[Dish], products_map: dict[str, Product]
    ) -> list[Dish]:
        synced = []
        for dish in dishes:
            available_flags = self._available_flags(dish.ingredients, products_map)
            next_flags = [flag for flag in dish.flags if flag in available_flags]
            if next_flags != dish.flags:
                dish = replace(dish, flags=next_flags, updated_at=now_iso())
            synced.append(dish)
        return synced

    def _dish_view(self, dish: Dish, products_map: dict[str, dict | Product]) -> dict:
        payload = dish.to_dict()
        ingredients = []
        for ingredient in dish.ingredients:
            product = products_map[ingredient.product_id]
            product_name = product.name if isinstance(product, Product) else product["name"]
            ingredients.append(
                {
                    "product_id": ingredient.product_id,
                    "product_name": product_name,
                    "quantity": ingredient.quantity,
                }
            )
        available_flags = self._available_flags(dish.ingredients, self._products_map())
        payload["ingredients"] = ingredients
        payload["suggested_nutrition"] = self._calculate_dish_nutrition(
            dish.ingredients, self._products_map()
        ).to_dict()
        payload["available_flags"] = available_flags
        return payload

    def _normalize_dish_name(self, raw_name: str) -> tuple[str, str | None]:
        name = raw_name.strip()
        if not name:
            return name, None

        lower_name = name.lower()
        matches = []
        for macro in MACRO_TO_CATEGORY:
            position = lower_name.find(macro)
            if position != -1:
                matches.append((position, macro))

        if not matches:
            return name, None

        matches.sort(key=lambda item: item[0])
        _, first_macro = matches[0]
        pattern = "|".join(re.escape(macro) for macro in MACRO_TO_CATEGORY)
        cleaned = re.sub(pattern, "", name, flags=re.IGNORECASE).strip()
        cleaned = " ".join(cleaned.split())
        return cleaned, MACRO_TO_CATEGORY[first_macro]

    def _validate_ingredients(
        self, payload: list[dict] | None, products_map: dict[str, Product]
    ) -> list[DishIngredient]:
        if not payload or not isinstance(payload, list):
            raise ValidationError("У блюда должен быть хотя бы один ингредиент.")
        ingredients = []
        for item in payload:
            product_id = item.get("product_id")
            if product_id not in products_map:
                raise ValidationError("В составе указан несуществующий продукт.")
            quantity = self._require_positive(item.get("quantity"), "Количество продукта")
            ingredients.append(DishIngredient(product_id=product_id, quantity=quantity))
        return ingredients

    def _calculate_dish_nutrition(
        self, ingredients: list[DishIngredient], products_map: dict[str, Product]
    ) -> Nutrition:
        calories = protein = fat = carbs = 0.0
        for ingredient in ingredients:
            product = products_map[ingredient.product_id]
            ratio = ingredient.quantity / 100
            calories += product.calories * ratio
            protein += product.protein * ratio
            fat += product.fat * ratio
            carbs += product.carbs * ratio
        return Nutrition(
            calories=round(calories, 2),
            protein=round(protein, 2),
            fat=round(fat, 2),
            carbs=round(carbs, 2),
        )

    def _available_flags(
        self, ingredients: list[DishIngredient], products_map: dict[str, Product]
    ) -> list[str]:
        available = []
        for flag in Flag:
            if all(flag.value in products_map[item.product_id].flags for item in ingredients):
                available.append(flag.value)
        return available

    def _require_name(self, value: object, field_name: str) -> str:
        if not isinstance(value, str) or len(value.strip()) < 2:
            raise ValidationError(f"{field_name} должно содержать минимум 2 символа.")
        return value.strip()

    def _validate_photos(self, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("Фотографии должны быть массивом.")
        if len(value) > 5:
            raise ValidationError("Можно указать не более 5 фотографий.")
        photos = []
        for item in value:
            if not isinstance(item, str):
                raise ValidationError("Фотографии должны быть строками.")
            item = item.strip()
            if item:
                photos.append(item)
        return photos

    def _validate_enum(self, value: object, allowed: set[str], field_name: str) -> str:
        if value not in allowed:
            raise ValidationError(
                f"{field_name} должно быть одним из: {', '.join(sorted(allowed))}."
            )
        return str(value)

    def _validate_flags(self, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValidationError("Флаги должны быть массивом.")
        allowed = {item.value for item in Flag}
        flags = []
        for item in value:
            item = self.LEGACY_FLAG_MAP.get(item, item)
            if item not in allowed:
                raise ValidationError(f"Неизвестный флаг: {item}.")
            if item not in flags:
                flags.append(item)
        return flags

    def _normalize_flag_values(self, flags: list[str]) -> list[str]:
        return [self.LEGACY_FLAG_MAP.get(flag, flag) for flag in flags]

    def _require_non_negative(self, value: object, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{field_name} должно быть числом.") from None
        if number < 0:
            raise ValidationError(f"{field_name} не может быть меньше 0.")
        return round(number, 2)

    def _optional_non_negative(
        self, value: object, field_name: str, fallback: float
    ) -> float:
        if value in (None, ""):
            return fallback
        return self._require_non_negative(value, field_name)

    def _bounded_macro(self, value: object, field_name: str) -> float:
        number = self._require_non_negative(value, field_name)
        if number > 100:
            raise ValidationError(f"{field_name} не может превышать 100.")
        return number

    def _validate_macro_sum(self, protein: float, fat: float, carbs: float) -> None:
        if protein + fat + carbs > 100:
            raise ValidationError("Сумма БЖУ не может превышать 100 на 100 грамм.")

    def _validate_dish_macro_sum(
        self, protein: float, fat: float, carbs: float, portion_size: float
    ) -> None:
        macros_per_100 = (protein + fat + carbs) / portion_size * 100
        if macros_per_100 > 100:
            raise ValidationError(
                "Сумма БЖУ блюда в пересчёте на 100 грамм не может превышать 100."
            )

    def _require_positive(self, value: object, field_name: str) -> float:
        number = self._require_non_negative(value, field_name)
        if number <= 0:
            raise ValidationError(f"{field_name} должно быть больше 0.")
        return number

    def _validate_calories_consistency(
        self,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
        entity_name: str,
        *,
        per_100_grams: bool,
    ) -> None:
        expected = round(protein * 4 + fat * 9 + carbs * 4, 2)
        tolerance = 5.0
        if abs(calories - expected) > tolerance:
            suffix = "на 100 грамм" if per_100_grams else "на порцию"
            raise ValidationError(
                f"Калорийность {entity_name} должна быть согласована с БЖУ {suffix}. "
                f"Ожидаемое значение около {expected} ккал, допустимое отклонение {tolerance} ккал."
            )
