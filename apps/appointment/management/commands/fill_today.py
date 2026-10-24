"""
Management command: fill_today
Crea citas para todos los doctores en los turnos de HOY desde las 15:00.
Los turnos ya vencidos se marcan como 'realizada' (con diagnóstico),
los vigentes como 'pendiente' o 'confirmada'.

Uso:
    python manage.py fill_today
    python manage.py fill_today --desde 08:00   # hora de inicio personalizada
"""
import random
from datetime import date, time, datetime, timedelta

from django.conf import settings
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
    'Continuar antihipertensivo. Restricción de sal. Actividad física moderada.',
    'Paracetamol 500mg c/8h por 3 días. Reposo y aislamiento relativo.',
    'Omeprazol 20mg en ayunas. Evitar picantes y frituras. Dieta blanda 5 días.',
    'Mantener hábitos saludables. Próximo chequeo en 1 año.',
    'Metformina ajustada. Dieta balanceada. Control glucémico mensual.',
    'Amoxicilina 500mg c/8h por 7 días. Salbutamol inhalador según necesidad.',
    'Seguir esquema actualizado. Control en 30 días.',
    'Diclofenaco tópico c/8h. Reposo relativo. Fisioterapia si no mejora en 1 semana.',
    'Sin medicación indicada. Mantener controles anuales.',
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
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina las citas de hoy desde --desde antes de recrearlas.',
        )

    def handle(self, *args, **options):
        try:
            h, m = map(int, options['desde'].split(':'))
            desde = time(h, m)
        except Exception:
            self.stderr.write('Formato de hora inválido. Usar HH:MM')
            return

        created, skipped = self._fill(desde, reset=options['reset'])
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {created} citas creadas desde las {options["desde"]} para hoy ({date.today()}).'
            + (f' {skipped} doctores sin horario hoy.' if skipped else '')
        ))

    @transaction.atomic
    def _fill(self, desde: time, reset: bool = False):
        from apps.medicalprofile.models import ProfileMedical, ConsultationSchedule, SpecialtyProfile
        from apps.patientprofile.models import ProfilePatient
        from apps.appointment.models import Appointment
        from apps.core.models import Specialty

        sys_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        SYS_UID = sys_user.id if sys_user else None

        now_aware = timezone.now()
        now = timezone.localtime(now_aware).replace(tzinfo=None)  # hora local Ecuador, naive
        today = now.date()
        day_name = DAY_MAP[today.weekday()]
        grace = timedelta(minutes=getattr(settings, 'APPOINTMENT_EXPIRE_GRACE_MINUTES', 120))

        if reset:
            from apps.appointment.models import Appointment as _Appt
            deleted, _ = _Appt.objects.filter(
                appointment_date=today,
                appointment_time__gte=desde,
            ).delete()


        doctors = list(ProfileMedical.objects.filter(status=True))
        patients = list(ProfilePatient.objects.filter(status=True))

        if not patients:
            raise Exception('No hay pacientes en la base de datos.')

        specialty_fallback = Specialty.objects.first()

        def doctor_specialty(doctor):
            sp = SpecialtyProfile.objects.filter(
                profilemedical=doctor
            ).select_related('specialty').first()
            return sp.specialty if sp else specialty_fallback

        def slot_free(doctor, patient, t):
            doc_busy = Appointment.objects.filter(
                doctor=doctor, appointment_date=today, appointment_time=t,
            ).exclude(status='cancelada').exists()
            pat_busy = Appointment.objects.filter(
                patient=patient, appointment_date=today, appointment_time=t,
            ).exclude(status='cancelada').exists()
            return not doc_busy and not pat_busy

        def is_expired(slot_time, duration):
            """¿Este turno ya pasó el margen de gracia de expire_appointments?"""
            slot_end = datetime.combine(today, slot_time) + (duration or timedelta(0))
            return slot_end + grace < now

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
            times = [t for t in all_times if t >= desde]
            if not times:
                skipped += 1
                continue

            specialty = doctor_specialty(doctor)
            duration = schedule.consultation_duration

            for t in times:
                patient = next_patient()
                attempts = 0
                while not slot_free(doctor, patient, t) and attempts < len(patients):
                    patient = next_patient()
                    attempts += 1
                if not slot_free(doctor, patient, t):
                    continue

                if is_expired(t, duration):
                    # Turno ya vencido: marcar como realizada con diagnóstico
                    idx = random.randint(0, len(REASONS_PAST) - 1)
                    appt = Appointment(
                        patient=patient,
                        doctor=doctor,
                        speciality=specialty,
                        consultation_schedule=schedule,
                        appointment_time=t,
                        appointment_date=today,
                        status='realizada',
                        reason=REASONS_PAST[idx],
                        diagnosis=DIAGNOSES[idx],
                        indications=INDICATIONS[idx],
                        attended_at=timezone.make_aware(datetime.combine(today, t)),
                    )
                else:
                    # Turno vigente: pendiente o confirmada
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

        return created, skipped
