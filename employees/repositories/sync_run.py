from employees.models import SyncRun

from .base import BaseRepository


class SyncRunRepository(BaseRepository):
    model = SyncRun

    def get_queryset(self):
        return SyncRun.objects.select_related("company", "ldap_server")

    def last_successful(self, ldap_server=None):
        queryset = self.get_queryset().filter(status=SyncRun.Status.SUCCESS, dry_run=False)
        if ldap_server is not None:
            queryset = queryset.filter(ldap_server=ldap_server)
        return queryset.exclude(max_when_changed=None).order_by("-max_when_changed").first()

    def watermark(self, ldap_server=None):
        run = self.last_successful(ldap_server)
        return run.max_when_changed if run else None

    def last_finished(self):
        return self.get_queryset().filter(status=SyncRun.Status.SUCCESS).order_by("-finished_at").first()
