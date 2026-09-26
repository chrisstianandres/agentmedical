from datetime import datetime, timedelta
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator

from apps.appointment.functions import expire_appointments
from apps.functions import add_data_session


# Create your views here.
# -*- coding: UTF-8 -*-

# Independiente del locale del servidor (strftime('%A') cambia con el idioma)
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
WEEKDAY_LABELS = {'monday': 'Lunes', 'tuesday': 'Martes', 'wednesday': 'Miércoles', 'thursday': 'Jueves',
                  'friday': 'Viernes', 'saturday': 'Sábado', 'sunday': 'Domingo'}
DURATION_CHOICES = [15, 20, 30, 45, 60]
DOCTOR_ACTIONS = ('doctorprofile', 'savedoctorprofile', 'doctorschedule', 'addschedule', 'editschedule', 'deleteschedule',
                  'doctorappointments', 'doctorappointmentdetail', 'confirmappointment', 'saveresult', 'followupappointment',
                  'doctorcancelappointment')
PATIENT_ACTIONS = ('appointment', 'myappointments', 'directory', 'profile', 'editprofile', 'addappointment',
                   'cancelappointment', 'rescheduleappointment', 'profileedit', 'savepersonal', 'savecontact',
                   'savemedical', 'savealergies')
CONTACT_TEXT_FIELDS = ('cellphonenumber', 'telefonenumber', 'city', 'ciudadela', 'sector', 'streetaddress',
                       'secondarystreetaddress', 'numberstreet', 'reference')
BLOOD_GROUP_CHOICES = ['A', 'B', 'AB', 'O']
RH_CHOICES = ['+', '-']
ADMIN_ACTIONS = ('adminpersons', 'adminpersonform', 'adminsaveperson', 'searchpatients', 'adminappointments',
                 'adminnewappointment', 'adminaddappointment', 'adminconfirmappointment', 'adminrescheduleappointment',
                 'admincancelappointment')
ADMIN_JSON_GET_ACTIONS = ('searchpatients',)
PROFILE_HOME = {'patient': '/panel?action=appointment', 'doctor': '/panel?action=doctorappointments',
                'admin': '/panel?action=adminappointments'}
PROFILE_LABELS = {'patient': 'paciente', 'doctor': 'médico', 'admin': 'administrativo'}
ROLE_DENIED = {'doctor': 'Esta opción es solo para personal médico.', 'admin': 'Esta opción es solo para personal administrativo.'}
DOCTOR_GROUP = 'Medico'
ADMIN_GROUP = 'Administrativo'
PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
PHOTO_MAX_SIZE = 5 * 1024 * 1024


def get_doctor(person):
    """ Perfil médico activo de la persona o None """
    from apps.medicalprofile.models import ProfileMedical
    return ProfileMedical.objects.filter(status=True, person_id=person.id).first()


def can_be_doctor(request):
    return bool(get_doctor(request.session['person'])) or request.user.groups.filter(name=DOCTOR_GROUP).exists()


def must_change_password(person):
    """ Se lee de la BD: la persona en sesión puede estar desactualizada tras un restablecimiento """
    from apps.core.models import Person
    return Person.objects.filter(id=person.id, must_change_password=True).exists()


def can_be_admin(request):
    return request.user.is_superuser or request.user.groups.filter(name=ADMIN_GROUP).exists()


def available_profiles(request):
    """ Perfiles que puede usar el usuario en sesión, en orden de menú """
    profiles = ['patient']
    if can_be_doctor(request):
        profiles.append('doctor')
    if can_be_admin(request):
        profiles.append('admin')
    return profiles


def can_use_profile(request, profile):
    return profile == 'patient' or (profile == 'doctor' and can_be_doctor(request)) or (profile == 'admin' and can_be_admin(request))


def update_person_contact(request, person):
    """ Aplica teléfono, email y foto opcional del POST a la persona (sin guardar) """
    cellphonenumber = request.POST.get('cellphonenumber', '').strip()
    email = request.POST.get('email', '').strip()
    if not cellphonenumber:
        raise NameError('Debe ingresar un teléfono móvil')
    try:
        validate_email(email)
    except ValidationError:
        raise NameError('Debe ingresar un correo electrónico válido')
    person.cellphonenumber = cellphonenumber
    person.email = email
    apply_photo(request, person)


def apply_photo(request, person):
    """ Valida y asigna la foto opcional del POST a la persona (sin guardar) """
    photo = request.FILES.get('photo')
    if photo:
        if not photo.name.lower().endswith(PHOTO_EXTENSIONS):
            raise NameError('La foto debe ser una imagen JPG, PNG o WEBP')
        if photo.size > PHOTO_MAX_SIZE:
            raise NameError('La foto no debe superar los 5 MB')
        person.photo = photo


def clip(request, model, field):
    """ Texto del POST sin espacios y recortado al max_length del campo """
    return request.POST.get(field, '').strip()[:model._meta.get_field(field).max_length]


def parse_number(request, field, label, minimum, maximum):
    """ Número decimal opcional del POST dentro de [minimum, maximum]; vacío → None """
    raw = request.POST.get(field, '').strip().replace(',', '.')
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        raise NameError(f'{label} debe ser un número')
    if not minimum <= value <= maximum:
        raise NameError(f'{label} debe estar entre {minimum} y {maximum}')
    return value


def resolve_location(request, model, field, invalid_message, parent_field=None, parent=None, missing_parent_message=None):
    """ FK de ubicación del POST validando que pertenece al nivel superior; vacío → None """
    value = request.POST.get(field, '').strip()
    if not value:
        return None
    if parent_field and parent is None:
        raise NameError(missing_parent_message)
    filters = {'status': True, 'id': value if value.isdigit() else 0}
    if parent_field:
        filters[parent_field] = parent
    instance = model.objects.filter(**filters).first()
    if not instance:
        raise NameError(invalid_message)
    return instance


def location_results(queryset):
    return JsonResponse({"results": [{'id': item.id, 'text': item.name} for item in queryset.filter(status=True).order_by('name')]})


def apply_personal(request, person):
    """ Valida y asigna los datos personales del POST (incluida la foto) a la persona, sin guardar """
    from apps.core.models import Person
    names = clip(request, Person, 'names')
    lastnames = clip(request, Person, 'lastnames')
    document = clip(request, Person, 'document')
    if not names or not lastnames:
        raise NameError('Debe ingresar nombres y apellidos')
    typedocument = request.POST.get('typedocument', '')
    if not typedocument.isdigit() or int(typedocument) not in dict(Person.TYPEDOCUMENT):
        raise NameError('Tipo de documento no válido')
    typedocument = int(typedocument)
    if not document:
        raise NameError('Debe ingresar el número de documento')
    if typedocument == 1 and not (document.isdigit() and len(document) == 10):
        raise NameError('La cédula debe tener 10 dígitos')
    if Person.objects.filter(document=document).exclude(id=person.id).exists():
        raise NameError('El número de documento ya está registrado por otra persona')
    birthdate = parse_date(request.POST.get('birthdate'))
    today = datetime.now().date()
    if birthdate > today:
        raise NameError('La fecha de nacimiento no puede ser futura')
    if today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day)) > 120:
        raise NameError('La fecha de nacimiento no es válida (edad máxima 120 años)')
    sexo = request.POST.get('sexo', '')
    if not sexo.isdigit() or int(sexo) not in dict(Person.SEX):
        raise NameError('Sexo no válido')
    person.names = names
    person.lastnames = lastnames
    person.typedocument = typedocument
    person.document = document
    person.birthdate = birthdate
    person.sexo = int(sexo)
    person.nacionality = clip(request, Person, 'nacionality')
    apply_photo(request, person)


def apply_contact(request, person, text_fields, with_emailinst=False):
    """ Valida y asigna email, ubicación jerárquica y los textos indicados del POST, sin guardar """
    from apps.core.models import Person, Country, Province, Canton, Parish
    email = clip(request, Person, 'email')
    try:
        validate_email(email)
    except ValidationError:
        raise NameError('Debe ingresar un correo electrónico personal válido')
    if with_emailinst:
        emailinst = clip(request, Person, 'emailinst')
        if emailinst:
            try:
                validate_email(emailinst)
            except ValidationError:
                raise NameError('El correo electrónico institucional no es válido')
        person.emailinst = emailinst
    country = resolve_location(request, Country, 'country', 'El país seleccionado no existe')
    province = resolve_location(request, Province, 'province', 'La provincia no pertenece al país seleccionado',
                                'country', country, 'Debe elegir el país antes de la provincia')
    canton = resolve_location(request, Canton, 'canton', 'El cantón no pertenece a la provincia seleccionada',
                              'province', province, 'Debe elegir la provincia antes del cantón')
    parish = resolve_location(request, Parish, 'parish', 'La parroquia no pertenece al cantón seleccionado',
                              'canton', canton, 'Debe elegir el cantón antes de la parroquia')
    person.email = email
    person.country, person.province, person.canton, person.parish = country, province, canton, parish
    for field in text_fields:
        setattr(person, field, clip(request, Person, field))


def parse_specialities(request):
    """ Especialidades activas elegidas en el POST (al menos una) """
    from apps.core.models import Specialty
    speciality_ids = [value for value in request.POST.getlist('specialities') if value.isdigit()]
    specialities = list(Specialty.objects.filter(status=True, id__in=speciality_ids))
    if not specialities:
        raise NameError('Debe elegir al menos una especialidad')
    return specialities


def sync_specialities(request, doctor, specialities):
    """ Reactiva o crea las especialidades elegidas del doctor y desactiva las quitadas """
    from apps.medicalprofile.models import SpecialtyProfile
    chosen = {specialty.id for specialty in specialities}
    seen = set()
    for profile in SpecialtyProfile.objects.filter(profilemedical=doctor).order_by('id'):
        active = profile.specialty_id in chosen and profile.specialty_id not in seen
        seen.add(profile.specialty_id)
        if profile.status != active:
            profile.status = active
            profile.save(request)
    for specialty in specialities:
        if specialty.id not in seen:
            SpecialtyProfile(profilemedical=doctor, specialty=specialty, isprincipal=False).save(request)


def future_appointments(schedule):
    """ Citas no canceladas desde ahora ligadas al horario """
    from apps.appointment.models import Appointment
    now = datetime.now()
    return Appointment.objects.filter(consultation_schedule=schedule).exclude(status=Appointment.STATUS_CANCELLED).filter(
        Q(appointment_date__gt=now.date()) | Q(appointment_date=now.date(), appointment_time__gte=now.time()))


def slots_count(start_time, end_time, duration):
    if not duration or duration <= timedelta(0):
        return 0
    total = datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)
    return max(int(total // duration), 0)


def parse_schedule_post(request):
    """ start_time, end_time y duración (timedelta) validados del POST """
    start_time = parse_time(request.POST.get('start_time'))
    end_time = parse_time(request.POST.get('end_time'))
    if start_time >= end_time:
        raise NameError('La hora de inicio debe ser menor que la hora de fin')
    try:
        minutes = int(request.POST.get('duration', ''))
    except ValueError:
        raise NameError('La duración debe ser un número de minutos')
    span = datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)
    if minutes < 5 or timedelta(minutes=minutes) > span:
        raise NameError('La duración debe ser de al menos 5 minutos y no superar el rango del horario')
    return start_time, end_time, timedelta(minutes=minutes)


def check_schedule_overlap(doctor, day, start_time, end_time, exclude_id=None):
    from apps.medicalprofile.models import ConsultationSchedule
    overlaps = ConsultationSchedule.objects.filter(doctor=doctor, available_days=day, start_time__lt=end_time, end_time__gt=start_time)
    if exclude_id:
        overlaps = overlaps.exclude(id=exclude_id)
    overlap = overlaps.order_by('start_time').first()
    if overlap:
        raise NameError(f"El horario se solapa el {WEEKDAY_LABELS[day]} con {overlap.start_time.strftime('%H:%M')}-{overlap.end_time.strftime('%H:%M')}")


def get_doctor_schedule(request, data):
    """ Horario del doctor en sesión validando que le pertenece y no tiene citas futuras """
    from apps.medicalprofile.models import ConsultationSchedule
    doctor = get_doctor(data['person'])
    if not doctor:
        raise NameError('Primero crea tu perfil médico')
    schedule = ConsultationSchedule.objects.filter(id=request.POST.get('id') or 0, doctor=doctor).first()
    if not schedule:
        raise NameError('El horario no existe')
    pending = future_appointments(schedule).count()
    if pending:
        raise NameError(f'Tiene {pending} citas futuras en este horario; cancélelas o reagéndelas primero.')
    return doctor, schedule


def get_patient(person, create=False, request=None):
    """ Perfil de paciente activo de la persona; opcionalmente lo crea o reactiva """
    from apps.patientprofile.models import ProfilePatient
    patient = ProfilePatient.objects.filter(person_id=person.id).first()
    if patient and patient.status:
        return patient
    if not create:
        return None
    if patient:
        # OneToOne con Person: se reactiva el perfil dado de baja en lugar de crear otro
        patient.status = True
        patient.save(request)
        return patient
    number = f"HC-{person.id:06d}"
    suffix = 1
    while ProfilePatient.objects.filter(medical_record_number=number).exists():
        number = f"HC-{person.id:06d}-{suffix}"
        suffix += 1
    patient = ProfilePatient(person_id=person.id, medical_record_number=number)
    patient.save(request)
    return patient


def appointment_querysets(patient):
    """ Citas del paciente separadas en próximas, historial y canceladas """
    from apps.appointment.models import Appointment
    today = datetime.now().date()
    base = Appointment.objects.filter(patient=patient) if patient else Appointment.objects.none()
    base = base.select_related('doctor__person', 'speciality').prefetch_related('medications')
    upcoming = base.filter(appointment_date__gte=today, status__in=Appointment.ACTIVE_STATUSES).order_by('appointment_date', 'appointment_time')
    history = base.filter(Q(status=Appointment.STATUS_DONE) | (Q(appointment_date__lt=today) & ~Q(status=Appointment.STATUS_CANCELLED))).order_by('-appointment_date', '-appointment_time')
    cancelled = base.filter(status=Appointment.STATUS_CANCELLED).order_by('-appointment_date', '-appointment_time')
    return {'upcoming': upcoming, 'history': history, 'cancelled': cancelled}


def doctor_appointment_querysets(doctor):
    """ Citas del doctor separadas en hoy, próximas, historial y canceladas """
    from apps.appointment.models import Appointment
    today = datetime.now().date()
    base = Appointment.objects.filter(doctor=doctor) if doctor else Appointment.objects.none()
    return appointment_tab_querysets(base.select_related('patient__person', 'speciality').prefetch_related('medications'))


def appointment_tab_querysets(base):
    """ Pestañas hoy / próximas / historial / canceladas sobre un queryset de citas """
    from apps.appointment.models import Appointment
    today = datetime.now().date()
    return {
        'today': base.filter(appointment_date=today).exclude(status=Appointment.STATUS_CANCELLED).order_by('appointment_time'),
        'upcoming': base.filter(appointment_date__gt=today, status__in=Appointment.ACTIVE_STATUSES).order_by('appointment_date', 'appointment_time'),
        'history': base.filter(Q(status=Appointment.STATUS_DONE) | (Q(appointment_date__lt=today) & ~Q(status=Appointment.STATUS_CANCELLED))).order_by('-appointment_date', '-appointment_time'),
        'cancelled': base.filter(status=Appointment.STATUS_CANCELLED).order_by('-appointment_date', '-appointment_time'),
    }


def get_active_profile(request):
    """ Perfil activo en sesión ('patient' | 'doctor' | 'admin'); lo inicializa si falta o ya no es válido """
    profile = request.session.get('active_profile')
    if profile in PROFILE_HOME and can_use_profile(request, profile):
        return profile
    if can_be_admin(request):
        profile = 'admin'
    else:
        profile = 'patient'
        if can_be_doctor(request):
            patient = get_patient(request.session['person'])
            if not (patient and patient.appointment_set.exists()):
                profile = 'doctor'
    request.session['active_profile'] = profile
    return profile


def required_profile(action):
    if action in PATIENT_ACTIONS:
        return 'patient'
    if action in DOCTOR_ACTIONS:
        return 'doctor'
    if action in ADMIN_ACTIONS:
        return 'admin'
    return None


def get_doctor_appointment(request, data, appointment_id):
    """ Cita del doctor en sesión o NameError """
    from apps.appointment.models import Appointment
    doctor = get_doctor(data['person'])
    if not doctor:
        raise NameError('Primero crea tu perfil médico')
    appointment = Appointment.objects.select_related('patient__person', 'speciality', 'doctor__person').filter(
        id=appointment_id if str(appointment_id or '').isdigit() else 0, doctor=doctor).first()
    if not appointment:
        raise NameError('La cita no existe')
    return doctor, appointment


MEDICATION_FIELDS = (('name', 150, 'el nombre'), ('dose', 100, 'la dosis'), ('frequency', 100, 'la frecuencia'),
                     ('duration', 100, None), ('route', 50, None), ('instructions', 255, None))
MEDICATIONS_MAX = 30


def parse_medications(raw):
    """ Lista JSON de medicamentos validada y recortada; NameError con el número de ítem si falla """
    import json
    try:
        items = json.loads(raw or '[]')
    except ValueError:
        raise NameError('La lista de medicamentos no es un JSON válido')
    if not isinstance(items, list):
        raise NameError('La lista de medicamentos no es un JSON válido')
    if len(items) > MEDICATIONS_MAX:
        raise NameError(f'No se pueden prescribir más de {MEDICATIONS_MAX} medicamentos')
    medications = []
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise NameError(f'Medicamento {number}: formato inválido')
        medication = {}
        for field, max_length, required in MEDICATION_FIELDS:
            value = str(item.get(field) or '').strip()[:max_length]
            if required and not value:
                raise NameError(f'Medicamento {number}: falta {required}')
            medication[field] = value
        medications.append(medication)
    return medications


def can_record_result(appointment):
    return appointment.status != appointment.STATUS_CANCELLED and appointment.appointment_date <= datetime.now().date()


def add_panel_data(request, data, action, title):
    """ Contexto común de las vistas HTML del panel (título, acción, perfil activo y badges del sidebar) """
    data['title'] = title
    data['action'] = action
    data['available_profiles'] = available_profiles(request)
    data['can_switch'] = len(data['available_profiles']) > 1
    data['is_doctor'] = 'doctor' in data['available_profiles']
    data['is_admin'] = 'admin' in data['available_profiles']
    data['active_profile'] = get_active_profile(request)
    data['doctor'] = get_doctor(data['person'])
    patient = get_patient(data['person'])
    data['counts_upcoming'] = 0
    data['counts_doctor_today'] = 0
    if data['active_profile'] == 'patient' and patient:
        data['counts_upcoming'] = appointment_querysets(patient)['upcoming'].count()
    if data['active_profile'] == 'doctor' and data['doctor']:
        data['counts_doctor_today'] = doctor_appointment_querysets(data['doctor'])['today'].count()
    # Cabecera que distingue el perfil activo
    person = data['person']
    data['header_photo'] = person.get_photo()
    if data['active_profile'] == 'doctor':
        data['header_name'] = f"{'Dra.' if person.sexo == 2 else 'Dr.'} {person.full_name()}"
        data['header_role'] = 'Médico'
        specialities = data['doctor'].specialtyprofile_set.filter(status=True).values_list('specialty__title', flat=True) if data['doctor'] else []
        data['header_detail'] = ' · '.join(specialities) or 'Perfil médico sin completar'
    elif data['active_profile'] == 'admin':
        data['header_name'] = person.full_name()
        data['header_role'] = 'Administrativo'
        data['header_detail'] = 'Gestión del centro médico'
    else:
        data['header_name'] = person.full_name()
        data['header_role'] = 'Paciente'
        record = patient.medical_record_number if patient else ''
        # Los números generados ya empiezan por "HC-": no duplicar el prefijo
        data['header_detail'] = (record if record.upper().startswith('HC') else f"HC {record}") if record else 'Paciente'
    return patient


def parse_date(value):
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        raise NameError('La fecha debe tener el formato YYYY-MM-DD')


def parse_time(value):
    try:
        return datetime.strptime(value or '', '%H:%M').time()
    except ValueError:
        raise NameError('La hora debe tener el formato HH:MM')


def time_label(value):
    hour = value.hour % 12 or 12
    return f"{hour:02d}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def free_slots(doctor_id, date, exclude_appointment_id=None):
    """ Turnos libres (time, ConsultationSchedule) del doctor en la fecha dada """
    from apps.appointment.models import Appointment
    from apps.medicalprofile.models import ConsultationSchedule
    schedules = ConsultationSchedule.objects.filter(doctor_id=doctor_id, available_days=WEEKDAYS[date.weekday()]).order_by('start_time')
    busy = Appointment.objects.filter(doctor_id=doctor_id, appointment_date=date).exclude(status=Appointment.STATUS_CANCELLED)
    if exclude_appointment_id:
        busy = busy.exclude(id=exclude_appointment_id)
    busy = set(busy.values_list('appointment_time', flat=True))
    now = datetime.now()
    slots = {}
    for schedule in schedules:
        if not schedule.consultation_duration or schedule.consultation_duration <= timedelta(0):
            continue
        current = datetime.combine(date, schedule.start_time)
        end = datetime.combine(date, schedule.end_time)
        while current + schedule.consultation_duration <= end:
            slot = current.time()
            if slot not in busy and slot not in slots and (date != now.date() or current > now):
                slots[slot] = schedule
            current += schedule.consultation_duration
    return sorted(slots.items(), key=lambda item: item[0])


@login_required(redirect_field_name='ret', login_url='/login')
# @secure_module
# @last_access
@transaction.atomic()
def view(request):
    data = {}
    #
    add_data_session(request, data)
    data['person'] = request.session['person']
    expire_appointments()
    if must_change_password(data['person']):
        # Contraseña temporal generada por el administrativo: nada del panel hasta cambiarla
        if request.method == 'POST':
            return JsonResponse({"result": "bad", "mensaje": "Debe cambiar su contraseña antes de continuar."})
        return HttpResponseRedirect('/password_change?forced=1')
    if request.method == 'POST':
        action = request.POST.get('action', '')
        required = required_profile(action)
        if required in ROLE_DENIED and not can_use_profile(request, required):
            return JsonResponse({"result": "bad", "mensaje": ROLE_DENIED[required]})
        if required and get_active_profile(request) != required:
            return JsonResponse({"result": "bad", "mensaje": f"Cambie al perfil {PROFILE_LABELS[required]} para usar esta opción."})
        if required == 'admin':
            from apps.core.admin_panel import admin_post
            return admin_post(request, data, action)

        if action == 'addappointment':
            try:
                from apps.appointment.models import Appointment
                from apps.core.models import Specialty
                from apps.medicalprofile.models import ProfileMedical
                speciality = Specialty.objects.filter(status=True, id=request.POST.get('speciality') or 0).first()
                if not speciality:
                    raise NameError('Debe elegir una especialidad')
                doctor = ProfileMedical.objects.filter(status=True, id=request.POST.get('doctor') or 0,
                                                       specialtyprofile__status=True, specialtyprofile__specialty=speciality).select_related('person').first()
                if not doctor:
                    raise NameError('Debe elegir un doctor de la especialidad seleccionada')
                if doctor.person_id == data['person'].id:
                    raise NameError('No puede reservar una cita consigo mismo.')
                date = parse_date(request.POST.get('date'))
                time = parse_time(request.POST.get('time'))
                schedule = dict(free_slots(doctor.id, date)).get(time)
                if not schedule:
                    raise NameError('El turno seleccionado no está disponible')
                patient = get_patient(data['person'], create=True, request=request)
                appointment = Appointment(patient=patient, doctor=doctor, speciality=speciality, consultation_schedule=schedule,
                                          appointment_date=date, appointment_time=time, reason=request.POST.get('reason', '').strip() or None)
                appointment.full_clean()
                appointment.save(request)
                return JsonResponse({"result": "ok", "data": {"doctor": doctor.person.full_name(), "specialty": speciality.title,
                                                              "date": date.strftime('%Y-%m-%d'), "time": time.strftime('%H:%M'), "office": doctor.office}})
            except ValidationError as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": ' '.join(ex.messages)})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'cancelappointment':
            try:
                from apps.appointment.models import Appointment
                patient = get_patient(data['person'])
                appointment = Appointment.objects.filter(id=request.POST.get('id') or 0, patient=patient).first() if patient else None
                if not appointment:
                    raise NameError('La cita no existe')
                if appointment.status not in Appointment.ACTIVE_STATUSES:
                    raise NameError('Solo se pueden cancelar citas pendientes o confirmadas')
                appointment.status = Appointment.STATUS_CANCELLED
                appointment.cancelled_by = Appointment.CANCELLED_BY_PATIENT
                appointment.cancel_reason = request.POST.get('reason', '').strip()[:255]
                appointment.save(request)
                return JsonResponse({"result": "ok", "mensaje": "Cita cancelada correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'rescheduleappointment':
            try:
                from apps.appointment.models import Appointment
                patient = get_patient(data['person'])
                appointment = Appointment.objects.filter(id=request.POST.get('id') or 0, patient=patient).first() if patient else None
                if not appointment:
                    raise NameError('La cita no existe')
                if appointment.status not in Appointment.ACTIVE_STATUSES:
                    raise NameError('Solo se pueden reprogramar citas pendientes o confirmadas')
                date = parse_date(request.POST.get('date'))
                time = parse_time(request.POST.get('time'))
                schedule = dict(free_slots(appointment.doctor_id, date, exclude_appointment_id=appointment.id)).get(time)
                if not schedule:
                    raise NameError('El turno seleccionado no está disponible')
                appointment.appointment_date = date
                appointment.appointment_time = time
                appointment.consultation_schedule = schedule
                appointment.full_clean()
                appointment.save(request)
                return JsonResponse({"result": "ok", "mensaje": "Cita reprogramada correctamente"})
            except ValidationError as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": ' '.join(ex.messages)})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'editprofile':
            try:
                from apps.core.models import Person
                person = Person.objects.get(id=data['person'].id)
                update_person_contact(request, person)
                person.save(request)
                request.session['person'] = person
                return JsonResponse({"result": "ok", "mensaje": "Perfil actualizado correctamente",
                                     "data": {"cellphonenumber": person.cellphonenumber, "email": person.email, "photo": person.get_photo()}})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'savepersonal':
            try:
                from apps.core.models import Person
                person = Person.objects.get(id=data['person'].id)
                apply_personal(request, person)
                person.save(request)
                request.session['person'] = person
                return JsonResponse({"result": "ok", "mensaje": "Datos personales actualizados correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'savecontact':
            try:
                from apps.core.models import Person
                person = Person.objects.get(id=data['person'].id)
                apply_contact(request, person, CONTACT_TEXT_FIELDS, with_emailinst=True)
                person.save(request)
                request.session['person'] = person
                return JsonResponse({"result": "ok", "mensaje": "Datos de contacto actualizados correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'savemedical':
            try:
                from apps.core.models import Person
                from apps.patientprofile.models import ProfilePatient
                blood_group = request.POST.get('blood_group', '').strip().upper()
                rh_factor = request.POST.get('rh_factor', '').strip()
                if blood_group and blood_group not in BLOOD_GROUP_CHOICES:
                    raise NameError('Grupo sanguíneo no válido')
                if rh_factor and rh_factor not in RH_CHOICES:
                    raise NameError('Factor RH no válido')
                weight = parse_number(request, 'weight', 'El peso (kg)', 0, 500)
                height = parse_number(request, 'height', 'La altura (cm)', 0, 300)
                emergency = {field: clip(request, ProfilePatient, field) for field in
                             ('emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone')}
                if bool(emergency['emergency_contact_name']) != bool(emergency['emergency_contact_phone']):
                    raise NameError('Complete el nombre y el teléfono del contacto de emergencia')
                patient = get_patient(data['person'], create=True, request=request)
                for field, value in emergency.items():
                    setattr(patient, field, value)
                patient.blood_group = blood_group or None
                patient.rh_factor = rh_factor or None
                patient.weight = weight
                patient.height = height
                patient.blood_pressure = clip(request, ProfilePatient, 'blood_pressure') or None
                patient.insurance_number = clip(request, ProfilePatient, 'insurance_number') or None
                patient.diabetes = request.POST.get('diabetes', '0') == '1'
                patient.save(request)
                request.session['person'] = Person.objects.get(id=data['person'].id)
                return JsonResponse({"result": "ok", "mensaje": "Datos médicos actualizados correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'savealergies':
            try:
                from apps.core.models import Person
                from apps.patientprofile.models import Alergy, PatientAlergy
                patient = get_patient(data['person'], create=True, request=request)
                ids = {value.strip() for value in request.POST.getlist('alergies') if value.strip()}
                if not all(value.isdigit() for value in ids):
                    raise NameError('Alergia no válida')
                chosen = {alergy.id for alergy in Alergy.objects.filter(status=True, id__in=ids)}
                if len(chosen) != len(ids):
                    raise NameError('Alguna de las alergias elegidas no existe en el catálogo')
                max_length = Alergy._meta.get_field('name').max_length
                typed = set()
                for name in (item.strip()[:max_length] for item in request.POST.get('new_alergies', '').split(',')):
                    # Conserva la primera forma escrita si se repite con otras mayúsculas
                    if not name or name.lower() in typed:
                        continue
                    typed.add(name.lower())
                    # Catálogo sin duplicados por mayúsculas; una alergia desactivada se reutiliza
                    alergy = Alergy.objects.filter(name__iexact=name).order_by('-status', 'id').first()
                    if not alergy:
                        alergy = Alergy(name=name)
                        alergy.save(request)
                    elif not alergy.status:
                        alergy.status = True
                        alergy.save(request)
                    chosen.add(alergy.id)
                seen = set()
                for relation in PatientAlergy.objects.filter(patient=patient).order_by('id'):
                    active = relation.alergy_id in chosen and relation.alergy_id not in seen
                    seen.add(relation.alergy_id)
                    if relation.status != active:
                        relation.status = active
                        relation.save(request)
                for alergy_id in chosen - seen:
                    PatientAlergy(patient=patient, alergy_id=alergy_id).save(request)
                request.session['person'] = Person.objects.get(id=data['person'].id)
                alergies = PatientAlergy.objects.filter(patient=patient, status=True).select_related('alergy').order_by('alergy__name')
                return JsonResponse({"result": "ok", "mensaje": "Alergias actualizadas correctamente",
                                     "data": {"alergies": [{'id': item.alergy_id, 'name': item.alergy.name} for item in alergies]}})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'savedoctorprofile':
            try:
                from decimal import Decimal, InvalidOperation
                from apps.core.models import Person
                from apps.medicalprofile.models import ProfileMedical
                person = Person.objects.get(id=data['person'].id)
                specialities = parse_specialities(request)
                try:
                    years_experience = int(request.POST.get('years_experience') or 0)
                    consultation_price = Decimal(request.POST.get('consultation_price') or 0).quantize(Decimal('0.01'))
                except (ValueError, InvalidOperation):
                    raise NameError('Los años de experiencia y el precio deben ser números')
                if years_experience < 0 or consultation_price < 0:
                    raise NameError('Los años de experiencia y el precio no pueden ser negativos')
                if consultation_price >= Decimal('1000000'):
                    raise NameError('El precio de consulta es demasiado alto')
                update_person_contact(request, person)
                person.save(request)
                doctor = get_doctor(person)
                created = doctor is None
                if created:
                    doctor = ProfileMedical(person=person, isprincipal=True)
                doctor.aboutme = request.POST.get('aboutme', '').strip()
                doctor.years_experience = years_experience
                doctor.office = request.POST.get('office', '').strip()[:150]
                doctor.consultation_price = consultation_price
                doctor.save(request)
                sync_specialities(request, doctor, specialities)
                request.session['person'] = person
                return JsonResponse({"result": "ok", "mensaje": "Perfil médico guardado correctamente", "data": {"id": doctor.id, "created": created}})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'addschedule':
            try:
                from apps.medicalprofile.models import ConsultationSchedule
                doctor = get_doctor(data['person'])
                if not doctor:
                    raise NameError('Primero crea tu perfil médico')
                days = [day for day in WEEKDAYS if day in request.POST.getlist('days')]
                if not days:
                    raise NameError('Debe elegir al menos un día válido')
                start_time, end_time, duration = parse_schedule_post(request)
                for day in days:
                    check_schedule_overlap(doctor, day, start_time, end_time)
                for day in days:
                    ConsultationSchedule.objects.create(doctor=doctor, available_days=day, start_time=start_time,
                                                        end_time=end_time, consultation_duration=duration)
                return JsonResponse({"result": "ok", "mensaje": "Horario agregado correctamente", "data": {"created": len(days)}})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'editschedule':
            try:
                doctor, schedule = get_doctor_schedule(request, data)
                start_time, end_time, duration = parse_schedule_post(request)
                check_schedule_overlap(doctor, schedule.available_days, start_time, end_time, exclude_id=schedule.id)
                schedule.start_time = start_time
                schedule.end_time = end_time
                schedule.consultation_duration = duration
                schedule.save()
                return JsonResponse({"result": "ok", "mensaje": "Horario actualizado correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'confirmappointment':
            try:
                doctor, appointment = get_doctor_appointment(request, data, request.POST.get('id'))
                if appointment.status != appointment.STATUS_PENDING:
                    raise NameError('Solo se pueden confirmar citas pendientes')
                appointment.status = appointment.STATUS_CONFIRMED
                appointment.save(request)
                return JsonResponse({"result": "ok", "mensaje": "Cita confirmada correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'doctorcancelappointment':
            try:
                doctor, appointment = get_doctor_appointment(request, data, request.POST.get('id'))
                if appointment.status not in appointment.ACTIVE_STATUSES or appointment.diagnosis:
                    raise NameError('Solo se pueden cancelar citas pendientes o confirmadas sin diagnóstico')
                reason = request.POST.get('reason', '').strip()
                if not reason:
                    raise NameError('Debe indicar el motivo de la cancelación')
                appointment.status = appointment.STATUS_CANCELLED
                appointment.cancelled_by = appointment.CANCELLED_BY_DOCTOR
                appointment.cancel_reason = reason[:255]
                appointment.save(request)
                return JsonResponse({"result": "ok", "mensaje": "Cita cancelada correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'saveresult':
            try:
                from django.utils import timezone
                doctor, appointment = get_doctor_appointment(request, data, request.POST.get('id'))
                if not can_record_result(appointment):
                    raise NameError('Solo se puede registrar el resultado de citas no canceladas de hoy o anteriores')
                diagnosis = request.POST.get('diagnosis', '').strip()
                if not diagnosis:
                    raise NameError('Debe ingresar el diagnóstico')
                # Sin el campo 'medications' en el POST se conservan las prescripciones existentes
                medications = parse_medications(request.POST['medications']) if 'medications' in request.POST else None
                appointment.diagnosis = diagnosis
                appointment.indications = request.POST.get('indications', '').strip() or None
                appointment.status = appointment.STATUS_DONE
                if not appointment.attended_at:
                    appointment.attended_at = timezone.now()
                appointment.save(request)
                if medications is not None:
                    from apps.appointment.models import PrescribedMedication
                    appointment.medications.all().delete()
                    for index, item in enumerate(medications):
                        PrescribedMedication(appointment=appointment, order=index, **item).save(request)
                return JsonResponse({"result": "ok", "mensaje": "Resultado de la cita guardado correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'followupappointment':
            try:
                from apps.appointment.models import Appointment
                doctor, appointment = get_doctor_appointment(request, data, request.POST.get('id'))
                date = parse_date(request.POST.get('date'))
                time = parse_time(request.POST.get('time'))
                schedule = dict(free_slots(doctor.id, date)).get(time)
                if not schedule:
                    raise NameError('El turno seleccionado no está disponible')
                followup = Appointment(patient=appointment.patient, doctor=doctor, speciality=appointment.speciality, consultation_schedule=schedule,
                                       appointment_date=date, appointment_time=time, reason=request.POST.get('reason', '').strip() or None)
                followup.full_clean()
                followup.save(request)
                return JsonResponse({"result": "ok", "mensaje": "Cita de seguimiento agendada correctamente",
                                     "data": {"id": followup.id, "date": date.strftime('%Y-%m-%d'), "time": time.strftime('%H:%M')}})
            except ValidationError as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": ' '.join(ex.messages)})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        elif action == 'deleteschedule':
            try:
                from apps.appointment.models import Appointment
                doctor, schedule = get_doctor_schedule(request, data)
                # El FK de Appointment es CASCADE: borrar el horario eliminaría el historial de citas
                history = Appointment.objects.filter(consultation_schedule=schedule).count()
                if history:
                    raise NameError(f'El horario tiene {history} citas registradas en su historial y no se puede eliminar; edítelo en su lugar.')
                schedule.delete()
                return JsonResponse({"result": "ok", "mensaje": "Horario eliminado correctamente"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})

        return JsonResponse({"result": "bad", "mensaje": u"Solicitud Incorrecta."})

    else:
        if 'action' in request.GET:
            action = request.GET['action']
            data['action'] = action
            if action == 'switchprofile':
                profile = request.GET.get('profile', '')
                if profile in ROLE_DENIED and not can_use_profile(request, profile):
                    return HttpResponseRedirect(f"{PROFILE_HOME[get_active_profile(request)]}&info={quote(ROLE_DENIED[profile])}")
                if profile not in PROFILE_HOME:
                    return HttpResponseRedirect(f"{PROFILE_HOME[get_active_profile(request)]}&info={quote('Perfil no válido.')}")
                request.session['active_profile'] = profile
                return HttpResponseRedirect(PROFILE_HOME[profile])

            required = required_profile(action)
            active = get_active_profile(request)
            message = None
            if required in ROLE_DENIED and not can_use_profile(request, required):
                message = ROLE_DENIED[required]
            elif required and active != required:
                message = f'Cambie al perfil {PROFILE_LABELS[required]} para usar esta opción.'
            if message:
                if action in ADMIN_JSON_GET_ACTIONS:
                    return JsonResponse({"results": [], "message": message})
                return HttpResponseRedirect(f"{PROFILE_HOME[active]}&info={quote(message)}")
            if required == 'admin':
                from apps.core.admin_panel import admin_get
                return admin_get(request, data, action)

            if action == 'doctorappointments':
                # Vista inicial del perfil médico: sin redirect en error para no entrar en bucle
                add_panel_data(request, data, action, 'Citas de mis pacientes')
                doctor = data['doctor']
                if not doctor:
                    return HttpResponseRedirect(f"/panel?action=doctorprofile&info={quote('Primero crea tu perfil médico')}")
                querysets = doctor_appointment_querysets(doctor)
                tab = request.GET.get('tab', 'today')
                if tab not in querysets:
                    tab = 'today'
                appointments = querysets[tab]
                q = request.GET.get('q', '').strip()
                for term in q.split():
                    appointments = appointments.filter(Q(patient__person__names__icontains=term) | Q(patient__person__lastnames__icontains=term) |
                                                       Q(patient__person__document__icontains=term))
                date = request.GET.get('date', '').strip()
                if date:
                    try:
                        appointments = appointments.filter(appointment_date=parse_date(date))
                    except NameError:
                        date = ''
                data['appointments'] = appointments
                data['tab'] = tab
                data['counts'] = {key: qs.count() for key, qs in querysets.items()}
                data['q'] = q
                data['date'] = date
                return render(request, "doctor_appointments.html", data)

            elif action == 'doctorappointmentdetail':
                try:
                    from apps.appointment.models import Appointment
                    from apps.patientprofile.models import PatientAlergy
                    add_panel_data(request, data, action, 'Atención de cita')
                    doctor, appointment = get_doctor_appointment(request, data, request.GET.get('id'))
                    data['appointment'] = appointment
                    data['patient'] = appointment.patient
                    data['patient_person'] = appointment.patient.person
                    data['alergies'] = PatientAlergy.objects.filter(patient=appointment.patient, status=True).select_related('alergy')
                    data['history'] = Appointment.objects.filter(patient=appointment.patient, doctor=doctor).exclude(id=appointment.id).select_related(
                        'speciality').prefetch_related('medications').order_by('-appointment_date', '-appointment_time')
                    data['medications'] = appointment.medications.all()
                    data['can_record_result'] = can_record_result(appointment)
                    data['can_confirm'] = appointment.status == appointment.STATUS_PENDING
                    # Hora local del servidor, igual que expire_appointments (TIME_ZONE='UTC' desfasa {% now %})
                    slot_end = datetime.combine(appointment.appointment_date, appointment.appointment_time) + (appointment.consultation_schedule.consultation_duration or timedelta(0))
                    data['slot_passed'] = appointment.status in appointment.ACTIVE_STATUSES and slot_end < datetime.now()
                    return render(request, "doctor_appointment_detail.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"/panel?action=doctorappointments&info={quote(ex.__str__())}")

            elif action == 'doctorprofile':
                # Inicio de los médicos sin perfil: sin redirect en error para no entrar en bucle
                from apps.core.models import Person, Specialty
                add_panel_data(request, data, action, 'Mi perfil médico')
                doctor = data['doctor']
                data['person'] = Person.objects.get(id=data['person'].id)
                data['specialities'] = Specialty.objects.filter(status=True).order_by('title')
                data['doctor_speciality_ids'] = [str(value) for value in doctor.specialtyprofile_set.filter(status=True).values_list('specialty_id', flat=True)] if doctor else []
                return render(request, "doctor_profile.html", data)

            elif action == 'doctorschedule':
                try:
                    from apps.medicalprofile.models import ConsultationSchedule
                    add_panel_data(request, data, action, 'Mis turnos de atención')
                    doctor = data['doctor']
                    if not doctor:
                        return HttpResponseRedirect(f"/panel?action=doctorprofile&info={quote('Primero crea tu perfil médico')}")
                    items = {day: [] for day in WEEKDAYS}
                    for schedule in ConsultationSchedule.objects.filter(doctor=doctor).order_by('start_time'):
                        if schedule.available_days not in items:
                            continue
                        duration = schedule.consultation_duration or timedelta(0)
                        items[schedule.available_days].append({
                            'id': schedule.id, 'start_time': schedule.start_time.strftime('%H:%M'), 'end_time': schedule.end_time.strftime('%H:%M'),
                            'duration_minutes': int(duration.total_seconds() // 60),
                            'slots_count': slots_count(schedule.start_time, schedule.end_time, duration),
                            'has_future_appointments': future_appointments(schedule).exists()})
                    data['schedule_days'] = [{'code': day, 'label': WEEKDAY_LABELS[day], 'items': items[day]} for day in WEEKDAYS]
                    data['day_choices'] = [(day, WEEKDAY_LABELS[day]) for day in WEEKDAYS]
                    data['duration_choices'] = DURATION_CHOICES
                    return render(request, "doctor_schedule.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"/panel?action=doctorappointments&info={quote(ex.__str__())}")

            elif action == 'appointment':
                from .forms import AppointmentForm
                from apps.core.models import Specialty
                add_panel_data(request, data, action, 'Reservar una cita médica')
                data['form'] = AppointmentForm()
                data['specialities'] = Specialty.objects.filter(status=True).order_by('title')
                preset_doctor = request.GET.get('doctor', '')
                preset_speciality = request.GET.get('speciality', '')
                data['preset_doctor'] = preset_doctor if preset_doctor.isdigit() else ''
                data['preset_speciality'] = preset_speciality if preset_speciality.isdigit() else ''
                return render(request, "appointment.html", data)

            elif action == 'myappointments':
                try:
                    patient = add_panel_data(request, data, action, 'Mis citas')
                    querysets = appointment_querysets(patient)
                    tab = request.GET.get('tab', 'upcoming')
                    if tab not in querysets:
                        tab = 'upcoming'
                    data['tab'] = tab
                    data['appointments'] = querysets[tab]
                    data['counts'] = {key: qs.count() for key, qs in querysets.items()}
                    return render(request, "my_appointments.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"/panel?action=appointment&info={quote(ex.__str__())}")

            elif action == 'directory':
                try:
                    from apps.core.models import Specialty
                    from apps.medicalprofile.models import ProfileMedical, SpecialtyProfile
                    add_panel_data(request, data, action, 'Directorio médico')
                    q = request.GET.get('q', '').strip()
                    speciality = request.GET.get('speciality', '').strip()
                    doctors = ProfileMedical.objects.filter(status=True).select_related('person').prefetch_related(
                        Prefetch('specialtyprofile_set', queryset=SpecialtyProfile.objects.filter(status=True).select_related('specialty')))
                    for term in q.split():
                        doctors = doctors.filter(Q(person__names__icontains=term) | Q(person__lastnames__icontains=term) |
                                                 Q(specialtyprofile__status=True, specialtyprofile__specialty__title__icontains=term))
                    if speciality.isdigit():
                        doctors = doctors.filter(specialtyprofile__status=True, specialtyprofile__specialty_id=speciality)
                    data['doctors'] = doctors.distinct().order_by('person__lastnames', 'person__names')
                    data['specialities'] = Specialty.objects.filter(status=True).order_by('title')
                    data['q'] = q
                    data['speciality'] = speciality
                    return render(request, "directory.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"/panel?action=appointment&info={quote(ex.__str__())}")

            elif action == 'profile':
                try:
                    from apps.core.models import Person
                    from apps.patientprofile.models import PatientAlergy
                    patient = add_panel_data(request, data, action, 'Mi perfil')
                    data['person'] = Person.objects.get(id=data['person'].id)
                    data['patient'] = patient
                    data['alergies'] = PatientAlergy.objects.filter(patient=patient, status=True).select_related('alergy') if patient else PatientAlergy.objects.none()
                    return render(request, "patient_profile.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"/panel?action=appointment&info={quote(ex.__str__())}")

            elif action == 'settings':
                try:
                    add_panel_data(request, data, action, 'Configuración')
                    return render(request, "settings.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"{PROFILE_HOME[get_active_profile(request)]}&info={quote(ex.__str__())}")

            elif action == 'profileedit':
                try:
                    from apps.core.models import Person, Country, Province, Canton, Parish
                    from apps.patientprofile.models import Alergy
                    add_panel_data(request, data, action, 'Editar mi perfil')
                    person = Person.objects.select_related('country', 'province', 'canton', 'parish').get(id=data['person'].id)
                    patient = get_patient(person, create=True, request=request)
                    data['person'] = person
                    data['patient'] = patient
                    data['sex_choices'] = Person.SEX
                    data['typedocument_choices'] = Person.TYPEDOCUMENT
                    data['countries'] = Country.objects.filter(status=True).order_by('name')
                    data['provinces'] = Province.objects.filter(status=True, country_id=person.country_id).order_by('name') if person.country_id else Province.objects.none()
                    data['cantons'] = Canton.objects.filter(status=True, province_id=person.province_id).order_by('name') if person.province_id else Canton.objects.none()
                    data['parishes'] = Parish.objects.filter(status=True, canton_id=person.canton_id).order_by('name') if person.canton_id else Parish.objects.none()
                    data['alergy_catalog'] = Alergy.objects.filter(status=True).order_by('name')
                    data['patient_alergy_ids'] = [str(value) for value in patient.patientalergy_set.filter(status=True).values_list('alergy_id', flat=True)]
                    data['blood_group_choices'] = BLOOD_GROUP_CHOICES
                    data['rh_choices'] = RH_CHOICES
                    return render(request, "patient_profile_edit.html", data)
                except Exception as ex:
                    return HttpResponseRedirect(f"/panel?action=profile&info={quote(ex.__str__())}")

            elif action == 'getprovinces':
                from apps.core.models import Province
                country_id = request.GET.get('country_id', '')
                return location_results(Province.objects.filter(country_id=country_id) if country_id.isdigit() else Province.objects.none())

            elif action == 'getcantons':
                from apps.core.models import Canton
                province_id = request.GET.get('province_id', '')
                return location_results(Canton.objects.filter(province_id=province_id) if province_id.isdigit() else Canton.objects.none())

            elif action == 'getparishes':
                from apps.core.models import Parish
                canton_id = request.GET.get('canton_id', '')
                return location_results(Parish.objects.filter(canton_id=canton_id) if canton_id.isdigit() else Parish.objects.none())

            elif action == 'searchdoctorbyspeciality':
                try:
                    from apps.medicalprofile.models import SpecialtyProfile
                    id_speciality = request.GET.get('id_speciality', None)
                    if not id_speciality:
                        raise NameError('Debe elegir una especialidad')
                    doctors = SpecialtyProfile.objects.filter(status=True, specialty_id=id_speciality, profilemedical__status=True).select_related('specialty', 'profilemedical__person')
                    results = [{'id': doctor.profilemedical_id, 'text': doctor.profilemedical.person.full_name(), 'image_url': doctor.profilemedical.person.get_photo()} for doctor in doctors]
                    return JsonResponse({"results": results}, safe=False)

                except Exception as ex:
                    return JsonResponse({"results": [], 'message': f'{ex}'})

            elif action == 'getdoctorinfo':
                try:
                    from apps.appointment.models import Appointment
                    from apps.medicalprofile.models import ProfileMedical
                    id_doctor = request.GET.get('id_doctor', None)
                    if not id_doctor:
                        raise NameError('Debe elegir un doctor')
                    doctor = ProfileMedical.objects.filter(status=True, id=id_doctor).select_related('person').first()
                    if not doctor:
                        raise NameError('El doctor no existe')
                    person = doctor.person
                    patients_count = Appointment.objects.filter(doctor=doctor).exclude(status=Appointment.STATUS_CANCELLED).values('patient_id').distinct().count()
                    results = {'photo_doctor': person.get_photo(), 'name_doctor': person.full_name(), 'front_page_card': person.get_front_page_card(),
                               'country_doctor': person.full_residence_country(),
                               'specialities_doctor': ' - '.join(doctor.specialtyprofile_set.select_related('specialty').filter(status=True).values_list('specialty__title', flat=True)[:2]),
                               'bio': doctor.aboutme, 'years_experience': doctor.years_experience, 'office': doctor.office,
                               'price': f'{doctor.consultation_price:.2f}', 'patients_count': patients_count}
                    # Devolvemos la respuesta en el formato que espera Select2
                    return JsonResponse({"data": results, 'display': True, 'message': 'ok'}, safe=False)

                except Exception as ex:
                    return JsonResponse({"data": [], 'display': False, 'message': f'{ex}'})

            elif action == 'getdatesavalies':
                try:
                    doctor_id = request.GET.get('doctor_id', None)
                    if not doctor_id:
                        raise NameError('Debe elegir un doctor')
                    today = datetime.now().date()
                    # Próximos 30 días que todavía tienen turnos libres
                    available_dates = []
                    for offset in range(31):
                        current_date = today + timedelta(days=offset)
                        if free_slots(doctor_id, current_date):
                            available_dates.append(current_date.strftime('%Y-%m-%d'))
                    return JsonResponse({"data": available_dates, 'message': 'ok'}, safe=False)
                except Exception as ex:
                    return JsonResponse({"data": [], 'message': f'{ex}'})

            elif action == 'getslots':
                try:
                    doctor_id = request.GET.get('doctor_id', None)
                    if not doctor_id:
                        raise NameError('Debe elegir un doctor')
                    date = parse_date(request.GET.get('date'))
                    results = [{'time': slot.strftime('%H:%M'), 'label': time_label(slot)} for slot, schedule in free_slots(doctor_id, date)]
                    return JsonResponse({"data": results, 'message': 'ok'}, safe=False)
                except Exception as ex:
                    return JsonResponse({"data": [], 'message': f'{ex}'})

            return JsonResponse({"data": [], 'message': 'error'}, safe=False)
        else:
            return HttpResponseRedirect(PROFILE_HOME[get_active_profile(request)])


@method_decorator(login_required(redirect_field_name='ret', login_url='/login'), name='dispatch')
class PanelPasswordChangeView(PasswordChangeView):
    template_name = 'password_change.html'
    success_url = reverse_lazy('password_change_done')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs['class'] = 'form-control'
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        add_data_session(self.request, context)
        add_panel_data(self.request, context, 'settings', 'Cambiar contraseña')
        context['forced'] = self.request.GET.get('forced') == '1' or must_change_password(context['person'])
        return context

    def form_valid(self, form):
        # super() guarda la contraseña y conserva la sesión (update_session_auth_hash)
        response = super().form_valid(form)
        from apps.core.models import Person
        Person.objects.filter(id=self.request.session['person'].id).update(must_change_password=False)
        self.request.session['person'] = Person.objects.get(id=self.request.session['person'].id)
        return response



def login_view(request):
    from django.contrib.auth import login as auth_login
    from apps.core.models import Person
    from .forms import LoginForm

    redirect_to = request.POST.get('ret') or request.GET.get('ret') or '/panel'
    # Solo rutas internas: evita redirigir a un dominio externo con ?ret=
    if not redirect_to.startswith('/'):
        redirect_to = '/panel'

    if request.user.is_authenticated:
        return HttpResponseRedirect(redirect_to)

    data = {'title': 'Iniciar sesión', 'ret': redirect_to}

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # /panel exige una Person asociada (add_data_session). Sin ella la
            # sesion revienta despues del login, asi que se corta aqui.
            if not Person.objects.filter(user=user).exists():
                data['form'] = form
                data['error'] = 'El usuario no tiene una persona asociada. Contacte al administrador.'
                return render(request, "sign-in.html", data)
            auth_login(request, user)
            return HttpResponseRedirect(redirect_to)
        data['form'] = form
        return render(request, "sign-in.html", data)

    data['form'] = LoginForm(request)
    return render(request, "sign-in.html", data)


def logout_view(request):
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return HttpResponseRedirect('/login')
