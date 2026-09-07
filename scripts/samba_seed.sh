#!/bin/bash
set -u

BASE_DN="${BASE_DN:-DC=corp,DC=local}"
COMPANY_NAME="${COMPANY_NAME:-ЦЦ ТЭК}"
SEED_SET="${SEED_SET:-main}"
USERS_OU="OU=Users,OU=Company,${BASE_DN}"
PASS='Passw0rd!2026'
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
        --company="$COMPANY_NAME" \
        --mail-address="${login}@$(echo "$BASE_DN" | sed 's/DC=//g; s/,/./g')" \
        --telephone-number="$phone" \
        --physical-delivery-office="Главный офис" \
        >/dev/null && echo "Создан: $login ($surname $given)"
}

user_dn() {
    samba-tool user show "$1" 2>/dev/null | awk '/^dn: /{sub(/^dn: /, ""); print; exit}'
}

create_ou "OU=Company,${BASE_DN}"
create_ou "${USERS_OU}"
create_ou "OU=Service,${BASE_DN}"

if [ "$SEED_SET" = "engs" ]; then
    BOSS_LOGIN=morozov
    create_user morozov  "Морозов"  "Виктор" "Директор"            "Дирекция"  "+7 (843) 200-10-01"
    create_user sokolov  "Соколов"  "Олег"   "Логист"            "Логистика" "+7 (843) 200-10-02"
    create_user zaytseva "Зайцева"  "Ольга"  "Менеджер"          "Продажи"   "+7 (843) 200-10-03"
    STAFF="sokolov zaytseva"
    DISABLED=zaytseva
else
    BOSS_LOGIN=sidorov
    create_user ivanov    "Иванов"    "Иван"      "Ведущий инженер"         "Отдел разработки"  "+7 (495) 123-45-67"
    create_user petrova   "Петрова"   "Мария"     "Бухгалтер"               "Бухгалтерия"       "+7 (495) 123-45-68"
    create_user sidorov   "Сидоров"   "Сидор"     "Руководитель отдела"     "Отдел разработки"  "+7 (495) 123-45-69"
    create_user kuznetsov "Кузнецов"  "Алексей"   "Системный администратор" "ИТ-инфраструктура" "+7 (495) 123-45-70"
    create_user orlova    "Орлова"    "Анна"      "HR-менеджер"             "Кадры"             "+7 (495) 123-45-71"
    create_user uvolen    "Уволенный" "Сотрудник" "Инженер"                 "Отдел разработки"  "+7 (495) 123-45-72"
    STAFF="ivanov petrova kuznetsov orlova uvolen"
    DISABLED=uvolen
fi

BOSS_DN="$(user_dn "$BOSS_LOGIN")"
counter=0
for login in $STAFF; do
    dn="$(user_dn "$login")"
    [ -z "$dn" ] && continue
    counter=$((counter + 1))
    if printf 'dn: %s\nchangetype: modify\nreplace: manager\nmanager: %s\n-\nreplace: mobile\nmobile: +7 916 000-00-0%s\n-\nreplace: ipPhone\nipPhone: 10%s\n-\nreplace: homePhone\nhomePhone: +7 916 100-20-3%s\n' \
        "$dn" "$BOSS_DN" "$counter" "$counter" "$counter" | ldbmodify -H "$SAM_LDB" >/dev/null 2>&1; then
        echo "  атрибуты обновлены: $login"
    else
        echo "  не удалось обновить атрибуты: $login"
    fi
done

for login in $BOSS_LOGIN $STAFF; do
    dn="$(user_dn "$login")"
    [ -z "$dn" ] && continue
    printf 'dn: %s\nchangetype: modify\nreplace: company\ncompany: %s\n' "$dn" "$COMPANY_NAME" \
        | ldbmodify -H "$SAM_LDB" >/dev/null 2>&1 \
        && echo "  организация проставлена: $login ($COMPANY_NAME)"
done

samba-tool user disable "$DISABLED" >/dev/null 2>&1 && echo "Отключена учётка: $DISABLED"

if ! samba-tool user show svc-contacts >/dev/null 2>&1; then
    samba-tool user create svc-contacts "$PASS" --userou="OU=Service" \
        --description="Сервисная учётка микросервиса Контакты" >/dev/null \
        && echo "Создана сервисная учётка: svc-contacts"
fi

echo
echo "Готово. Домен ${BASE_DN}:"
samba-tool user list
