# UI system tests

Тесты в этом каталоге покрывают приложение через браузерный UI с помощью
Playwright Python. Сервер поднимается на временной базе `db.json`, поэтому
рабочие данные из `data/db.json` не изменяются.

## Запуск

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m unittest discover -s tests/ui -v
```

## Тест-дизайн

| Техника | Где используется | Что проверяется |
| --- | --- | --- |
| Эквивалентное разбиение | `test_create_products_from_valid_equivalence_classes` | Валидные классы продуктов: жидкость с нулевым КБЖУ и мясной продукт без флага `Веган`. |
| Эквивалентное разбиение | `test_dish_preview_creation_and_macro_category_work_from_ui` | Многоингредиентное блюдо, авторасчёт КБЖУ, макрос категории в названии. |
| Эквивалентное разбиение | `test_product_filters_select_expected_equivalence_partition` | Комбинированные фильтры оставляют только подходящий класс продуктов. |
| Эквивалентное разбиение | `test_deleting_product_used_by_dish_shows_conflict_in_ui` | Продукт, используемый блюдом, относится к недоступному для удаления классу. |
| Анализ граничных значений | `test_product_name_boundary_is_enforced_by_visible_form` | Имя продукта: `1` символ невалиден, `2` символа валидны. |
| Анализ граничных значений | `test_product_photo_count_boundary_is_checked_after_submit` | Фото продукта: `5` ссылок валидны, `6` ссылок невалидны. |
| Анализ граничных значений | `test_product_macro_upper_boundary_is_enforced_by_visible_form` | БЖУ продукта: `100` валидно, `100.01` невалидно. |
| Анализ граничных значений | `test_dish_portion_boundary_is_enforced_by_visible_form` | Порция блюда: `0` невалидно, `0.01` валидно. |
