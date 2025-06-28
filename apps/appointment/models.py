from django.core.exceptions import ValidationError

from apps.models import ModeloBase
from django.db import models

class Appointment(ModeloBase):
    from apps.core.models import Specialty
    from apps.patientprofile.models import ProfilePatient
    from apps.medicalprofile.models import ProfileMedical, ConsultationSchedule
    patient = models.ForeignKey(ProfilePatient, on_delete=models.CASCADE, verbose_name="Paciente")
    doctor = models.ForeignKey(ProfileMedical, on_delete=models.CASCADE, verbose_name="Doctor")
    speciality = models.ForeignKey(Specialty, on_delete=models.CASCADE, verbose_name="Especialidad")
    consultation_schedule = models.ForeignKey(ConsultationSchedule, on_delete=models.CASCADE, verbose_name="Horario de consulta")
    appointment_time = models.TimeField(verbose_name="Hora de la cita")
    appointment_date = models.DateField(verbose_name="Fecha de la cita")

    def __str__(self):
        return f"Cita con {self.doctor} el {self.appointment_date} a las {self.appointment_time}"

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        unique_together = ['doctor', 'appointment_date', 'appointment_time']  # No se pueden tener dos citas al mismo tiempo

    def clean(self):
        # Verificar que la cita esté dentro de un horario disponible del doctor
        if not self.consultation_schedule:
            raise ValidationError("Debe seleccionar un horario de consulta válido.")
        if Appointment.objects.filter(doctor=self.doctor, appointment_date=self.appointment_date, appointment_time=self.appointment_time).exists():
            raise ValidationError("La hora de la cita ya está reservada en otra cita del doctor.")
        if not (self.consultation_schedule.start_time <= self.appointment_time < self.consultation_schedule.end_time):
            raise ValidationError("La hora de la cita no está dentro del horario de consulta del doctor.")

