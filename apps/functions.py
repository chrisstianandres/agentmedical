


def get_entity():
    from apps.core.models import Entity
    return Entity.objects.filter(status=True).only('name', 'address', 'logo').first()

def add_data_session(request, data):
    from apps.core.models import Person
    from agentmedical.settings import DEBUG
    from datetime import datetime
    if 'person' not in request.session:
        if not request.user.is_authenticated:
            raise Exception('Usuario no autentificado en el sistema')
        request.session['person'] = Person.objects.get(user=request.user)
    if not 'entity' in request.session:
        request.session['entity'] = get_entity()
    data['version_static'] = '23.0.1'
    data['person'] = request.session['person']
    data['entity'] = request.session['entity']
    data['check_session'] = False
    data['DEBUG'] = DEBUG
    if 'ultimo_acceso' not in request.session:
        request.session['ultimo_acceso'] = datetime.now()
