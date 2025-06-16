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