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
| `extensionAttribute1` | `bithday` | `birthday` | строка `dd.MM.yyyy`, ровно 10 символов, иначе `null` |
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

## Чего не хватает для сверки

* **Скриншот с маппингом** от руководителя — сверить с таблицей выше.
* `extensionAttribute1..7` есть только в AD со схемой Exchange. На тестовом Samba
  их нет, поэтому клиент сверяется со схемой сервера и молча пропускает
  неизвестные атрибуты (иначе строгий сервер роняет весь поиск).
* Порядок `dd.MM.yyyy` для `extensionAttribute1` в Java различался по доменам —
  в коде остался закомментированный вариант для `corp.eriell.com`. Для ЦЦ ТЭК и
  ЭНГС используется `dd.MM.yyyy`; при подключении других доменов проверить.
