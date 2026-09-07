# Маппинг LDAP → БД

Снят с рабочего кода Java: `LDAPService.getListAllOfUsers()` (файл пришёл под
именем `CheckNull.java`) и модели `LDAPUser` (файл `DFT_YMDHMS_JSONSerializer.java`).
Реализован в [ldapsync/config.py](../ldapsync/config.py) — `AD_PROFILE`.

## Параметры подключения

| Параметр | Значение в Java | Как сейчас |
| --- | --- | --- |
| протокол | `ldap://host:389`, simple bind | то же, задаётся в `.env` |
| учётка | `username@domain` (UPN) | собирается из `LDAP_<CODE>_BIND_USER` + `_DOMAIN` |
| ветка поиска | `OU=<ORG> Users,DC=...` | `LDAP_<CODE>_BASE_DN` |
| область | SUBTREE | SUBTREE |
| постранично | `PagedResultsControl`, 500 | `paged_search`, `page_size=500` |
| фильтр | `(&(objectCategory=person)(objectClass=user)(sAMAccountName=*))` | тот же |
| отключённые | **забираются** (отсечение закомментировано) и помечаются `state=0` | `include_disabled=True`, помечаются `is_active=False` |

## Поля

| Атрибут AD | Поле `LDAPUser` (Java) | Поле модели | Примечание |
| --- | --- | --- | --- |
| `sAMAccountName` | `userid` (+`@domain`) | `sam_account_name`, `userid` | `userid` повторяет ключ старой системы |
| `objectGUID` | — | `object_guid` | ключ upsert, в Java его не было |
| `name` (или `sn+givenName+middleName`) | `fullname` | `full_name` | ФИО собирается, если `name` пуст |
| `givenName` | `firstname` | `first_name` | |
| `sn` | `surename` | `last_name` | |
| `middleName` | `patronymic` | `middle_name` | |
| `l` | `region` | `region` | |
| `physicalDeliveryOfficeName` | `office_location` | `office` | |
| `extensionAttribute4` | `department_code` | `department_code` | |
| `department` | `department` | `department` | |
| `title` | `position` | `title` | |
| `extensionAttribute6` = `1` | — | `title` → «Перевод сотрудника. Данные обновляются...» | должность подменяется |
| `mail` | `email` | `email` | |
| `homePhone` | `phone_mobile` | `phone_mobile` | именно `homePhone`, не `mobile` |
| `telephoneNumber; mobile; facsimileTelephoneNumber; pager` | `phone_mobile_work` | `phone_mobile_work` | склейка через `; ` |
| `otherTelephone; ipPhone` | `phone_internal` | `phone_internal` | склейка через `; ` |
| `extensionAttribute1` | `bithday` | `birthday` | несколько форматов, см. раздел ниже |
| `employeeNumber` | `uid_zup` | `zup_uid` | ключ связи с 1С ЗУП |
| `manager` | `manager` → ФИО, `manager_id` | `manager_dn` + FK `manager` | в Java на каждого делался отдельный запрос в AD |
| `extensionAttribute2` | `project_name` | `project_name` | |
| `extensionAttribute7` = `1` | `personal_data_consent` | `personal_data_consent` | |
| `thumbnailPhoto` | `photo` (400×650), `photosmall` (100×100) | `photo` | сейчас кладём оригинал, ресайз — отдельная задача |
| `userAccountControl` | — | `ad_enabled`, `is_active` | бит `0x2` — учётка отключена |
| `company` | — | `company_name` | справочное поле AD |
| `whenChanged`, `uSNChanged` | — | `when_changed`, `usn_changed` | для инкрементальной выборки |

## Не из AD — константы организации

`org_id`, `org_name`, `country_id`, `country_name` в Java передавались в
`getListAllOfUsers()` параметрами. У нас они лежат на организации (`Company`) и
подтягиваются к сотруднику через связь — дублировать в каждой записи не нужно.

| Организация | `org_id` | домен | ветка |
| --- | --- | --- | --- |
| ЦЦ ТЭК | `cdtek.ru` | `root.cdtek.ru` | `OU=CDTEK Users,DC=root,DC=cdtek,DC=ru` |
| ЭНГС | `engsdrilling.ru` | `corp.engsdrilling.ru` | `OU=ENGS Users,DC=corp,DC=engsdrilling,DC=ru` |

## Не из AD — данные 1С

Заполняются отдельными вызовами (`getUserZUPInfo`, `getUserDOInfo`,
`getUserVocationInfo`). Поля в модели заведены, синхронизация их пока не трогает:
`zup_state`, `zup_state_dateto`, `do_user_uid`, `do_user_state`, `do_user_role`,
`vacation_days`. URL и логины сервисов лежат в `Company.integrations`, пароли —
в переменных окружения.

## Что проверено

* Маппинг покрыт тестами `employees/tests/test_mapping.py` — склейка телефонов,
  extension-атрибуты, дата рождения, подмена должности, отключённые учётки.
* Прогон на двух тестовых доменах Samba: 6 + 3 записи, уволенные приходят и
  помечаются неактивными.

## Сверено с боевым AD ЦЦ ТЭК (59 записей)

| Атрибут | Заполнено | Вывод |
| --- | --- | --- |
| `extensionAttribute1` | 85% | дата рождения, формат `MM.dd.yyyy` - покрывает 100% значений |
| `extensionAttribute7` | 93% | согласие на ПДн: у всех заполненных значение `1` - подтверждено |
| `extensionAttribute6` | 85% | признак перевода: значение `1` у 8 человек, `0` у 42 - подтверждено |
| `homePhone` | 83% | мобильный - подтверждено |
| `telephoneNumber` / `mobile` | 86% / 5% | рабочий - подтверждено |
| `ipPhone` | 53% | внутренний - подтверждено |
| `employeeNumber` | 92% | UID в 1С ЗУП - подтверждено |
| `thumbnailPhoto` | 88% | фото - подтверждено |
| `l` | 85% | регион - подтверждено |
| `extensionAttribute2` | 0% | проект **не заполняется** |
| `extensionAttribute4` | 0% | код подразделения **не заполняется** |
| `physicalDeliveryOfficeName` | 0% | офис **не заполняется** |
| `otherTelephone`, `pager`, `facsimileTelephoneNumber` | 0% | не используются |
| `manager` | 8% | руководители в каталоге почти не проставлены |

### Формат даты рождения — MM.dd.yyyy

Аудит показал: все 50 значений имеют длину ровно 10 символов, но при чтении как
`dd.MM.yyyy` разбирались только 15. Разгадка в объявлении Java:

```java
static SimpleDateFormat df = new SimpleDateFormat("MM.dd.yyyy");
```

`dfextattr1` использует именно `df` — **сначала месяц, потом день**. То есть
каталог хранит даты в американском порядке. Порядок разбора приведён к
оригиналу: `MM.dd.yyyy` первым, дальше `dd.MM.yyyy`, `yyyy-MM-dd`, `yyyy.MM.dd`,
`dd-MM-yyyy`; время в конце значения допускается.

Два следствия, важных для сверки:

* Даты, где обе части ≤ 12 (например `12.05.1990`), неоднозначны. Мы трактуем их
  как в Java — 5 декабря, а не 12 мая.
* Java разбирал дату «мягко»: `SimpleDateFormat` при месяце `17` не падал, а
  переносил дату на следующий год. То есть у части сотрудников в старой базе
  дата рождения **уже неверная**. При первой полной синхронизации такие записи
  исправятся сами.

Аудит боевого каталога ЦЦ ТЭК подтвердил: `MM.dd.yyyy` разбирает все 50
значений, `dd.MM.yyyy` — только 15. После исправления поле `birthday`
заполняется у 85% записей вместо 25%.

Порядок форматов проверен на обеих организациях:

| Организация | Формат в каталоге | Разбирается |
| --- | --- | --- |
| ЦЦ ТЭК | `MM.dd.yyyy` | 100% значений (50 из 50) |
| ЭНГС | `yyyy-MM-dd` | однозначный формат, спутать с первым нельзя |

Одна цепочка покрывает оба случая, настраивать ничего не нужно. Если у какой-то
организации появится третий порядок — он задаётся на подключении полем
«Формат даты рождения» (`MM.dd.yyyy` / `dd.MM.yyyy`) или переменной
`LDAP_<CODE>_BIRTHDAY_FORMAT`, без правки кода. Команда `ldap_audit` показывает,
какой формат покрывает все значения каталога.

## Чего не хватает для сверки

* **Скриншот с маппингом** от руководителя — сверить с таблицей выше.
* `extensionAttribute1..7` есть только в AD со схемой Exchange. На тестовом Samba
  их нет, поэтому клиент сверяется со схемой сервера и молча пропускает
  неизвестные атрибуты (иначе строгий сервер роняет весь поиск).
* Порядок `dd.MM.yyyy` для `extensionAttribute1` в Java различался по доменам —
  в коде остался закомментированный вариант для `corp.eriell.com`. Для ЦЦ ТЭК и
  ЭНГС используется `dd.MM.yyyy`; при подключении других доменов проверить.
