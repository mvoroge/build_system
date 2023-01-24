import os
from sys import argv
from os import path as os_path

from build_api import start_build_system


def create_artefacts_dir() -> str:
    # Создание папки с артефактами в случае его отсутствия
    if not os_path.exists('artifacts'):
        os.mkdir('artifacts')
    return os_path.abspath('artifacts')


def main() -> None:
    # config_path = os_path.abspath(argv[1])
    config_path = os_path.abspath('test_cnfg.json')   # Вариант запуска с тестовым файлом конфигурации
    assert os_path.isfile(config_path), 'Путь недействительный!'

    artefacts_dir = create_artefacts_dir()

    # Вывод результата сборки
    print(start_build_system(config_path=config_path, artefacts_dir=artefacts_dir))


if __name__ == '__main__':
    main()
