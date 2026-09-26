import os
from datetime import date

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agentmedical.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from apps.core.models import Person

User = get_user_model()

username = "admin"
email = "cgomezm3@gmail.com"
password = "TuClaveSegura123!"

# Persona asociada al superusuario (perfil administrativo)
person_data = {
    'names': 'Christian',
    'lastnames': 'Gomez',
    'document': '0604551580',
    'typedocument': 1,  # CEDULA
    'email': email,
    'birthdate': date(1990, 1, 1),  # Requerida por el modelo: actualizarla desde el panel
    'sexo': 1,  # MASCULINO
}

with transaction.atomic():
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create_superuser(username=username, email=email, password=password)
        print("Superusuario creado")
    else:
        print("El superusuario ya existe")

    user.first_name = person_data['names']
    user.last_name = person_data['lastnames']
    user.save(update_fields=['first_name', 'last_name'])

    # Busca la persona por cédula para que el script se pueda ejecutar varias veces
    person = Person.objects.filter(document=person_data['document']).first()
    if person is None:
        person = Person(**person_data)
        print("Persona creada")
    else:
        print("La persona ya existe")
    person.user = user
    person.save(usuario_id=user.id)

    group, _ = Group.objects.get_or_create(name='Administrativo')
    user.groups.add(group)
    print(f"Perfil administrativo asignado a {person.names} {person.lastnames} (@{user.username})")
