"""
Management command: seed_doctors
Crea 3 doctores, sus horarios, 10 pacientes y citas médicas
(pasadas del mes anterior y futuras hasta la próxima semana).

Uso:
    python manage.py seed_doctors
    python manage.py seed_doctors --reset   # elimina y vuelve a crear
"""
import random
from datetime import date, time, timedelta, datetime

from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand
from django.db import transaction


DAY_MAP = {
    0: 'monday', 1: 'tuesday', 2: 'wednesday',
    3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday',
}

REASONS_PAST = [
    'Dolor de cabeza persistente',
    'Control de presión arterial',
    'Gripe y fiebre',
    'Dolor abdominal',
    'Revisión general anual',
    'Control y seguimiento de diabetes',
    'Infección respiratoria alta',
    'Revisión y ajuste de medicamentos',
    'Dolor muscular en miembros inferiores',
    'Chequeo preventivo',
]

DIAGNOSES = [
    'Cefalea tensional. Se recomienda hidratación, descanso y manejo del estrés.',
    'Hipertensión arterial controlada. Continuar medicación y dieta hiposódica.',
    'Síndrome gripal. Tratamiento sintomático con analgésicos y reposo.',
    'Gastritis aguda. Dieta blanda y antiácidos indicados.',
    'Paciente en buen estado general de salud. Sin hallazgos significativos.',
    'Diabetes tipo 2 compensada. Se ajusta dosis de metformina.',
    'Bronquitis aguda leve. Antibioticoterapia y broncodilatador iniciados.',
    'Esquema farmacológico actualizado según evolución clínica.',
    'Mialgia de miembros inferiores. Reposo relativo y antiinflamatorio tópico.',
    'Chequeo preventivo completado. Sin alteraciones relevantes.',
]

INDICATIONS = [
    'Hidratación abundante (2 litros/día). Reposo. Control en 2 semanas si persiste.',
    'Enalapril 10 mg c/24 h. Dieta hiposódica. Control tensión cada semana. Próximo control en 1 mes.',
    'Paracetamol 500 mg c/6 h por 3 días. Amoxicilina 500 mg c/8 h por 7 días. Reposo en casa.',
    'Omeprazol 20 mg en ayunas por 30 días. Dieta blanda. Evitar picantes y alcohol.',
    'Exámenes de rutina anuales. Actividad física regular. Próximo control en 1 año.',
    'Metformina 850 mg c/12 h con alimentos. Dieta para diabéticos. HbA1c en 3 meses.',
    'Amoxicilina-clavulánico 875 mg c/12 h por 7 días. Salbutamol 2 puff c/4-6 h SOS.',
    'Nueva formulación entregada. Cumplir pauta indicada. Traer exámenes en próximo control.',
    'Ibuprofeno 400 mg c/8 h con alimentos por 5 días. Fisioterapia si no mejora.',
    'Próximo control en 1 año. Vacunación al día. Actividad física 30 min/día.',
]

MEDICATIONS = [
    [('Paracetamol', '500 mg', 'Cada 6 horas', '3 días', 'Oral')],
    [('Enalapril', '10 mg', 'Una vez al día', 'Continuo', 'Oral'),
     ('Hidroclorotiazida', '25 mg', 'Una vez al día', 'Continuo', 'Oral')],
    [('Amoxicilina', '500 mg', 'Cada 8 horas', '7 días', 'Oral'),
     ('Paracetamol', '500 mg', 'Cada 6 horas', '3 días', 'Oral')],
    [('Omeprazol', '20 mg', 'En ayunas', '30 días', 'Oral')],
    [],
    [('Metformina', '850 mg', 'Cada 12 horas con alimentos', 'Continuo', 'Oral')],
    [('Amoxicilina-Clavulánico', '875 mg', 'Cada 12 horas', '7 días', 'Oral'),
     ('Salbutamol', '2 puff', 'Cada 4-6 horas SOS', '15 días', 'Inhalatoria')],
    [],
    [('Ibuprofeno', '400 mg', 'Cada 8 horas con alimentos', '5 días', 'Oral'),
     ('Ciclobenzaprina', '5 mg', 'Por las noches', '7 días', 'Oral')],
    [],
]

FUTURE_REASONS = [
    'Consulta de seguimiento post-tratamiento',
    'Dolor de garganta y malestar general',
    'Control de peso y presión arterial',
    'Revisión de resultados de laboratorio',
    'Dolor lumbar crónico',
    'Posible infección urinaria',
    'Chequeo anual preventivo',
    'Renovación de receta médica',
    'Revisión por cefalea recurrente',
    'Control de cicatriz post-operatoria',
]


def _build_times(start: time, end: time, step_min: int = 30):
    """Genera lista de horarios entre start y end con intervalo step_min."""
    times = []
    h, m = start.hour, start.minute
    while True:
        t = time(h, m)
        if t >= end:
            break
        times.append(t)
        m += step_min
        if m >= 60:
            h += 1
            m -= 60
        if h >= 24:
            break
    return times


class Command(BaseCommand):
    help = 'Crea 3 doctores, pacientes y citas médicas de prueba.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina los usuarios/personas/perfiles/citas creadas por este comando antes de recrearlos.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.core.models import Country, Province, Canton, Parish, Person, Specialty
        from apps.medicalprofile.models import (
            ProfileMedical, TypeProfileMedical,
            ConsultationSchedule, SpecialtyProfile,
        )
        from apps.patientprofile.models import ProfilePatient
        from apps.appointment.models import Appointment, PrescribedMedication

        DOCTOR_USERNAMES = ['rferuzola', 'hgomez', 'jolivo']
        PATIENT_USERNAMES = [
            'amartinez_p', 'jlopez_p', 'mgarcia_p', 'pmorales_p', 'lrojas_p',
            'cespinoza_p', 'svalencia_p', 'fherrera_p', 'vsalinas_p', 'dcordova_p',
        ]

        if options['reset']:
            self.stdout.write(self.style.WARNING('Eliminando datos previos...'))
            User.objects.filter(username__in=DOCTOR_USERNAMES + PATIENT_USERNAMES).delete()
            self.stdout.write('  Usuarios eliminados.')

        # ── 1. Geografía ────────────────────────────────────────────────────
        self.stdout.write('Configurando geografía...')
        country, _ = Country.objects.get_or_create(name='Ecuador')
        province, _ = Province.objects.get_or_create(
            name='Guayas', defaults={'country': country}
        )
        if not province.country_id:
            province.country = country
            Province._base_manager.filter(pk=province.pk).update(country=country)

        canton, _ = Canton.objects.get_or_create(
            name='Guayaquil', defaults={'province': province}
        )
        parish, _ = Parish.objects.get_or_create(
            name='Tarqui', defaults={'canton': canton}
        )

        # ── 2. Especialidades ────────────────────────────────────────────────
        self.stdout.write('Creando especialidades...')

        def get_or_create_specialty(title, description):
            sp = Specialty.objects.filter(title=title).first()
            if not sp:
                sp = Specialty(title=title, description=description, image='')
                sp.save(usuario_id=1)
            return sp

        specialty_general = get_or_create_specialty(
            'Medicina General',
            'Atención médica integral y preventiva. Diagnóstico y tratamiento '
            'de enfermedades comunes, control de enfermedades crónicas y '
            'promoción de la salud.',
        )
        specialty_neuro = get_or_create_specialty(
            'Neurología',
            'Diagnóstico y tratamiento de enfermedades del sistema nervioso central y '
            'periférico: epilepsia, migraña, ELA, Parkinson, esclerosis múltiple y más.',
        )
        specialty_cirugia = get_or_create_specialty(
            'Cirugía General y Oncológica',
            'Procedimientos quirúrgicos generales y oncológicos: resección de tumores, '
            'cirugía laparoscópica, manejo de cáncer de colon, estómago, mama y piel.',
        )

        # ── 3. Tipos de perfil médico ────────────────────────────────────────
        type_general, _ = TypeProfileMedical.objects.get_or_create(name='Doctor General')
        type_specialist, _ = TypeProfileMedical.objects.get_or_create(name='Médico Especialista')
        type_surgeon, _ = TypeProfileMedical.objects.get_or_create(name='Cirujano')

        # ── 4. Grupos ────────────────────────────────────────────────────────
        doctor_group, _ = Group.objects.get_or_create(name='doctor')
        patient_group, _ = Group.objects.get_or_create(name='patient')

        # ── 5. Doctores ──────────────────────────────────────────────────────
        doctors_info = [
            dict(
                username='rferuzola',
                email='rferuzola@agentmedical.com',
                names='Ruben Dario',
                lastnames='Feruzola Gomez',
                document='0912345678',
                birthdate=date(1978, 5, 15),
                sexo=1,
                cell='0991234567',
                aboutme=(
                    'Médico General con más de 18 años de trayectoria en atención '
                    'primaria y preventiva. Especializado en manejo de enfermedades '
                    'crónicas (hipertensión, diabetes), urgencias menores y medicina '
                    'familiar. Comprometido con una atención personalizada y empática.'
                ),
                years_experience=18,
                office='Consultorio 101 — Piso 1',
                price=30.00,
                type_profile=type_general,
                specialties=[specialty_general],
            ),
            dict(
                username='hgomez',
                email='hgomez@agentmedical.com',
                names='Hector Andres',
                lastnames='Gomez',
                document='0923456789',
                birthdate=date(1982, 3, 22),
                sexo=1,
                cell='0992345678',
                aboutme=(
                    'Neurólogo especialista con 12 años de experiencia en el diagnóstico '
                    'y tratamiento de enfermedades del sistema nervioso. Manejo de '
                    'epilepsia, migraña crónica, enfermedad de Parkinson, esclerosis '
                    'múltiple y neuropatías periféricas. Certificado por la Sociedad '
                    'Ecuatoriana de Neurología.'
                ),
                years_experience=12,
                office='Consultorio 102 — Piso 1',
                price=55.00,
                type_profile=type_specialist,
                specialties=[specialty_neuro],
            ),
            dict(
                username='jolivo',
                email='jolivo@agentmedical.com',
                names='Johang Mauricio',
                lastnames='Olivo Roman',
                document='0934567890',
                birthdate=date(1985, 9, 10),
                sexo=1,
                cell='0993456789',
                aboutme=(
                    'Cirujano General y Oncólogo con más de 10 años de práctica en '
                    'procedimientos laparoscópicos y oncológicos. Especialista en '
                    'resección de tumores, cirugía de cáncer colorrectal, gástrico y '
                    'de mama. Formación en oncología quirúrgica por la Universidad '
                    'Central del Ecuador. Miembro de la Sociedad Ecuatoriana de Cirugía.'
                ),
                years_experience=10,
                office='Consultorio 103 — Piso 2',
                price=70.00,
                type_profile=type_surgeon,
                specialties=[specialty_cirugia, specialty_general],
            ),
        ]

        doctor_profiles = []

        for info in doctors_info:
            user, created = User.objects.get_or_create(
                username=info['username'],
                defaults={
                    'email': info['email'],
                    'first_name': info['names'],
                    'last_name': info['lastnames'],
                    'is_active': True,
                },
            )
            if created:
                user.set_password('Doctor2024*')
                user.save()
            user.groups.add(doctor_group)

            person, _ = Person.objects.get_or_create(
                document=info['document'],
                defaults=dict(
                    names=info['names'],
                    lastnames=info['lastnames'],
                    typedocument=1,
                    birthdate=info['birthdate'],
                    sexo=info['sexo'],
                    cellphonenumber=info['cell'],
                    email=info['email'],
                    nacionality='Ecuatoriana',
                    country=country,
                    province=province,
                    canton=canton,
                    parish=parish,
                    birthdatecountry=country,
                    birthdateprovince=province,
                    birthdatecanton=canton,
                    city='Guayaquil',
                    streetaddress='Av. Francisco de Orellana',
                    secondarystreetaddress='Av. Miguel H. Alcívar',
                    numberstreet='S/N',
                    ciudadela='Kennedy Norte',
                    user=user,
                ),
            )

            profile, _ = ProfileMedical.objects.get_or_create(
                person=person,
                defaults=dict(
                    type=info['type_profile'],
                    aboutme=info['aboutme'],
                    isprincipal=True,
                    years_experience=info['years_experience'],
                    office=info['office'],
                    consultation_price=info['price'],
                ),
            )

            for i, sp in enumerate(info['specialties']):
                SpecialtyProfile.objects.get_or_create(
                    profilemedical=profile,
                    specialty=sp,
                    defaults={'isprincipal': (i == 0)},
                )

            # Horarios: Lunes–Viernes 08:00–17:00
            for day in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday'):
                ConsultationSchedule.objects.get_or_create(
                    doctor=profile,
                    available_days=day,
                    defaults=dict(
                        start_time=time(8, 0),
                        end_time=time(17, 0),
                        consultation_duration=timedelta(minutes=30),
                    ),
                )

            # Horarios: Sábado–Domingo 10:00–13:00
            for day in ('saturday', 'sunday'):
                ConsultationSchedule.objects.get_or_create(
                    doctor=profile,
                    available_days=day,
                    defaults=dict(
                        start_time=time(10, 0),
                        end_time=time(13, 0),
                        consultation_duration=timedelta(minutes=30),
                    ),
                )

            doctor_profiles.append(profile)
            self.stdout.write(
                self.style.SUCCESS(f'  Doctor: {person.full_name()} ({info["office"]})')
            )

        # ── 6. Pacientes ─────────────────────────────────────────────────────
        self.stdout.write('Creando pacientes...')

        patients_info = [
            dict(username='amartinez_p', names='Ana', lastnames='Martinez Vera',
                 document='0801234567', birthdate=date(1990, 4, 12), sexo=2,
                 cell='0980123456', email='amartinez@gmail.com',
                 weight=62.0, height=1.62, blood='O', rh='+', record='HC-001',
                 emg_name='Roberto Martinez', emg_rel='Esposo', emg_phone='0999111111'),
            dict(username='jlopez_p', names='Juan Carlos', lastnames='Lopez Reyes',
                 document='0802345678', birthdate=date(1985, 7, 25), sexo=1,
                 cell='0981234567', email='jlopez@gmail.com',
                 weight=78.5, height=1.75, blood='A', rh='+', record='HC-002',
                 emg_name='Maria Lopez', emg_rel='Madre', emg_phone='0999222222'),
            dict(username='mgarcia_p', names='Maria Elena', lastnames='Garcia Suarez',
                 document='0803456789', birthdate=date(1995, 11, 3), sexo=2,
                 cell='0982345678', email='mgarcia@gmail.com',
                 weight=55.0, height=1.58, blood='B', rh='-', record='HC-003',
                 emg_name='Carlos Garcia', emg_rel='Padre', emg_phone='0999333333'),
            dict(username='pmorales_p', names='Pedro Antonio', lastnames='Morales Castro',
                 document='0804567890', birthdate=date(1972, 2, 14), sexo=1,
                 cell='0983456789', email='pmorales@gmail.com',
                 weight=85.0, height=1.70, blood='AB', rh='+', record='HC-004',
                 emg_name='Carmen Morales', emg_rel='Esposa', emg_phone='0999444444'),
            dict(username='lrojas_p', names='Laura Beatriz', lastnames='Rojas Delgado',
                 document='0805678901', birthdate=date(1988, 9, 30), sexo=2,
                 cell='0984567890', email='lrojas@gmail.com',
                 weight=68.0, height=1.65, blood='O', rh='-', record='HC-005',
                 emg_name='Diego Rojas', emg_rel='Hermano', emg_phone='0999555555'),
            dict(username='cespinoza_p', names='Carlos Alberto', lastnames='Espinoza Abad',
                 document='0806789012', birthdate=date(1965, 6, 8), sexo=1,
                 cell='0985678901', email='cespinoza@gmail.com',
                 weight=90.0, height=1.68, blood='A', rh='-', record='HC-006',
                 emg_name='Rosa Espinoza', emg_rel='Hija', emg_phone='0999666666'),
            dict(username='svalencia_p', names='Sofia', lastnames='Valencia Torres',
                 document='0807890123', birthdate=date(2000, 1, 20), sexo=2,
                 cell='0986789012', email='svalencia@gmail.com',
                 weight=52.0, height=1.60, blood='B', rh='+', record='HC-007',
                 emg_name='Jorge Valencia', emg_rel='Padre', emg_phone='0999777777'),
            dict(username='fherrera_p', names='Felipe Eduardo', lastnames='Herrera Mena',
                 document='0808901234', birthdate=date(1978, 12, 5), sexo=1,
                 cell='0987890123', email='fherrera@gmail.com',
                 weight=75.0, height=1.72, blood='O', rh='+', record='HC-008',
                 emg_name='Lucia Herrera', emg_rel='Esposa', emg_phone='0999888888'),
            dict(username='vsalinas_p', names='Valeria', lastnames='Salinas Guaman',
                 document='0809012345', birthdate=date(1993, 8, 17), sexo=2,
                 cell='0988901234', email='vsalinas@gmail.com',
                 weight=60.0, height=1.63, blood='AB', rh='-', record='HC-009',
                 emg_name='Mario Salinas', emg_rel='Hermano', emg_phone='0999000111'),
            dict(username='dcordova_p', names='Diego Santiago', lastnames='Cordova Vega',
                 document='0810123456', birthdate=date(1982, 3, 28), sexo=1,
                 cell='0989012345', email='dcordova@gmail.com',
                 weight=82.0, height=1.78, blood='A', rh='+', record='HC-010',
                 emg_name='Patricia Cordova', emg_rel='Madre', emg_phone='0999000222'),
        ]

        patient_profiles = []

        for info in patients_info:
            user, created = User.objects.get_or_create(
                username=info['username'],
                defaults={
                    'email': info['email'],
                    'first_name': info['names'],
                    'last_name': info['lastnames'],
                    'is_active': True,
                },
            )
            if created:
                user.set_password('Paciente2024*')
                user.save()
            user.groups.add(patient_group)

            person, _ = Person.objects.get_or_create(
                document=info['document'],
                defaults=dict(
                    names=info['names'],
                    lastnames=info['lastnames'],
                    typedocument=1,
                    birthdate=info['birthdate'],
                    sexo=info['sexo'],
                    cellphonenumber=info['cell'],
                    email=info['email'],
                    nacionality='Ecuatoriana',
                    country=country,
                    province=province,
                    canton=canton,
                    parish=parish,
                    birthdatecountry=country,
                    birthdateprovince=province,
                    birthdatecanton=canton,
                    city='Guayaquil',
                    streetaddress='Calle Cuenca',
                    secondarystreetaddress='Av. 9 de Octubre',
                    numberstreet=str(random.randint(100, 999)),
                    user=user,
                ),
            )

            patient, _ = ProfilePatient.objects.get_or_create(
                medical_record_number=info['record'],
                defaults=dict(
                    person=person,
                    weight=info['weight'],
                    height=info['height'],
                    blood_group=info['blood'],
                    rh_factor=info['rh'],
                    blood_pressure='120/80 mmHg',
                    diabetes=False,
                    emergency_contact_name=info['emg_name'],
                    emergency_contact_relationship=info['emg_rel'],
                    emergency_contact_phone=info['emg_phone'],
                ),
            )
            patient_profiles.append(patient)

        self.stdout.write(
            self.style.SUCCESS(f'  {len(patient_profiles)} pacientes listos.')
        )

        # ── 7. Citas ─────────────────────────────────────────────────────────
        self.stdout.write('Creando citas médicas...')

        today = date.today()
        appt_count = 0

        # Índice rotativo de pacientes para distribuir las citas
        pat_idx = 0

        def next_patient():
            nonlocal pat_idx
            p = patient_profiles[pat_idx % len(patient_profiles)]
            pat_idx += 1
            return p

        def slot_free(doctor, patient, appt_date, appt_time):
            """Verifica que el turno no esté ocupado (sin canceladas)."""
            doc_busy = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appt_date,
                appointment_time=appt_time,
            ).exclude(status='cancelada').exists()
            pat_busy = Appointment.objects.filter(
                patient=patient,
                appointment_date=appt_date,
                appointment_time=appt_time,
            ).exclude(status='cancelada').exists()
            return not doc_busy and not pat_busy

        # Mapa doctor → especialidad principal para las citas
        def doctor_main_specialty(doctor):
            sp_profile = SpecialtyProfile.objects.filter(
                profilemedical=doctor, isprincipal=True
            ).select_related('specialty').first()
            if sp_profile:
                return sp_profile.specialty
            # fallback
            sp_profile = SpecialtyProfile.objects.filter(
                profilemedical=doctor
            ).select_related('specialty').first()
            return sp_profile.specialty if sp_profile else specialty_general

        def make_appointment(doctor, patient, appt_date, appt_time, schedule, past=True):
            nonlocal appt_count
            if not slot_free(doctor, patient, appt_date, appt_time):
                return
            doc_specialty = doctor_main_specialty(doctor)
            if past:
                idx = random.randint(0, len(REASONS_PAST) - 1)
                appt = Appointment(
                    patient=patient,
                    doctor=doctor,
                    speciality=doc_specialty,
                    consultation_schedule=schedule,
                    appointment_time=appt_time,
                    appointment_date=appt_date,
                    status='realizada',
                    reason=REASONS_PAST[idx],
                    diagnosis=DIAGNOSES[idx],
                    indications=INDICATIONS[idx],
                    attended_at=datetime.combine(appt_date, appt_time),
                )
                appt.save(usuario_id=1)
                for order, (name, dose, freq, dur, route) in enumerate(MEDICATIONS[idx]):
                    PrescribedMedication(
                        appointment=appt,
                        name=name, dose=dose, frequency=freq,
                        duration=dur, route=route, order=order,
                    ).save(usuario_id=1)
            else:
                appt = Appointment(
                    patient=patient,
                    doctor=doctor,
                    speciality=doc_specialty,
                    consultation_schedule=schedule,
                    appointment_time=appt_time,
                    appointment_date=appt_date,
                    status=random.choice(['pendiente', 'confirmada']),
                    reason=random.choice(FUTURE_REASONS),
                )
                appt.save(usuario_id=1)
            appt_count += 1

        # — Citas pasadas: primer día del mes pasado → ayer —
        last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        yesterday = today - timedelta(days=1)

        current = last_month_start
        while current <= yesterday:
            day_name = DAY_MAP[current.weekday()]
            for doctor in doctor_profiles:
                schedule = ConsultationSchedule.objects.filter(
                    doctor=doctor, available_days=day_name
                ).first()
                if not schedule:
                    continue
                times = _build_times(schedule.start_time, schedule.end_time)
                if not times:
                    continue
                # 2–4 citas por doctor por día
                n = random.randint(2, min(4, len(times)))
                chosen_times = random.sample(times, n)
                for t in chosen_times:
                    make_appointment(doctor, next_patient(), current, t, schedule, past=True)
            current += timedelta(days=1)

        # — Citas futuras: hoy → próximos 7 días —
        future_end = today + timedelta(days=7)
        current = today

        while current <= future_end:
            day_name = DAY_MAP[current.weekday()]
            for doctor in doctor_profiles:
                schedule = ConsultationSchedule.objects.filter(
                    doctor=doctor, available_days=day_name
                ).first()
                if not schedule:
                    continue
                times = _build_times(schedule.start_time, schedule.end_time)
                if not times:
                    continue
                # 2–5 citas por doctor por día
                n = random.randint(2, min(5, len(times)))
                chosen_times = random.sample(times, n)
                for t in chosen_times:
                    make_appointment(doctor, next_patient(), current, t, schedule, past=False)
            current += timedelta(days=1)

        # ── Resumen ──────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Datos creados exitosamente:'))
        self.stdout.write(f'  Doctores   : {len(doctor_profiles)}')
        self.stdout.write(f'  Pacientes  : {len(patient_profiles)}')
        self.stdout.write(f'  Citas total: {appt_count}')
        self.stdout.write('')
        self.stdout.write('Credenciales de acceso:')
        self.stdout.write('  Doctores  → contraseña: Doctor2024*')
        self.stdout.write('    rferuzola  (Ruben Dario Feruzola Gomez)')
        self.stdout.write('    hgomez     (Hector Andres Gomez)')
        self.stdout.write('    jolivo     (Johang Mauricio Olivo Roman)')
        self.stdout.write('  Pacientes → contraseña: Paciente2024*')
        self.stdout.write('    amartinez_p  jlopez_p  mgarcia_p  pmorales_p  lrojas_p')
        self.stdout.write('    cespinoza_p  svalencia_p  fherrera_p  vsalinas_p  dcordova_p')
