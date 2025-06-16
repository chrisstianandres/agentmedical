


def get_entity():
    from apps.core.models import Entity
    return Entity.objects.filter(status=True).only('name', 'address', 'logo').first()