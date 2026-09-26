from django.core.exceptions import ValidationError

from apps.models import ModeloBase
from django.db import models

class Appointment(ModeloBase):
    from apps.core.models import Specialty
    from apps.patientprofile.models import ProfilePatient
    from apps.medicalprofile.models import ProfileMedical, ConsultationSchedule
    STATUS_PENDING = 'pendiente'
    STATUS_CONFIRMED = 'confirmada'
    STATUS_DONE = 'realizada'
    STATUS_CANCELLED = 'cancelada'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_CONFIRMED, 'Confirmada'),
        (STATUS_DONE, 'Realizada'),
        (STATUS_CANCELLED, 'Cancelada'),
    ]
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED)
    CANCELLED_BY_PATIENT = 'paciente'
    CANCELLED_BY_DOCTOR = 'medico'
    CANCELLED_BY_SYSTEM = 'sistema'
    CANCELLED_BY_ADMIN = 'administrativo'
    CANCELLED_BY_CHOICES = [
        (CANCELLED_BY_PATIENT, 'Paciente'),
        (CANCELLED_BY_DOCTOR, 'Médico'),
        (CANCELLED_BY_SYSTEM, 'Sistema'),
        (CANCELLED_BY_ADMIN, 'Administrativo'),
    ]

    patient = models.ForeignKey(ProfilePatient, on_delete=models.CASCADE, verbose_name="Paciente")
    doctor = models.ForeignKey(ProfileMedical, on_delete=models.CASCADE, verbose_name="Doctor")
    speciality = models.ForeignKey(Specialty, on_delete=models.CASCADE, verbose_name="Especialidad")
    consultation_schedule = models.ForeignKey(ConsultationSchedule, on_delete=models.CASCADE, verbose_name="Horario de consulta")
    appointment_time = models.TimeField(verbose_name="Hora de la cita")
    appointment_date = models.DateField(verbose_name="Fecha de la cita")
    # Reemplaza el booleano heredado de ModeloBase por el estado de la cita
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Estado")
    reason = models.TextField(blank=True, null=True, verbose_name="Motivo de la consulta")
    diagnosis = models.TextField(blank=True, null=True, verbose_name="Diagnóstico")
    indications = models.TextField(blank=True, null=True, verbose_name="Indicaciones")
    attended_at = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de atención")
    cancel_reason = models.CharField(max_length=255, blank=True, default='', verbose_name="Motivo de cancelación")
    cancelled_by = models.CharField(max_length=20, choices=CANCELLED_BY_CHOICES, blank=True, default='', verbose_name="Cancelada por")

    def __str__(self):
        return f"Cita con {self.doctor} el {self.appointment_date} a las {self.appointment_time}"

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"

    def clean(self):
        # Verificar que la cita esté dentro de un horario disponible del doctor
        if not self.consultation_schedule_id:
            raise ValidationError("Debe seleccionar un horario de consulta válido.")
        if self.status != self.STATUS_CANCELLED:
            # Las citas canceladas liberan el turno
            duplicates = Appointment.objects.filter(doctor_id=self.doctor_id, appointment_date=self.appointment_date,
                                                    appointment_time=self.appointment_time).exclude(status=self.STATUS_CANCELLED)
            if self.pk:
                duplicates = duplicates.exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError("La hora de la cita ya está reservada en otra cita del doctor.")
        if not (self.consultation_schedule.start_time <= self.appointment_time < self.consultation_schedule.end_time):
            raise ValidationError("La hora de la cita no está dentro del horario de consulta del doctor.")


class PrescribedMedication(ModeloBase):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='medications', verbose_name="Cita")
    name = models.CharField(max_length=150, verbose_name="Medicamento")
    dose = models.CharField(max_length=100, verbose_name="Dosis")
    frequency = models.CharField(max_length=100, verbose_name="Frecuencia")
    duration = models.CharField(max_length=100, blank=True, default='', verbose_name="Duración")
    route = models.CharField(max_length=50, blank=True, default='', verbose_name="Vía de administración")
    instructions = models.CharField(max_length=255, blank=True, default='', verbose_name="Indicaciones")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Orden")

    def __str__(self):
        return f"{self.name} {self.dose} - {self.frequency}"

    class Meta:
        verbose_name = "Medicamento prescrito"
        verbose_name_plural = "Medicamentos prescritos"
        ordering = ['order', 'id']
