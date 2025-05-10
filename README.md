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

![powered by halabudalab](https://i.ibb.co/SXHK6JRt/poweredbyhalabudalab.png)
