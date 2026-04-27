import tempfile
import unittest
from pathlib import Path

from recipebook.service import RecipeBookService, ValidationError
from recipebook.store import JsonStore


class DishCalorieCalculationTest(unittest.TestCase):
    """Тесты на автоподсчет калорийности блюда."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        store = JsonStore(Path(self.temp_dir.name) / "db.json")
        self.service = RecipeBookService(store)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_product(
        self,
        name: str,
        protein: float,
        fat: float,
        carbs: float,
        *,
        category: str = "Овощи",
    ) -> dict:
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
                "category": category,
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

    def test_calories_with_different_valid_inputs(self) -> None:
        """Эквивалентное разбиение."""
        carrot = self._create_product("Морковь", protein=1.3, fat=0.1, carbs=6.9)
        beet = self._create_product("Свекла", protein=1.6, fat=0.2, carbs=9.6)
        water = self._create_product(
            "Вода", protein=0, fat=0, carbs=0, category="Жидкость"
        )

        cases = [
            {
                "title": "one_product",
                "portion_size": 120,
                "ingredients": [{"product_id": carrot["id"], "quantity": 120}],
                "expected_calories": 40.44,
            },
            {
                "title": "two_products",
                "portion_size": 250,
                "ingredients": [
                    {"product_id": carrot["id"], "quantity": 100},
                    {"product_id": beet["id"], "quantity": 150},
                ],
                "expected_calories": 103.6,
            },
            {
                "title": "with_water",
                "portion_size": 300,
                "ingredients": [
                    {"product_id": beet["id"], "quantity": 100},
                    {"product_id": water["id"], "quantity": 200},
                ],
                "expected_calories": 46.6,
            },
        ]

        for case in cases:
            with self.subTest(case=case["title"]):
                dish = self._create_dish(case["portion_size"], case["ingredients"])
                self.assertEqual(
                    case["expected_calories"], dish["suggested_nutrition"]["calories"]
                )
                self.assertEqual(case["expected_calories"], dish["calories"])

    def test_calories_on_boundaries(self) -> None:
        """Граничные значения."""
        pumpkin = self._create_product("Тыква", protein=1.0, fat=0.1, carbs=4.4)

        cases = [
            {
                "title": "min_quantity",
                "portion_size": 0.01,
                "ingredients": [{"product_id": pumpkin["id"], "quantity": 0.01}],
                "expected_calories": 0.0,
            },
            {
                "title": "exact_100g",
                "portion_size": 100,
                "ingredients": [{"product_id": pumpkin["id"], "quantity": 100}],
                "expected_calories": pumpkin["calories"],
            },
        ]

        for case in cases:
            with self.subTest(case=case["title"]):
                dish = self._create_dish(case["portion_size"], case["ingredients"])
                self.assertEqual(
                    case["expected_calories"], dish["suggested_nutrition"]["calories"]
                )

        with self.subTest(case="zero_quantity"):
            with self.assertRaises(ValidationError):
                self._create_dish(
                    100,
                    [{"product_id": pumpkin["id"], "quantity": 0}],
                )

    def test_macro_sets_category_when_field_is_empty(self) -> None:
        water = self._create_product(
            "Вода", protein=0, fat=0, carbs=0, category="Жидкость"
        )

        dish = self.service.create_dish(
            {
                "name": "!суп Борщ",
                "photos": [],
                "portion_size": 300,
                "ingredients": [{"product_id": water["id"], "quantity": 300}],
                "flags": ["Веган", "Без глютена", "Без сахара"],
            }
        )

        self.assertEqual("Борщ", dish["name"])
        self.assertEqual("Суп", dish["category"])

    def test_first_macro_is_used_when_there_are_several(self) -> None:
        water = self._create_product(
            "Вода", protein=0, fat=0, carbs=0, category="Жидкость"
        )

        dish = self.service.create_dish(
            {
                "name": "!десерт !салат Тест",
                "photos": [],
                "portion_size": 300,
                "ingredients": [{"product_id": water["id"], "quantity": 300}],
                "flags": ["Веган", "Без глютена", "Без сахара"],
            }
        )

        self.assertEqual("Тест", dish["name"])
        self.assertEqual("Десерт", dish["category"])

    def test_user_can_override_auto_calculated_kbju_for_dish(self) -> None:
        water = self._create_product(
            "Вода", protein=0, fat=0, carbs=0, category="Жидкость"
        )

        dish = self.service.create_dish(
            {
                "name": "Тест ручной правки",
                "photos": [],
                "portion_size": 300,
                "category": "Суп",
                "ingredients": [{"product_id": water["id"], "quantity": 300}],
                "calories": 25,
                "protein": 2,
                "fat": 1,
                "carbs": 3,
                "flags": ["Веган", "Без глютена", "Без сахара"],
            }
        )

        self.assertEqual(25.0, dish["calories"])
        self.assertEqual(2.0, dish["protein"])
        self.assertEqual(1.0, dish["fat"])
        self.assertEqual(3.0, dish["carbs"])


if __name__ == "__main__":
    unittest.main()
