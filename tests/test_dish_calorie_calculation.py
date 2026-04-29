"""Тесты автоподсчета калорийности блюда."""

import tempfile
import unittest
from pathlib import Path

from recipebook.service import RecipeBookService, ValidationError
from recipebook.store import JsonStore


class DishCalorieCalculationTest(unittest.TestCase):
    """Проверка расчета калорийности блюда."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = RecipeBookService(JsonStore(Path(self.temp_dir.name) / "db.json"))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_product(self, name: str, protein: float, fat: float, carbs: float) -> dict:
        calories = round(protein * 4 + fat * 9 + carbs * 4, 2)
        return self.service.create_product(
            {
                "name": name,
                "photos": [],
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs,
                "composition": "",
                "category": "Овощи",
                "cooking_state": "Готовый к употреблению",
                "flags": ["Веган", "Без глютена", "Без сахара"],
            }
        )

    def _create_dish(self, portion_size: float, ingredients: list[dict]) -> dict:
        return self.service.create_dish(
            {
                "name": "Тестовое блюдо",
                "photos": [],
                "portion_size": portion_size,
                "category": "Суп",
                "ingredients": ingredients,
                "flags": ["Веган", "Без глютена", "Без сахара"],
            }
        )

    def test_calories_equivalence_partitioning(self) -> None:
        """Эквивалентное разбиение: один и несколько валидных ингредиентов."""
        carrot = self._create_product("Морковь", 1.3, 0.1, 6.9)
        beet = self._create_product("Свекла", 1.6, 0.2, 9.6)

        cases = [
            {
                "ingredients": [{"product_id": carrot["id"], "quantity": 100}],
                "portion_size": 100,
                "expected_calories": 33.7,
            },
            {
                "ingredients": [
                    {"product_id": carrot["id"], "quantity": 100},
                    {"product_id": beet["id"], "quantity": 100},
                ],
                "portion_size": 200,
                "expected_calories": 80.3,
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                dish = self._create_dish(case["portion_size"], case["ingredients"])
                self.assertEqual(case["expected_calories"], dish["calories"])
                self.assertEqual(
                    case["expected_calories"], dish["suggested_nutrition"]["calories"]
                )

    def test_empty_dish_equivalence_partitioning(self) -> None:
        """Эквивалентное разбиение: пустое блюдо относится к невалидному классу."""
        with self.assertRaises(ValidationError):
            self._create_dish(100, [])

    def test_calories_boundary_values(self) -> None:
        """Граничные значения: минимально допустимое и недопустимое количество."""
        pumpkin = self._create_product("Тыква", 1.0, 0.1, 4.4)

        dish = self._create_dish(
            0.01,
            [{"product_id": pumpkin["id"], "quantity": 0.01}],
        )
        self.assertEqual(0.0, dish["calories"])

        with self.assertRaises(ValidationError):
            self._create_dish(
                100,
                [{"product_id": pumpkin["id"], "quantity": 0}],
            )

        with self.assertRaises(ValidationError):
            self._create_dish(
                100,
                [{"product_id": pumpkin["id"], "quantity": -0.01}],
            )

if __name__ == "__main__":
    unittest.main()
