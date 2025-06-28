from django.contrib.auth.models import User
from django.db import models

from apps.models import ModeloBase


# Create your models here.
class Entity(ModeloBase):
    name = models.CharField(default='', max_length=100, verbose_name='Entity')
    mision = models.TextField(default='',verbose_name='mision')
    vision = models.TextField(default='', verbose_name='vision')
    address = models.TextField(default='', verbose_name='address')
    logo = models.FileField(upload_to='logo/', null=True, blank=True)


    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = "Entity"
        verbose_name_plural = "Entities"

class AboutUsEntity(ModeloBase):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, verbose_name='Entity')
    decription = models.TextField(default='', verbose_name='Description about us')
    urlvideo = models.TextField(default='', verbose_name='Video about us')
    picturevideo = models.FileField(upload_to='images/', null=True, blank=True)


    def __str__(self):
        return f'{self.decription}'

    class Meta:
        verbose_name = "About Us"
        verbose_name_plural = "About Us"

class AboutUsDetail(ModeloBase):
    aboutus = models.ForeignKey(AboutUsEntity, on_delete=models.CASCADE, verbose_name='About Us Entity')
    title = models.TextField(default='', verbose_name='Title')
    decription = models.TextField(default='', verbose_name='Description about us')
    icon = models.CharField(default='', verbose_name='icon', max_length=100)


    def __str__(self):
        return f'{self.title} {self.decription}'

    class Meta:
        verbose_name = "About Us detail"
        verbose_name_plural = "About Us details"


class FrequentlyQuestion(ModeloBase):
    question = models.TextField(default='', verbose_name='Entity')
    answer = models.TextField(default='', verbose_name='Description about us')


    def __str__(self):
        return f'{self.question}'

    class Meta:
        verbose_name = "Frequently Question"
        verbose_name_plural = "Frequently Questions"

class Specialty(ModeloBase):
    title = models.TextField(default='', verbose_name='Title')
    description = models.TextField(default='', verbose_name='Specialty')
    image = models.FileField(upload_to='images/')


    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = "Specialty"
        verbose_name_plural = "Specialties"

class Service(ModeloBase):
    title = models.TextField(default='', verbose_name='Title')
    description = models.TextField(default='', verbose_name='Specialty')
    icon = models.CharField(default='', verbose_name='icon', max_length=100)


    def __str__(self):
        return f'{self.title}'

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"


class Country(ModeloBase):
    name = models.CharField(default='', max_length=100, verbose_name="Nombre")


    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = "Country"
        verbose_name_plural = "Countries"



class Province(ModeloBase):
    country = models.ForeignKey(Country, blank=True, null=True, verbose_name='Country', on_delete=models.CASCADE)
    name = models.CharField(default='', max_length=100, verbose_name="Name")

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = "Province"
        verbose_name_plural = "Province"



class Canton(ModeloBase):
    province = models.ForeignKey(Province, blank=True, null=True, verbose_name='Province', on_delete=models.CASCADE)
    name = models.CharField(default='', max_length=100, verbose_name="Name")

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = "Canton"
        verbose_name_plural = "Cantones"



class Parish(ModeloBase):
    canton = models.ForeignKey(Canton, blank=True, null=True, verbose_name='Canton', on_delete=models.CASCADE)
    name = models.CharField(default='', max_length=100, verbose_name='Name')


    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = "Parish"
        verbose_name_plural = "Parishes"



class Person(ModeloBase):
    SEX = (
        (1, "MASCULINO"),
        (2, "FEMENINO"),
    )
    TYPEDOCUMENT = (
        (1, "CEDULA"),
        (2, "RUC"),
        (3, "PASAPORTE"),
        (4, "PASAPORTE"),
        (5, "OTRO")
    )
    names = models.CharField(default='', max_length=100, verbose_name=u'Nombre')
    lastnames = models.CharField(default='', max_length=50, verbose_name=u"1er Apellido")
    document = models.CharField(default='', max_length=20, verbose_name=u"Cedula", blank=True)
    typedocument = models.IntegerField(default=1, choices=TYPEDOCUMENT, verbose_name="Tipo de documento")
    birthdate = models.DateField(verbose_name=u"Fecha de nacimiento o constitución")
    sexo = models.IntegerField(default=1, choices=SEX, verbose_name="Sexo")
    birthdatecountry = models.ForeignKey(Country, blank=True, null=True, related_name='birthdatecountry_set', verbose_name=u'País de nacimiento', on_delete=models.CASCADE)
    birthdateprovince = models.ForeignKey(Province, blank=True, null=True, related_name='birthdateprovince_set', verbose_name=u"Provincia de nacimiento", on_delete=models.CASCADE)
    birthdatecanton = models.ForeignKey(Canton, blank=True, null=True, related_name='birthdatecanton_set', verbose_name=u"Canton de nacimiento", on_delete=models.CASCADE)
    birthdateparish = models.ForeignKey(Parish, blank=True, null=True, related_name='birthdateparish_set', verbose_name=u"Parroquia de nacimiento", on_delete=models.CASCADE)
    nacionality = models.CharField(default='', max_length=100, verbose_name=u'Nacionalidad')
    nacinalitycountry = models.ForeignKey(Country, blank=True, null=True, related_name='nacinalitycountry_set', verbose_name=u'País de nacionalidad', on_delete=models.CASCADE)
    country = models.ForeignKey(Country, blank=True, null=True, related_name='country_set', verbose_name=u'País residencia', on_delete=models.CASCADE)
    province = models.ForeignKey(Province, blank=True, null=True, related_name='province_set', verbose_name=u"Provincia de residencia", on_delete=models.CASCADE)
    canton = models.ForeignKey(Canton, blank=True, null=True, related_name='canton_set', verbose_name=u"Canton de residencia", on_delete=models.CASCADE)
    parish = models.ForeignKey(Parish, blank=True, null=True, related_name='parish_set', verbose_name=u"Parroquia de residencia", on_delete=models.CASCADE)
    ciudadela = models.CharField(default='', max_length=300, verbose_name=u"Ciudadela",  blank=True, null=True)
    sector = models.CharField(default='', max_length=300,  blank=True, null=True, verbose_name=u"Sector de residencia")
    city = models.CharField(default='', max_length=50,  blank=True, null=True, verbose_name=u"Ciudad de residencia")
    streetaddress = models.CharField(default='', max_length=300,  blank=True, null=True, verbose_name=u"Calle principal")
    secondarystreetaddress = models.CharField(default='',  blank=True, null=True, max_length=300, verbose_name=u"Calle secundaria")
    numberstreet = models.CharField(default='', max_length=15,  blank=True, null=True, verbose_name=u"Numero")
    reference = models.CharField(default='', max_length=100,  blank=True, null=True, verbose_name=u"Referencia")
    cellphonenumber = models.CharField(default='', max_length=50, verbose_name=u"Telefono movil")
    telefonenumber = models.CharField(default='', max_length=50,  blank=True, null=True, verbose_name=u"Telefono fijo")
    email = models.CharField(default='', max_length=200, verbose_name=u"Correo electronico personal")
    emailinst = models.CharField(default='', max_length=200,  blank=True, null=True, verbose_name=u"Correo electronico institucional")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    photo = models.FileField(upload_to='photos/', blank=True, null=True)
    front_page_card = models.FileField(upload_to='front_page/', blank=True, null=True)
    front_page_profile = models.FileField(upload_to='front_page/', blank=True, null=True)

    def __str__(self):
        return f'{self.names} {self.lastnames}'

    class Meta:
        verbose_name = "Person"
        verbose_name_plural = "Persons"

    def full_name(self):
        return f'{self.names} {self.lastnames}'

    def full_residence_country(self):
        if not self.country or not self.province or not self.canton:
            return ''
        return f'{self.country.name}-{self.province.name}, {self.canton.name}'

    def get_photo(self):
        return f'{self.photo.url}' if self.photo else '/static/admin/assets/img/no-profile.png'

    def get_front_page_card(self):
        return f'{self.front_page_card.url}' if self.front_page_card else '/static/admin/assets/img/portada_no_disponible.jpg'




# Modelo para el perfil
class UserProfile(ModeloBase):
    from apps.medicalprofile.models import ProfileMedical
    from apps.patientprofile.models import ProfilePatient
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    profilemedical = models.ForeignKey(ProfileMedical, blank=True, null=True, verbose_name='Perfil personal de salud', on_delete=models.CASCADE)
    patient = models.ForeignKey(ProfilePatient, blank=True, null=True, verbose_name='Paciente', on_delete=models.CASCADE)
    # admin = models.ForeignKey(ProfileAdmin, blank=True, null=True, verbose_name=u'Empleador bolsa laboral', on_delete=models.CASCADE)
    visible = models.BooleanField(default=True, verbose_name='Visible')
    def __str__(self):
        return u'%s' % "OTRO PERFIL"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

