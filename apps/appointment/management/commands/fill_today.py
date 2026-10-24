"""
Management command: fill_today
Crea citas para todos los doctores en los turnos de HOY desde las 15:00.

Uso:
    python manage.py fill_today
    python manage.py fill_today --desde 08:00   # hora de inicio personalizada
"""
import random
from datetime import date, time, datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

FUTURE_REASONS = [
    'Control rutinario',
    'Seguimiento de tratamiento',
    'Revisión de resultados',
    'Consulta por malestar general',
    'Control de presión arterial',
    'Chequeo preventivo',
    'Revisión post-operatoria',
    'Consulta por dolor de cabeza',
    'Renovación de receta',
    'Control de diabetes',
]

DAY_MAP = {
    0: 'monday', 1: 'tuesday', 2: 'wednesday',
    3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday',
}


def _build_times(start: time, end: time, step_min: int = 30):
    times = []
    h, m = start.hour, start.minute
    while True:
        t = time(h, m)
        if t >= end:
            break
        times.append(t)
        m += step_min
        h += m // 60
        m = m % 60
        if h >= 24:
            break
    return times


class Command(BaseCommand):
    help = 'Rellena los turnos de HOY con citas para todos los doctores.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--desde',
            default='15:00',
            help='Hora de inicio (HH:MM). Por defecto: 15:00',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.medicalprofile.models import ProfileMedical, ConsultationSchedule, SpecialtyProfile
        from apps.patientprofile.models import ProfilePatient
        from apps.appointment.models import Appointment
        from apps.core.models import Specialty

        sys_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        SYS_UID = sys_user.id if sys_user else None

        # Hora de inicio
        try:
            h, m = map(int, options['desde'].split(':'))
            desde = time(h, m)
        except Exception:
            self.stderr.write('Formato de hora inválido. Usar HH:MM')
            return

        today = date.today()
        day_name = DAY_MAP[today.weekday()]

        doctors = ProfileMedical.objects.filter(status=True)
        patients = list(ProfilePatient.objects.filter(status=True))

        if not patients:
            self.stderr.write('No hay pacientes en la base de datos.')
            return

        specialty_fallback = Specialty.objects.first()

        def doctor_specialty(doctor):
            sp = SpecialtyProfile.objects.filter(
                profilemedical=doctor
            ).select_related('specialty').first()
            return sp.specialty if sp else specialty_fallback

        def slot_free(doctor, patient, t):
            doc_busy = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=today,
                appointment_time=t,
            ).exclude(status='cancelada').exists()
            pat_busy = Appointment.objects.filter(
                patient=patient,
                appointment_date=today,
                appointment_time=t,
            ).exclude(status='cancelada').exists()
            return not doc_busy and not pat_busy

        pat_idx = 0

        def next_patient():
            nonlocal pat_idx
            p = patients[pat_idx % len(patients)]
            pat_idx += 1
            return p

        created = 0
        skipped = 0

        for doctor in doctors:
            schedule = ConsultationSchedule.objects.filter(
                doctor=doctor, available_days=day_name
            ).first()
            if not schedule:
                skipped += 1
                continue

            all_times = _build_times(schedule.start_time, schedule.end_time)
            # Solo los turnos a partir de "desde"
            times = [t for t in all_times if t >= desde]
            if not times:
                skipped += 1
                continue

            specialty = doctor_specialty(doctor)

            for t in times:
                patient = next_patient()
                # Buscar un paciente libre en ese turno
                attempts = 0
                while not slot_free(doctor, patient, t) and attempts < len(patients):
                    patient = next_patient()
                    attempts += 1
                if not slot_free(doctor, patient, t):
                    continue  # todos los pacientes ocupados en ese turno

                appt = Appointment(
                    patient=patient,
                    doctor=doctor,
                    speciality=specialty,
                    consultation_schedule=schedule,
                    appointment_time=t,
                    appointment_date=today,
                    status=random.choice(['pendiente', 'confirmada']),
                    reason=random.choice(FUTURE_REASONS),
                )
                appt.save(usuario_id=SYS_UID)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {created} citas creadas desde las {options["desde"]} para hoy ({today}).'
            + (f' {skipped} doctores sin horario hoy.' if skipped else '')
        ))
