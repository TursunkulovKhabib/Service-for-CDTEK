# Контакты — микросервис справочника сотрудников (Django + AD/LDAP)

Микросервис забирает сотрудников из Active Directory по LDAPS, складывает их в
PostgreSQL и отдаёт наружу REST API. Данными пользуются бот «Контакты» (MAX и
Telegram) и админка Django Unfold как справочник для ручного поиска и правок.
Переписывает существующий Java/Servlet-микросервис на Python/Django.

## Что уже работает

* подключение к каталогу через `ldap3`: LDAPS, StartTLS, простой/NTLM bind,
  проверка сертификата по корневому CA;
* постраничный поиск (`paged_search`) по нескольким OU с фильтром по
  `objectCategory=person` / `objectClass=user` и отсечением отключённых учёток
  через `userAccountControl:1.2.840.113556.1.4.803:=2`;
* upsert в PostgreSQL по `objectGUID` — переименование учётки или перенос между
  OU не создаёт дубль;
* пропавшие из выдачи сотрудники не удаляются, а помечаются неактивными
  (`is_active=False`, проставляется `deactivated_at`);
* инкрементальная синхронизация по `whenChanged` с водяным знаком прошлого
  успешного запуска и запасом в 10 минут на расхождение часов;
* запуск по расписанию: Celery beat (`django-celery-beat`) или cron через
  management-команду;
* журнал запусков `SyncRun` — сколько прочитано/создано/обновлено/деактивировано;
* REST API на DRF с поиском по ФИО, подразделению, должности, почте и телефону
  в любом формате; доступ по заголовку `X-API-Key`;
* админка на Django Unfold с кнопками ручного запуска синхронизации;
* 23 теста: маппинг атрибутов AD, логика синхронизации, API.

## Проверено вживую

| Каталог | Что проверено |
| --- | --- |
| Samba AD DC (docker-compose, схема настоящего AD) | bind, paged search, `objectGUID`, `userAccountControl`, `manager`, `whenChanged`, полная и инкрементальная синхронизация |
| `ldap.forumsys.com` (публичный OpenLDAP, read-only) | смоук-тест подключения и разбора записей |

Открытых Active Directory в интернете нет, поэтому боевая схема проверяется на
локальном Samba AD DC — там те же `sAMAccountName`, `objectGUID`, `memberOf` и
постраничный поиск, то есть код пишется сразу боевой.

## Структура

```
serviceforcdtek/         настройки Django, Celery
ldapsync/                работа с каталогом (без Django-моделей в API)
  config.py              параметры подключения и профили каталогов (ad / openldap)
  client.py              ldap3: подключение и постраничный поиск
  mapping.py             LDAP-атрибуты -> поля модели
  sync.py                upsert, мягкая деактивация, связывание руководителей
employees/               модели, админка Unfold, DRF API, Celery-задачи
  management/commands/   ldap_test, sync_ldap, setup_periodic_tasks
scripts/samba_seed.sh    наполнение тестового AD сотрудниками
docker-compose.yml       PostgreSQL, Redis, Samba AD DC
```

## Быстрый старт

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env        # прописать реквизиты AD и БД
docker compose up -d postgres redis
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Админка — `http://127.0.0.1:8000/admin/`, API — `http://127.0.0.1:8000/api/v1/`.

> В Windows-консоли перед запуском полезно выставить `set PYTHONUTF8=1`,
> иначе кириллица в выводе команд превращается в кракозябры.

## Тестовый LDAP-запрос

Публичный демо-сервер (ничего поднимать не нужно):

```bash
python manage.py ldap_test --demo --limit 5
```

Локальный Samba AD DC — настоящая схема AD:

```bash
docker compose --profile ad up -d samba-ad
docker cp scripts/samba_seed.sh contacts-samba-ad:/tmp/samba_seed.sh
docker exec contacts-samba-ad bash /tmp/samba_seed.sh
python manage.py ldap_test --profile ad --server ldap://127.0.0.1:1389 --no-ssl --bind-dn "CN=Administrator,CN=Users,DC=corp,DC=local" --password 'Passw0rd!2026' --base-dn "DC=corp,DC=local" --ou "OU=Users,OU=Company,DC=corp,DC=local"
```

> Скрипт наполнения копируется в контейнер, а не подаётся через `<`: в
> PowerShell перенаправление `<` не поддерживается.

Боевой AD — реквизиты берутся из `.env`:

```bash
python manage.py ldap_test --limit 5
```

Полезные флаги: `--raw` (сырые атрибуты каталога), `--json`, `--filter`,
`--include-disabled`, `--start-tls`, `--insecure` (не проверять сертификат —
только для тестового контура).

## Синхронизация

```bash
python manage.py sync_ldap                 # полный обход
python manage.py sync_ldap --incremental   # только изменённые с прошлого раза
python manage.py sync_ldap --dry-run       # посмотреть, ничего не записывая
python manage.py sync_ldap --demo          # с публичного демо-сервера
```

По расписанию — Celery:

```bash
python manage.py setup_periodic_tasks      # заводит задачи в django-celery-beat
celery -A serviceforcdtek worker -l info
celery -A serviceforcdtek beat -l info
```

Либо cron, если Celery в контуре не нужен:

```
*/15 * * * * cd /srv/contacts && .venv/bin/python manage.py sync_ldap --incremental
20 3 * * *   cd /srv/contacts && .venv/bin/python manage.py sync_ldap --full
```

## API

| Метод | Endpoint | Назначение |
| --- | --- | --- |
| GET | `/api/v1/employees/` | список и поиск |
| GET | `/api/v1/employees/{objectGUID}/` | карточка сотрудника с руководителем |
| GET | `/api/v1/departments/` | подразделения с количеством сотрудников |
| GET | `/api/v1/sync-runs/` | история синхронизаций |
| GET | `/api/v1/health/` | живость сервиса и свежесть данных |

Параметры поиска: `?q=` (ФИО, логин, почта, подразделение, должность, телефон),
`?phone=+7 (495) 123-45-67` (номер в любом формате — сравнение идёт по цифрам),
`?department=`, `?company=`, `?title=`, `?office=`, `?ordering=full_name`,
`?limit=&offset=`, `?include_inactive=1`.

```bash
curl -H "X-API-Key: $API_KEY" "https://contacts.corp.local/api/v1/employees/?q=иванов"
```

Ключ бота задаётся в `API_KEY`; при `API_REQUIRE_KEY=1` запросы без ключа
получают 403. Авторизованная сессия админки тоже пускает в API.

## Что забираем из AD

| Атрибут AD | Поле модели | Комментарий |
| --- | --- | --- |
| `objectGUID` | `object_guid` | ключ синхронизации, не меняется при переименовании |
| `sAMAccountName` | `sam_account_name` | логин |
| `displayName`, `sn`, `givenName`, `middleName` | `display_name`, `full_name`, … | ФИО собирается из `sn + givenName + middleName` |
| `mail` | `email` | |
| `telephoneNumber`, `mobile`, `ipPhone` | `phone`, `mobile_phone`, `internal_phone` | плюс `search_phone` — только цифры, для поиска |
| `department`, `title`, `company`, `physicalDeliveryOfficeName`, `l` | `department`, `title`, `company`, `office`, `city` | |
| `manager` | `manager_dn` + FK `manager` | связывается вторым проходом |
| `employeeID`, `description` | `employee_id`, `description` | |
| `userAccountControl` | `ad_enabled`, `is_active` | бит `0x2` — учётка отключена |
| `whenCreated`, `whenChanged`, `uSNChanged` | одноимённые поля | `whenChanged` — водяной знак инкрементальной выборки |

Состав полей уточняется по задаче в Битриксе — маппинг вынесен в
`ldapsync/config.py` (`AD_PROFILE.attribute_map`), правится одной строкой.
Несколько организаций поддерживаются списком OU в `LDAP_SEARCH_OUS` (через `;`),
организация сотрудника пишется в `company`.

## Ручные правки в админке

Синхронизация перетирает всё, что приехало из AD. Чтобы закрепить значение за
собой, перечислите поля в `locked_fields` карточки, например `["phone", "title"]`
— эти поля синхронизация не тронет. Есть также `is_hidden` (сотрудник остаётся в
БД, но не отдаётся боту) и `notes` для служебных заметок.

## Эксплуатация

* Реквизиты сервисной учётки — только в переменных окружения, в репозиторий не
  попадают (`.env` в `.gitignore`). Учётке достаточно прав на чтение каталога.
* В проде обязательно `LDAP_USE_SSL=1` и `LDAP_TLS_VALIDATE=1` с указанием
  корневого сертификата в `LDAP_CA_CERTS_FILE`.
* `LDAP_MIN_ENTRIES_FOR_DEACTIVATION` страхует от массовой деактивации, если AD
  вернул подозрительно мало записей (например, при обрыве связи).
* Полная синхронизация — раз в сутки ночью, инкрементальная — каждые 15 минут.

## Тесты

```bash
python manage.py test employees
```

## Дальше по задаче

* уточнить состав полей и список организаций/OU из задачи в Битриксе;
* включить LDAPS с корпоративным CA на реальном DC (сейчас проверено на
  самоподписанном контуре Samba);
* при необходимости перейти с `whenChanged` на `uSNChanged` — поле уже пишется;
* завести доступ боту: отдельный `API_KEY` и лимиты на стороне nginx.
