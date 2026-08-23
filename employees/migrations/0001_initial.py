import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SyncRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('full', 'Полная'), ('incremental', 'Инкрементальная')], default='full', max_length=16, verbose_name='Режим')),
                ('status', models.CharField(choices=[('running', 'Выполняется'), ('success', 'Успешно'), ('failed', 'Ошибка')], default='running', max_length=16, verbose_name='Статус')),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Начало')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='Окончание')),
                ('changed_since', models.DateTimeField(blank=True, null=True, verbose_name='Выборка изменений с')),
                ('entries_read', models.IntegerField(default=0, verbose_name='Прочитано записей')),
                ('created', models.IntegerField(default=0, verbose_name='Создано')),
                ('updated', models.IntegerField(default=0, verbose_name='Обновлено')),
                ('unchanged', models.IntegerField(default=0, verbose_name='Без изменений')),
                ('deactivated', models.IntegerField(default=0, verbose_name='Деактивировано')),
                ('skipped', models.IntegerField(default=0, verbose_name='Пропущено')),
                ('dry_run', models.BooleanField(default=False, verbose_name='Пробный прогон')),
                ('max_when_changed', models.DateTimeField(blank=True, null=True, verbose_name='Максимальный whenChanged')),
                ('error', models.TextField(blank=True, verbose_name='Ошибка')),
            ],
            options={
                'verbose_name': 'Запуск синхронизации',
                'verbose_name_plural': 'Запуски синхронизации',
                'ordering': ('-started_at',),
            },
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_guid', models.UUIDField(db_index=True, unique=True, verbose_name='objectGUID')),
                ('sam_account_name', models.CharField(blank=True, db_index=True, max_length=128, verbose_name='sAMAccountName')),
                ('user_principal_name', models.CharField(blank=True, max_length=255, verbose_name='UPN')),
                ('distinguished_name', models.CharField(blank=True, max_length=512, verbose_name='DN')),
                ('display_name', models.CharField(blank=True, max_length=255, verbose_name='Отображаемое имя')),
                ('full_name', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='ФИО')),
                ('last_name', models.CharField(blank=True, max_length=128, verbose_name='Фамилия')),
                ('first_name', models.CharField(blank=True, max_length=128, verbose_name='Имя')),
                ('middle_name', models.CharField(blank=True, max_length=128, verbose_name='Отчество')),
                ('email', models.CharField(blank=True, db_index=True, max_length=254, verbose_name='Email')),
                ('phone', models.CharField(blank=True, max_length=64, verbose_name='Телефон')),
                ('mobile_phone', models.CharField(blank=True, max_length=64, verbose_name='Мобильный')),
                ('internal_phone', models.CharField(blank=True, max_length=32, verbose_name='Внутренний')),
                ('search_phone', models.CharField(blank=True, db_index=True, help_text='Служебное поле для поиска по номеру без форматирования.', max_length=128, verbose_name='Телефоны (цифры)')),
                ('department', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='Подразделение')),
                ('title', models.CharField(blank=True, max_length=255, verbose_name='Должность')),
                ('company', models.CharField(blank=True, db_index=True, max_length=255, verbose_name='Организация')),
                ('office', models.CharField(blank=True, max_length=255, verbose_name='Офис')),
                ('city', models.CharField(blank=True, max_length=128, verbose_name='Город')),
                ('employee_id', models.CharField(blank=True, max_length=64, verbose_name='Табельный номер')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='Описание')),
                ('manager_dn', models.CharField(blank=True, max_length=512, verbose_name='DN руководителя')),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Снимается автоматически, если учётка пропала из выдачи AD или отключена.', verbose_name='Активен')),
                ('is_hidden', models.BooleanField(default=False, help_text='Ручной флаг: сотрудник есть в AD, но не должен попадать в бота.', verbose_name='Скрыт из API')),
                ('ad_enabled', models.BooleanField(default=True, verbose_name='Учётка включена в AD')),
                ('account_control', models.IntegerField(blank=True, null=True, verbose_name='userAccountControl')),
                ('notes', models.TextField(blank=True, help_text='Заполняется вручную, синхронизация не трогает.', verbose_name='Заметки')),
                ('locked_fields', models.JSONField(blank=True, default=list, help_text='Список полей, которые синхронизация не перезаписывает, например ["phone", "title"].', verbose_name='Поля, закреплённые вручную')),
                ('when_created', models.DateTimeField(blank=True, null=True, verbose_name='Создан в AD')),
                ('when_changed', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Изменён в AD')),
                ('usn_changed', models.BigIntegerField(blank=True, null=True, verbose_name='uSNChanged')),
                ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Впервые получен')),
                ('last_synced_at', models.DateTimeField(blank=True, null=True, verbose_name='Последняя синхронизация')),
                ('deactivated_at', models.DateTimeField(blank=True, null=True, verbose_name='Деактивирован')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлён')),
                ('manager', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subordinates', to='employees.employee', verbose_name='Руководитель')),
            ],
            options={
                'verbose_name': 'Сотрудник',
                'verbose_name_plural': 'Сотрудники',
                'ordering': ('full_name', 'sam_account_name'),
                'indexes': [models.Index(fields=['department', 'full_name'], name='employees_e_departm_5af4b5_idx'), models.Index(fields=['is_active', 'is_hidden'], name='employees_e_is_acti_6a086d_idx')],
            },
        ),
    ]
