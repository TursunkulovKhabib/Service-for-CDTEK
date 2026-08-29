class BaseService:
    repository_class = None

    def __init__(self, repository=None):
        self.repository = repository or self.repository_class()

    def list(self, **filters):
        return self.repository.filter(**filters) if filters else self.repository.all()

    def get(self, pk):
        return self.repository.get_by_pk(pk)

    def create(self, **fields):
        return self.repository.create(**fields)

    def update(self, instance, **fields):
        return self.repository.update(instance, **fields)

    def delete(self, instance):
        return self.repository.delete(instance)

    def deactivate(self, instance):
        return instance.deactivate()

    def activate(self, instance):
        return instance.activate()
