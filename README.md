## Описание
Корпоративный веб мессенджер на языке Python разработан для дипломной работы 
## Требования
- Компьютер
- Мышка, желательно не трекбольная
- Клавиатура
- Интернет

## Установка
Для работы потребуется [Python](https://www.python.org/downloads/) и библиотеки 
- [Waitress](https://pypi.org/project/waitress/) - Веб сервер 
```sh
pip install Waitress
```
- [WebOb](https://lectureswww.readthedocs.io/6.www.sync/2.codding/6.webob.html) - WebOb — это библиотека, сериализующая HTTP запрос (текст) в объект и позволяющая генерировать HTTP ответы
```sh
pip install WebOb
```
Или же автоматическая установка всех библеотек
```sh
pip install -r requirements.txt
```
## Инициализация и первый запуск
Для [VS Code](https://visualstudio.microsoft.com/ru/#vscode-section)
- После установки проекта в VS Code жмем F5
- После успешного запуска переходим в браузер
- Для доступа к окну регистрации в строке поиска пишем:
```sh
localhost:8000/register
```
- После успешной регистрации вас перенаправит на сайт авторизации
- После успешной авторизации вас перенаправит на окно с мессенджером

## Запуск тестов

1. Установите зависимости (если ещё не установлены):

    ```sh
    pip install -r test_requirements.txt
    ```

2. Запустите все тесты:

    ```sh
    python -m pytest -v
    ```

3. Запустите тесты с определённой меткой (например, только для поиска):

    ```sh
    python -m pytest -m search -v
    ```

4. Для проверки покрытия кода (если установлен pytest-cov):

    ```sh
    python -m pytest --cov=. --cov-report=term-missing
    ```

5. Для просмотра подробного отчёта покрытия в браузере:

    ```sh
    python -m pytest --cov=. --cov-report=html
    # Откройте файл htmlcov/index.html
    ```

---
**Примечание:**  
- Все тесты находятся в папке `tests/`.
- Для корректной работы тестов база данных должна быть в тестовом

![powered by halabudalab](https://i.ibb.co/SXHK6JRt/poweredbyhalabudalab.png)
