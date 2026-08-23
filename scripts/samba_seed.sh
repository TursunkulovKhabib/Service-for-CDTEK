#!/bin/bash
# Наполняет тестовый Samba AD DC оргструктурой и сотрудниками.
# Запуск (после `docker compose --profile ad up -d samba-ad`):
#
#   docker cp scripts/samba_seed.sh contacts-samba-ad:/tmp/samba_seed.sh
#   docker exec contacts-samba-ad bash /tmp/samba_seed.sh
#
# Скрипт идемпотентен: повторный запуск не падает на уже существующих объектах.
set -u

BASE_DN="DC=corp,DC=local"
USERS_OU="OU=Users,OU=Company,${BASE_DN}"
PASS='Passw0rd!2026'
# Расположение базы каталога зависит от сборки Samba, поэтому ищем её.
SAM_LDB="$(find /usr/local/samba /var/lib/samba -name sam.ldb 2>/dev/null | head -1)"

create_ou() {
    samba-tool ou create "$1" 2>/dev/null && echo "OU создана: $1" || echo "OU уже есть: $1"
}

create_user() {
    local login="$1" surname="$2" given="$3" title="$4" dept="$5" phone="$6"
    if samba-tool user show "$login" >/dev/null 2>&1; then
        echo "Пользователь уже есть: $login"
        return
    fi
    samba-tool user create "$login" "$PASS" \
        --userou="OU=Users,OU=Company" \
        --surname="$surname" \
        --given-name="$given" \
        --job-title="$title" \
        --department="$dept" \
        --company="ЦДТ" \
        --mail-address="${login}@corp.local" \
        --telephone-number="$phone" \
        --physical-delivery-office="Главный офис" \
        >/dev/null && echo "Создан: $login ($surname $given)"
}

create_ou "OU=Company,${BASE_DN}"
create_ou "${USERS_OU}"
create_ou "OU=Service,${BASE_DN}"

create_user ivanov    "Иванов"    "Иван"    "Ведущий инженер"      "Отдел разработки"    "+7 (495) 123-45-67"
create_user petrova   "Петрова"   "Мария"   "Бухгалтер"            "Бухгалтерия"         "+7 (495) 123-45-68"
create_user sidorov   "Сидоров"   "Сидор"   "Руководитель отдела"  "Отдел разработки"    "+7 (495) 123-45-69"
create_user kuznetsov "Кузнецов"  "Алексей" "Системный администратор" "ИТ-инфраструктура" "+7 (495) 123-45-70"
create_user orlova    "Орлова"    "Анна"    "HR-менеджер"          "Кадры"               "+7 (495) 123-45-71"
create_user uvolen    "Уволенный" "Сотрудник" "Инженер"            "Отдел разработки"    "+7 (495) 123-45-72"

# samba-tool строит CN из имени и фамилии, поэтому DN достаём из каталога.
user_dn() {
    samba-tool user show "$1" 2>/dev/null | awk '/^dn: /{sub(/^dn: /, ""); print; exit}'
}

# Руководитель, мобильный, внутренний номер и отчество - через LDIF.
BOSS_DN="$(user_dn sidorov)"
counter=0
for login in ivanov petrova kuznetsov orlova uvolen; do
    dn="$(user_dn "$login")"
    [ -z "$dn" ] && continue
    counter=$((counter + 1))
    if printf 'dn: %s\nchangetype: modify\nreplace: manager\nmanager: %s\n-\nreplace: mobile\nmobile: +7 916 000-00-0%s\n-\nreplace: ipPhone\nipPhone: 10%s\n' \
        "$dn" "$BOSS_DN" "$counter" "$counter" | ldbmodify -H "$SAM_LDB" >/dev/null 2>&1; then
        echo "  атрибуты обновлены: $login"
    else
        echo "  не удалось обновить атрибуты: $login"
    fi
done

# Одну учётку отключаем - она не должна попасть в справочник.
samba-tool user disable uvolen >/dev/null 2>&1 && echo "Отключена учётка: uvolen"

# Сервисная учётка с правом чтения каталога - под ней ходит микросервис.
if ! samba-tool user show svc-contacts >/dev/null 2>&1; then
    samba-tool user create svc-contacts "$PASS" --userou="OU=Service" \
        --description="Сервисная учётка микросервиса Контакты" >/dev/null \
        && echo "Создана сервисная учётка: svc-contacts"
fi

echo
echo "Готово. Проверка:"
samba-tool user list
