# Инструкция по запуску сервиса «Контакты»

Пошаговый сценарий: от чистой машины до работающей админки и API.
Все команды выполняются из корня проекта — `C:\Users\HONOR\PycharmProjects\serviceforcdtek`
(в PyCharm это вкладка **Terminal** внизу).

---

## 0. Что должно быть установлено

| Что | Зачем | Проверка |
| --- | --- | --- |
| Python 3.12 | сам сервис | `python --version` |
| Docker Desktop (запущен) | PostgreSQL, Redis, тестовый AD | `docker info` |

Если `docker info` ругается «cannot find the file specified» — Docker Desktop не
запущен. Откройте его из меню «Пуск» и подождите, пока значок кита перестанет
мигать.

**Кодировка консоли.** В PowerShell перед работой выполните один раз за сессию,
иначе русские буквы в выводе будут кракозябрами:

```bash
$env:PYTHONUTF8=1
```

---

## 1. Быстрый старт (минимум, чтобы увидеть админку)

### 1.1 Установить зависимости

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Если виртуального окружения ещё нет:

```bash
python -m venv .venv
```

### 1.2 Создать файл настроек

```bash
copy .env.example .env
```

Файл `.env` — это пароли и адреса. В git он не попадает. Для локальной работы
достаточно поправить в нём три строки:

```
POSTGRES_PORT=5433
API_V2_REQUIRE_JWT=0
LEGACY_V1_REQUIRE_BASIC_AUTH=0
```

### 1.3 Поднять базу данных и брокер

```bash
docker compose up -d postgres redis
```

Проверить, что оба контейнера живы:

```bash
docker ps
```

Ожидаемо: `contacts-postgres` на порту 5433 и `contacts-redis` на 6379, оба в
статусе `healthy`.

### 1.4 Создать таблицы

```bash
.venv\Scripts\python.exe manage.py migrate
```

### 1.5 Завести организации и LDAP-подключения

```bash
.venv\Scripts\python.exe manage.py load_companies
```

Команда читает [settings/companies.py](serviceforcdtek/settings/companies.py) и
создаёт в базе организации вместе с их LDAP-подключениями — дальше их можно
править прямо в админке.

### 1.6 Создать себе вход в админку

```bash
.venv\Scripts\python.exe manage.py createsuperuser
```

Спросит логин, почту (можно пропустить) и пароль. Пароль при вводе не
отображается — это нормально, просто печатайте вслепую.

### 1.7 Запустить сервис

```bash
.venv\Scripts\python.exe manage.py runserver
```

Пока команда работает — сервис живёт. Останавливается по `Ctrl+C`.

Открыть в браузере:

* **http://127.0.0.1:8000/admin/** — админка (логин из шага 1.6)
* **http://127.0.0.1:8000/api/v1/employees/** — старый API
* **http://127.0.0.1:8000/api/v2/employees/** — новый API
* **http://127.0.0.1:8000/api/v2/health/** — состояние сервиса

На этом этапе сотрудников ещё нет — их нужно откуда-то забрать. Дальше два
варианта: тестовый AD (шаг 2) или боевой (шаг 3).

---

## 2. Тестовый Active Directory

Пока нет доступа к боевому AD, поднимаем свой — два независимых домена, чтобы
проверить работу с двумя организациями.

### 2.1 Запустить доменные контроллеры

```bash
docker compose --profile ad --profile ad2 up -d samba-ad samba-ad-branch
```

Первый запуск занимает около минуты — контейнеры разворачивают домены
`corp.local` (порт 1389) и `branch.local` (порт 2389). Дождитесь статуса
`healthy`:

```bash
docker ps
```

### 2.2 Наполнить их сотрудниками

```bash
docker cp scripts/samba_seed.sh contacts-samba-ad:/tmp/seed.sh
```

```bash
docker exec contacts-samba-ad bash /tmp/seed.sh
```

```bash
docker cp scripts/samba_seed.sh contacts-samba-ad-branch:/tmp/seed.sh
```

```bash
docker exec -e BASE_DN="DC=branch,DC=local" -e COMPANY_NAME="ЭНГС" -e SEED_SET=engs contacts-samba-ad-branch bash /tmp/seed.sh
```

В первом домене появятся 6 сотрудников (один намеренно отключён — проверяем, что
уволенные не попадают в справочник), во втором — 3.

### 2.3 Проверить подключение, ничего не записывая

```bash
.venv\Scripts\python.exe manage.py ldap_test --connection "AD ЦЦ ТЭК"
```

Команда покажет параметры подключения, данные о сервере и найденные записи. В
базу она не пишет — это безопасная проверка.

Совсем без своего AD можно проверить связку на публичном сервере:

```bash
.venv\Scripts\python.exe manage.py ldap_test --demo --limit 5
```

### 2.4 Загрузить сотрудников в базу

```bash
.venv\Scripts\python.exe manage.py sync_ldap --all
```

В конце будет отчёт по каждой организации: прочитано / создано / обновлено /
деактивировано. Теперь в админке и в API есть люди.

---

## 3. Боевой Active Directory

Когда дадут доступ и VPN, код менять не нужно — только настройки.

1. Прописать в `.env` реквизиты (пароль **только** здесь, не в коде и не в git):

```
LDAP_CDTEK_SERVER_URI=ldaps://dc01.corp.local
LDAP_CDTEK_USE_SSL=1
LDAP_CDTEK_TLS_VALIDATE=1
LDAP_CDTEK_CA_CERTS_FILE=C:\certs\corp-root-ca.pem
LDAP_CDTEK_BIND_DN=CN=svc-contacts,OU=Service,DC=corp,DC=local
LDAP_CDTEK_BIND_PASSWORD=пароль-сервисной-учётки
LDAP_CDTEK_BASE_DN=DC=corp,DC=local
LDAP_CDTEK_SEARCH_OUS=OU=Users,OU=Company,DC=corp,DC=local
```

2. Обновить записи в базе:

```bash
.venv\Scripts\python.exe manage.py load_companies
```

3. Проверить подключение **до** первой синхронизации:

```bash
.venv\Scripts\python.exe manage.py ldap_test --limit 5
```

4. Первый прогон сделать вхолостую, чтобы посмотреть, что придёт:

```bash
.venv\Scripts\python.exe manage.py sync_ldap --dry-run --limit 20
```

5. И только потом по-настоящему:

```bash
.venv\Scripts\python.exe manage.py sync_ldap --all
```

Дальше подключения правятся прямо в админке, в разделе «LDAP-подключения», без
перезапуска сервиса.

---

## 4. Синхронизация по расписанию (Celery)

Расписание держится в базе и правится в админке. Создать задачи по умолчанию
(инкрементально каждые 15 минут, полная синхронизация ночью в 03:20):

```bash
.venv\Scripts\python.exe manage.py setup_periodic_tasks
```

Дальше нужны два процесса — **каждый в своём окне терминала**:

```bash
.venv\Scripts\python.exe -m celery -A serviceforcdtek worker -l info --pool=solo
```

```bash
.venv\Scripts\python.exe -m celery -A serviceforcdtek beat -l info
```

> `--pool=solo` обязателен на Windows — без него воркер падает.

Проверить, что связка жива: в админке → «Периодические задачи» → кнопка
«Проверить брокер и воркеры». Результаты выполненных задач видны в разделе
«Результаты задач».

Если Celery не нужен, то же самое можно повесить на планировщик задач Windows или
cron:

```
*/15 * * * * cd /srv/contacts && .venv/bin/python manage.py sync_ldap --incremental --all
20 3 * * *   cd /srv/contacts && .venv/bin/python manage.py sync_ldap --all
```

---

## 5. Запуск целиком в Docker

Вариант без локального Python — поднимаются сразу веб-сервис, воркер, расписание,
база и брокер:

```bash
docker compose --profile app up -d --build
```

Сервис будет на **http://127.0.0.1:8000/**. Миграции и загрузка организаций
выполняются автоматически при старте контейнера.

> **Важно про адреса.** Внутри контейнера `127.0.0.1` — это он сам, а не ваш
> компьютер. Поэтому в `.env` для docker-режима адреса тестовых доменов пишутся
> по именам сервисов, а не по локальному порту:
>
> ```
> LDAP_CDTEK_SERVER_URI=ldap://samba-ad:389
> LDAP_ENGS_SERVER_URI=ldap://samba-ad-branch:389
> ```
>
> Хост и порт PostgreSQL с Redis compose подставляет сам, их менять не нужно.
> Для боевого AD ничего этого не касается — там обычный внешний адрес.

Посмотреть логи:

```bash
docker compose --profile app logs -f app worker beat
```

Остановить:

```bash
docker compose --profile app down
```

---

## 6. Проверка, что всё работает

```bash
.venv\Scripts\python.exe manage.py test employees
```

Ожидаемо: `Ran 49 tests ... OK`.

Быстрый чек-лист вручную:

| Что проверяем | Где смотреть | Ожидаемо |
| --- | --- | --- |
| сервис жив | `/api/v2/health/` | `"status": "ok"`, число сотрудников |
| данные приехали | `/admin/employees/employee/` | список с ФИО, должностями |
| две организации | `/admin/employees/company/` | по каждой видно число сотрудников |
| подключения к AD | `/admin/employees/ldapserver/` | статус последней синхронизации |
| журнал прогонов | `/admin/employees/syncrun/` | прочитано / создано / обновлено |
| старый API | `/api/v1/employees/?query=иванов` | плоский массив из 4 полей |
| новый API | `/api/v2/employees/?company=cdtek` | ответ с пагинацией |

---

## 7. Ежедневные команды

```bash
.venv\Scripts\python.exe manage.py sync_ldap --all
```

```bash
.venv\Scripts\python.exe manage.py sync_ldap --company cdtek
```

```bash
.venv\Scripts\python.exe manage.py sync_ldap --incremental --all
```

```bash
.venv\Scripts\python.exe manage.py ldap_test --connection "AD ЦЦ ТЭК" --raw
```

Синхронизацию можно запускать и мышкой — в админке над списком сотрудников есть
кнопки «Полная синхронизация с AD» и «Инкрементальная синхронизация».

---

## 8. Если что-то пошло не так

**`Оператор "<" зарезервирован для использования в будущем`**
Это PowerShell: перенаправление `<` он не поддерживает. Используйте вариант с
`docker cp` из шага 2.2.

**`&&` выдаёт ошибку разбора**
В Windows PowerShell 5.1 нет `&&`. Запускайте команды по одной, каждую отдельной
строкой.

**Кракозябры вместо русских букв**
Выполните `$env:PYTHONUTF8=1` и повторите команду.

**`connection timeout expired` при `migrate`**
Не поднят PostgreSQL. Проверьте `docker ps`, при необходимости
`docker compose up -d postgres`. Если Docker Desktop был перезапущен, контейнеры
надо поднять заново.

**`Error response from daemon` / `cannot find the file specified`**
Не запущен Docker Desktop.

**`That port is already in use`**
Порт 8000 занят другим процессом. Запустите на другом:
`.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001`.

**В админке сообщение «Celery недоступен, выполнено синхронно»**
Не запущен воркер или Redis. Это не поломка: сервис специально выполняет
синхронизацию сразу, а не теряет её. Поднимите Redis и воркер (шаг 4).

**`Не удалось подключиться к ...` при синхронизации**
Проверьте подключение отдельно: `manage.py ldap_test --connection "AD ЦЦ ТЭК"`.
Типичные причины: не тот порт, нет VPN, неверный пароль сервисной учётки, или
сертификат не проходит проверку (для тестового контура помогает флаг
`--insecure`, в проде — правильный `LDAP_CDTEK_CA_CERTS_FILE`).

---

## 9. Остановка и очистка

Остановить контейнеры, данные сохранятся:

```bash
docker compose --profile ad --profile ad2 --profile app down
```

Удалить вообще всё, включая базу и тестовые домены (данные пропадут):

```bash
docker compose --profile ad --profile ad2 --profile app down -v
```

После этого запуск начинается заново с шага 1.3.
