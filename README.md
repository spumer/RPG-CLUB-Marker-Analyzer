# README #

# Звонкий Шекель 1.0.0 #

Это небольшой веб-сервис по анализу рынка серверов Lineage 2 проекта [rpg-club](http://www.rpg-club.com/).

## Системные требования:
Python >=3.3 (asyncio) или Python 3.4

## Возможности ##

* Сбор статистики спроса и предложений
* Отслеживание ситуаций когда продают дешевле, чем покупают (внерыночные котировки).

## Как это работает? ##
Запущенная Python-служба каждые 2 минуты парсит страницу рынка и записывает данные в БД. При открытии странички в браузере она начинает каждые 30 секунд опрашивать сервер на предмет изменений и сигнализирует звуковым сигналом. Так что вы можете открыть вкладку в фоне и заниматься своими делами.

В интерфейсе предусмотрена кнопка `ПОТРАЧЕНО`, чтобы вы могли помечать те позиции, которые уже не актуальны. Действие можно обратить повторным нажатием. Слева крупным шрифтом отображена потенциальная прибыль, а мелким, под ней, необходимые вложения. Справа название предмета, иконка и количество необходимое для купли-продажи.
![interface_example.PNG](https://bitbucket.org/repo/4XGban/images/1706823379-interface_example.PNG)

## Как установить? ##
### Подготовка БД ###
```python
import market

market.sqlite_init_items()
market.sqlite_init_trades()

exprs = []

for file_name in ('items_l2j.sql', 'items_rpgclug.sql'):
    with open(file_name) as f:
        exprs.extend(f.read().split(';'))

with market.sqlite_conn() as conn:
    cur = conn.cursor()
    for expr in exprs:
        cur.execute(expr)

```
По умолчанию будет создан файл `market_history.db`, но вы можете это изменить передав имя файла в качестве параметра в эти функции, либо задав значение по умолчанию `SQLITE_DB_FILENAME` в `market.py`

### Настройка Nginx ###
Скопируйте содержимое каталога `www` в любое доступное для nginx место, например `/var/www/`.
Пример конфигурации:
```nginx
server {
        listen *:80;
        server_name l2-shekel.example.com;

        location / {
                root /var/www;
        }

        location /api {
                access_log off;
                proxy_pass http://127.0.0.1:8080;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header Host $host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
}
```

## Как запустить? ##
Выполнить
```bash
python3.4 run.py
```
Пример файла `run_server.sh` для Python 3.3 + asyncio:
```bash
#!/bin/bash

SELF_DIR=$(dirname $(readlink -f $0))

source $SELF_DIR/aio/bin/activate
screen -AmdS market-rpg-club python $SELF_DIR/run.py
```
где `aio` это [виртуальное окружение Python](http://docs.python-guide.org/en/latest/dev/virtualenvs/), а про `screen` вы можете прочитать [отдельно](http://www.opennet.ru/man.shtml?topic=screen&category=8&russian=0)


## Что еще? ##
- Вы можете сообщить серверу какие торговцы уже ничего не продают или ничего не покупают, тогда он подберет вам других. К сожалению это реализовано только на стороне сервера, в интерфейсе никак не поддерживается. Вы можете доделать это сами. Если коротко, то для каждого покупающего/продающего формируется хэш и тонкий клиент отправляет те, которые необходимо проигнорировать при анализе, будто их нет. См. файл `analyze.py` метод `get_dupes`.
- Я прикладываю БД для сервера motherland (Родина), на ней вы сможете потренироваться если вдруг захотите построить графики или считать медиану для цены. Ведь одно из прибыльных направлений это быстрая скупка по бросовой цене и перепродажа. Всё в ваших руках!

# Благодарности #
Спасибо моим друзьям, за веб-интерфейс, за тестирование и за идеи, некоторым из которых так и не довелось дойти до конца. Это было весело и интересно!

# Что теперь? #
Этот проект больше не развивается и не поддерживается. Если у вас есть вопросы, то я готов ответить на них, но не по JS-коду :)