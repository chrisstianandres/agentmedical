from django.db import models


from apps.models import ModeloBase

class TypeProfileMedical(ModeloBase):
    name = models.CharField(default='', max_length=100, verbose_name='Nombre')


    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = "Type Profile Medical"
        verbose_name_plural = "Types Profiles Medical"


class ProfileMedical(ModeloBase):
    from apps.core.models import Person
    person = models.ForeignKey(Person, blank=True, null=True, verbose_name='Persona', on_delete=models.CASCADE)
    type = models.ForeignKey(TypeProfileMedical, blank=True, null=True, verbose_name='Tipo de perfil medico', on_delete=models.CASCADE)
    aboutme = models.TextField(default='', max_length=100, verbose_name='About me profile')
    isprincipal = models.BooleanField(default=True, verbose_name='Is principal profile')


    def __str__(self):
        return f'{self.aboutme}'

    class Meta:
        verbose_name = "Profile Medical"
        verbose_name_plural = "Profiles Medical"


class SpecialtyProfile(ModeloBase):
    from apps.core.models import Specialty
    profilemedical = models.ForeignKey(ProfileMedical, blank=True, null=True, verbose_name='Perfil medico', on_delete=models.CASCADE)
    specialty = models.ForeignKey(Specialty, blank=True, null=True, verbose_name='Especialidad de perfil medico', on_delete=models.CASCADE)
    isprincipal = models.BooleanField(default=True, verbose_name='Is principal profile')


    def __str__(self):
        return f'{self.isprincipal}'

    class Meta:
        verbose_name = "Speciality Profile Medical"
        verbose_name_plural = "Specialities Profiles Medical"


class ConsultationSchedule(models.Model):
    from apps.core.models import Person
    doctor = models.ForeignKey(ProfileMedical, on_delete=models.CASCADE, verbose_name="Doctor")
    start_time = models.TimeField(verbose_name="Hora de inicio")
    end_time = models.TimeField(verbose_name="Hora de fin")
    consultation_duration = models.DurationField(verbose_name="Duración de consulta")  # Para saber cuánto dura cada consulta
    available_days = models.CharField(
        max_length=50,
        choices=[('monday', 'Lunes'), ('tuesday', 'Martes'), ('wednesday', 'Miércoles'),
                 ('thursday', 'Jueves'), ('friday', 'Viernes'), ('saturday', 'Sábado'),
                 ('sunday', 'Domingo')],
        verbose_name="Días disponibles",
        help_text="Días de la semana en los que el doctor está disponible para consultas.",
        blank=True, null=True
    )

    def __str__(self):
        return f"{self.doctor} - {self.start_time} a {self.end_time}"

    class Meta:
        verbose_name = "Horario de consulta"
        verbose_name_plural = "Horarios de consulta"
