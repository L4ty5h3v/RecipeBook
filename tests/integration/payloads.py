"""Фабрики payload'ов для integration-тестов API."""

from __future__ import annotations


def build_product_payload(name: str, **overrides: object) -> dict:
    """Возвращает валидный payload продукта с возможностью переопределений."""
    payload = {
        "name": name,
        "photos": [],
        "calories": 41,
        "protein": 0.9,
        "fat": 0.2,
        "carbs": 9.6,
        "composition": "Морковь 100%",
        "category": "Овощи",
        "cooking_state": "Готовый к употреблению",
        "flags": ["Веган", "Без глютена", "Без сахара"],
    }
    payload.update(overrides)
    return payload


def build_dish_payload(name: str, ingredients: list[dict], **overrides: object) -> dict:
    """Возвращает валидный payload блюда с возможностью переопределений."""
    payload = {
        "name": name,
        "photos": [],
        "portion_size": 250,
        "category": "Суп",
        "ingredients": ingredients,
        "flags": ["Веган", "Без глютена", "Без сахара"],
    }
    payload.update(overrides)
    return payload
