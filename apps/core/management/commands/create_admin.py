"""
Management command: create_admin
Crea el usuario administrador cgomez (Christian Gomez) con perfil
de administrador y paciente.

Uso:
    python manage.py create_admin
    python manage.py create_admin --reset   # elimina y recrea
"""
from datetime import date

from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Crea el usuario administrador cgomez (Christian Gomez).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina el usuario y lo vuelve a crear desde cero.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.core.models import Person, Country, Province, Canton, Parish
        from apps.patientprofile.models import ProfilePatient

        USERNAME = 'cgomez'
        PASSWORD = 'Admin2024*'
        EMAIL    = 'cgomezm3@gmail.com'

        if options['reset']:
            User.objects.filter(username=USERNAME).delete()

        # ── Grupos ───────────────────────────────────────────────────────────
        admin_group,   _ = Group.objects.get_or_create(name='Administrativo')
        patient_group, _ = Group.objects.get_or_create(name='patient')

        # ── Usuario Django ───────────────────────────────────────────────────
        user, created = User.objects.get_or_create(
            username=USERNAME,
            defaults={
                'email':      EMAIL,
                'first_name': 'Christian',
                'last_name':  'Gomez',
                'is_active':  True,
                'is_staff':   True,
                'is_superuser': True,
            },
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        else:
            # Asegurar privilegios aunque el usuario ya existiera
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.save(update_fields=['is_superuser', 'is_staff'])

        user.groups.add(admin_group, patient_group)

        # ── Geografía mínima ─────────────────────────────────────────────────
        country,  _ = Country.objects.get_or_create(name='Ecuador')
        province, _ = Province.objects.get_or_create(
            name='Guayas', defaults={'country': country}
        )
        canton,   _ = Canton.objects.get_or_create(
            name='Guayaquil', defaults={'province': province}
        )
        parish,   _ = Parish.objects.get_or_create(
            name='Tarqui', defaults={'canton': canton}
        )

        # ── Persona ───────────────────────────────────────────────────────────
        person, _ = Person.objects.get_or_create(
            document='0604551580',
            defaults=dict(
                names='Christian',
                lastnames='Gomez',
                typedocument=1,
                birthdate=date(1990, 1, 1),
                sexo=1,
                cellphonenumber='0999000000',
                email=EMAIL,
                nacionality='Ecuatoriana',
                country=country,
                province=province,
                canton=canton,
                parish=parish,
                birthdatecountry=country,
                birthdateprovince=province,
                birthdatecanton=canton,
                city='Guayaquil',
                user=user,
            ),
        )
        if person.user_id != user.id:
            person.user = user
            person.save(usuario_id=user.id)

        # ── Perfil de paciente ────────────────────────────────────────────────
        ProfilePatient.objects.get_or_create(
            person=person,
            defaults={'medical_record_number': 'HC-ADMIN-001'},
        )

        self.stdout.write(self.style.SUCCESS(
            f'Listo: @{USERNAME} creado — admin + paciente. Contraseña: {PASSWORD}'
        ))
