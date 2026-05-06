"""Единая точка запуска integration-тестов живого API.

Файл удобно запускать напрямую из PyCharm одной кнопкой Run.
Тесты выполняются против уже поднятого backend и не поднимают сервер сами.
"""

from __future__ import annotations

import unittest


def build_suite() -> unittest.TestSuite:
    """Собирает integration-тесты из каталога tests/integration."""
    loader = unittest.defaultTestLoader
    return loader.discover("tests/integration", pattern="test_*.py")


def main() -> int:
    """Запускает полный test suite и возвращает код завершения."""
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
