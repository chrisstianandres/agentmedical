from django.db import models


from apps.models import ModeloBase

class ProfilePatient(ModeloBase):
    from apps.core.models import Person
    person = models.OneToOneField(Person, blank=True, null=True, verbose_name='Persona', on_delete=models.CASCADE)
    medical_record_number = models.CharField(max_length=20, verbose_name="Número de historia clínica", unique=True)
    diabetes = models.BooleanField(default=False, verbose_name="Diabetes")
    blood_pressure = models.CharField(max_length=50, verbose_name="Presión arterial", blank=True, null=True)
    weight = models.FloatField(verbose_name="Peso", blank=True, null=True)
    height = models.FloatField(verbose_name="Altura", blank=True, null=True)
    insurance_number = models.CharField(max_length=20, verbose_name="Número de seguro", blank=True, null=True)
    blood_group = models.CharField(max_length=10, verbose_name="Grupo sanguíneo", blank=True, null=True)
    rh_factor = models.CharField(max_length=3, verbose_name="Factor RH", blank=True, null=True)

    def __str__(self):
        return f'Paciente {self.person.full_name()}'

    class Meta:
        verbose_name = "Profile Patient"
        verbose_name_plural = "Profiles Patients"

class Alergy(ModeloBase):
    name = models.CharField(max_length=100, verbose_name="Nombre de la alergia")
    description = models.TextField(verbose_name="Descripción", blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Alergy"
        verbose_name_plural = "Alergies"


class PatientAlergy(ModeloBase):
    patient = models.ForeignKey(ProfilePatient, on_delete=models.CASCADE,  verbose_name="Paciente")
    alergy = models.ForeignKey(Alergy, on_delete=models.CASCADE, verbose_name="Alergia")

    def __str__(self):
        return f"{self.patient} tiene alergia a {self.alergy}"

    class Meta:
        verbose_name = "Patient Alergy"
        verbose_name_plural = "Patient Alergies"





class CheckPatient(ModeloBase):
    from apps.core.models import Person, Specialty
    from apps.medicalprofile.models import ProfileMedical
    pacient = models.ForeignKey(Person, on_delete=models.CASCADE, verbose_name="Paciente")
    doctor = models.ForeignKey(ProfileMedical, on_delete=models.CASCADE, verbose_name="Médico")
    speciality = models.ForeignKey(Specialty, on_delete=models.CASCADE, verbose_name="Especialidad")
    appointment_date = models.DateTimeField(verbose_name="Fecha de la consulta")
    status_check = models.CharField(max_length=20, choices=[('pendiente', 'Pendiente'), ('realizada', 'Realizada'), ('cancelada', 'Cancelada')], default='pendiente')
    snapshot = models.TextField(verbose_name="Resumen médico de la comsulta", blank=True, null=True)

    def __str__(self):
        return f"Consulta de {self.pacient} con {self.doctor} el {self.appointment_date}"

    class Meta:
        verbose_name = "Check"
        verbose_name_plural = "Checks"


class LabAnalysis(ModeloBase):
    name = models.CharField(max_length=100, verbose_name="Nombre del análisis")
    description = models.TextField(verbose_name="Descripción", blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Laboratory Analysis"
        verbose_name_plural = "Laboratory Analysis"

class PatientLabAnalysis(ModeloBase):
    patient = models.ForeignKey(ProfilePatient, on_delete=models.CASCADE, verbose_name="Paciente")
    checkpatient = models.ForeignKey(CheckPatient, on_delete=models.CASCADE, verbose_name="Consulta médica", null=True, blank=True)
    lab_analysis = models.ForeignKey(LabAnalysis, on_delete=models.CASCADE, verbose_name="Análisis de laboratorio")
    date = models.DateField(verbose_name="Fecha del análisis")

    def __str__(self):
        return f"Análisis de laboratorio de {self.patient} realizado el {self.date}"

    class Meta:
        verbose_name = "Patient Laboratories Analysis"
        verbose_name_plural = "Patients Laboratories Analysis"


class Illness(ModeloBase):
    name = models.CharField(max_length=100, verbose_name="Nombre de la enfermedad")
    description = models.TextField(verbose_name="Descripción", blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Enfermedad"
        verbose_name_plural = "Enfermedades"

class PatientIllness(ModeloBase):
    patient = models.ForeignKey(ProfilePatient, on_delete=models.CASCADE, verbose_name="Paciente")
    illness = models.ForeignKey(Illness, on_delete=models.CASCADE, verbose_name="Enfermedad")
    status_check = models.CharField(max_length=20, choices=[('padeciendo', 'Padeciendo'), ('curada', 'Curada'), ('recaida', 'Recaida')], default='padeciendo')

    def __str__(self):
        return f'{self.patient} padece - {self.illness}'

    class Meta:
        verbose_name = "Enfermedad"
        verbose_name_plural = "Enfermedades"
        
        
class PatientTherapy(ModeloBase):
    patientillnes = models.ForeignKey(PatientIllness, on_delete=models.CASCADE, verbose_name="Enfermedad")
    description = models.TextField(verbose_name="Descripción", blank=True, null=True)

    def __str__(self):
        return f'{self.patientillnes} - {self.description}'

    class Meta:
        verbose_name = "Patient Therapy"
        verbose_name_plural = "Patients Therapies"





