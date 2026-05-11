# UI system tests

Тесты в этом каталоге покрывают приложение через браузерный UI с помощью
Playwright Python. Они работают против уже запущенного приложения, как обычный
пользователь в браузере. Для cleanup используются только сущности с префиксом
`__ui_test__`, чтобы не удалять пользовательские данные.

## Запуск

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium

# В отдельном терминале:
python3 run.py

# В терминале с тестами:
python3 -m unittest discover -s tests/ui -v
```

Если приложение запущено не на `http://127.0.0.1:8080`, задайте адрес:

```bash
RECIPEBOOK_UI_BASE_URL=http://127.0.0.1:9000 python3 -m unittest discover -s tests/ui -v
```

## Тест-дизайн

| Техника | Где используется | Что проверяется |
| --- | --- | --- |
| Эквивалентное разбиение | `test_create_products_from_valid_equivalence_classes` | Валидные классы продуктов: жидкость с нулевым КБЖУ и мясной продукт без флага `Веган`. |
| Эквивалентное разбиение | `test_product_calories_must_match_macro_partition` | Несогласованная калорийность относится к невалидному классу. |
| Эквивалентное разбиение | `test_product_sort_by_calories` | Сортировка по числовому полю обрабатывает класс числовых значений. |
| Эквивалентное разбиение | `test_product_filters_select_expected_equivalence_partition` | Комбинированные фильтры оставляют только подходящий класс продуктов. |
| Эквивалентное разбиение | `test_dish_preview_creation_and_macro_category_work_from_ui` | Многоингредиентное блюдо, авторасчёт КБЖУ, макрос категории в названии. |
| Эквивалентное разбиение | `test_dish_unavailable_flag_is_disabled_for_meat_ingredient` | Блюдо с мясом не попадает в класс веганских блюд. |
| Эквивалентное разбиение | `test_delete_product_used_by_dish_shows_conflict` | Продукт, используемый блюдом, относится к недоступному для удаления классу. |
| Анализ граничных значений | `test_product_name_min_boundary` | Имя продукта: `1` символ невалиден, `2` символа валидны. |
| Анализ граничных значений | `test_product_photo_count_boundary` | Фото продукта: `5` ссылок валидны, `6` ссылок невалидны. |
| Анализ граничных значений | `test_product_macro_upper_boundary` | БЖУ продукта: `100` валидно, `100.01` невалидно. |
| Анализ граничных значений | `test_product_calories_lower_boundary` | Калории продукта: `0` валидно, `-0.01` невалидно. |
| Анализ граничных значений | `test_dish_portion_boundary` | Порция блюда: `0` невалидно, `0.01` валидно. |
| Анализ граничных значений | `test_dish_ingredient_quantity_boundary` | Количество ингредиента: `0` невалидно, `0.01` валидно. |

Дополнительно CRUD-потоки покрыты тестами редактирования и удаления продуктов и
блюд: `test_edit_product_updates_card`, `test_delete_unused_product_removes_card`,
`test_edit_dish_updates_card`, `test_delete_dish_removes_card`.
