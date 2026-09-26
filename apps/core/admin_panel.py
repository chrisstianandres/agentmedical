""" Acciones del perfil administrativo del panel (/panel?action=admin*). view() ya aplicó las guardas de rol y perfil. """
from datetime import datetime
from urllib.parse import quote

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render

from apps.core.views import (ADMIN_GROUP, DOCTOR_GROUP, add_panel_data, appointment_tab_querysets, apply_contact,
                             apply_personal, free_slots, get_patient, parse_date, parse_specialities, parse_time,
                             sync_specialities)

PAGE_SIZE = 20
ROLES = ('patient', 'doctor', 'admin')
ADMIN_CONTACT_FIELDS = ('cellphonenumber', 'city', 'streetaddress', 'reference')


def bad(ex):
    transaction.set_rollback(True)
    message = ' '.join(ex.messages) if isinstance(ex, ValidationError) else ex.__str__()
    return JsonResponse({"result": "bad", "mensaje": f"Error: {message}"})


def page_of(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get('page'))


def future_active_appointments(**filters):
    """ Citas pendientes/confirmadas desde ahora que cumplan los filtros """
    from apps.appointment.models import Appointment
    now = datetime.now()
    return Appointment.objects.filter(status__in=Appointment.ACTIVE_STATUSES, **filters).filter(
        Q(appointment_date__gt=now.date()) | Q(appointment_date=now.date(), appointment_time__gte=now.time()))


def patient_label(patient):
    person = patient.person
    return f"{person.full_name()} · C.I. {person.document}" if person.document else person.full_name()


def get_appointment(appointment_id):
    from apps.appointment.models import Appointment
    appointment = Appointment.objects.select_related('patient__person', 'doctor__person', 'speciality').filter(
        id=appointment_id if str(appointment_id or '').isdigit() else 0).first()
    if not appointment:
        raise NameError('La cita no existe')
    return appointment


def resolve_doctor(request, speciality):
    from apps.medicalprofile.models import ProfileMedical
    doctor = ProfileMedical.objects.filter(status=True, id=request.POST.get('doctor') if str(request.POST.get('doctor', '')).isdigit() else 0,
                                           specialtyprofile__status=True, specialtyprofile__specialty=speciality).select_related('person').first()
    if not doctor:
        raise NameError('Debe elegir un doctor de la especialidad seleccionada')
    return doctor


def persons_with_roles():
    """ Personas anotadas con sus roles activos (sin N+1) """
    from apps.core.models import Person
    from apps.medicalprofile.models import ProfileMedical
    from apps.patientprofile.models import ProfilePatient
    return Person.objects.select_related('user').annotate(
        role_patient=Exists(ProfilePatient.objects.filter(person=OuterRef('pk'), status=True)),
        patient_id=Subquery(ProfilePatient.objects.filter(person=OuterRef('pk'), status=True).values('id')[:1]),
        role_doctor=Exists(ProfileMedical.objects.filter(person=OuterRef('pk'), status=True)),
        role_admin_group=Exists(Group.objects.filter(name=ADMIN_GROUP, user=OuterRef('user_id'))))


def person_roles(person):
    user = person.user
    return {'patient': person.role_patient, 'doctor': person.role_doctor,
            'admin': bool(person.role_admin_group or (user and user.is_superuser))}


def admin_get(request, data, action):
    if action == 'adminappointments':
        # Vista inicial del perfil administrativo: sin redirect en error para no entrar en bucle
        from apps.appointment.models import Appointment
        from apps.core.models import Specialty
        from apps.medicalprofile.models import ProfileMedical
        add_panel_data(request, data, action, 'Gestión de citas')
        base = Appointment.objects.select_related('patient__person', 'doctor__person', 'speciality').prefetch_related('medications')
        q = request.GET.get('q', '').strip()
        for term in q.split():
            base = base.filter(Q(patient__person__names__icontains=term) | Q(patient__person__lastnames__icontains=term) |
                               Q(patient__person__document__icontains=term) | Q(doctor__person__names__icontains=term) |
                               Q(doctor__person__lastnames__icontains=term))
        doctor = request.GET.get('doctor', '').strip()
        if doctor.isdigit():
            base = base.filter(doctor_id=doctor)
        speciality = request.GET.get('speciality', '').strip()
        if speciality.isdigit():
            base = base.filter(speciality_id=speciality)
        date = request.GET.get('date', '').strip()
        if date:
            try:
                base = base.filter(appointment_date=parse_date(date))
            except NameError:
                date = ''
        querysets = appointment_tab_querysets(base)
        tab = request.GET.get('tab', 'today')
        if tab not in querysets:
            tab = 'today'
        data['page_obj'] = page_of(request, querysets[tab])
        data['appointments'] = data['page_obj'].object_list
        data['tab'] = tab
        data['counts'] = {key: qs.count() for key, qs in querysets.items()}
        data['q'] = q
        data['doctor'] = doctor if doctor.isdigit() else ''
        data['speciality'] = speciality if speciality.isdigit() else ''
        data['date'] = date
        data['doctors'] = ProfileMedical.objects.filter(status=True).select_related('person').order_by('person__lastnames', 'person__names')
        data['specialities'] = Specialty.objects.filter(status=True).order_by('title')
        return render(request, "admin_appointments.html", data)

    elif action == 'adminnewappointment':
        try:
            from apps.core.models import Specialty
            from apps.patientprofile.models import ProfilePatient
            add_panel_data(request, data, action, 'Agendar cita')
            data['specialities'] = Specialty.objects.filter(status=True).order_by('title')
            patient_id = request.GET.get('patient', '')
            patient = ProfilePatient.objects.filter(status=True, id=patient_id).select_related('person').first() if patient_id.isdigit() else None
            data['preset_patient'] = {'id': patient.id, 'text': patient_label(patient)} if patient else None
            return render(request, "admin_new_appointment.html", data)
        except Exception as ex:
            return HttpResponseRedirect(f"/panel?action=adminappointments&info={quote(ex.__str__())}")

    elif action == 'adminpersons':
        try:
            add_panel_data(request, data, action, 'Personas')
            persons = persons_with_roles()
            q = request.GET.get('q', '').strip()
            for term in q.split():
                persons = persons.filter(Q(names__icontains=term) | Q(lastnames__icontains=term) |
                                         Q(document__icontains=term) | Q(email__icontains=term))
            role = request.GET.get('role', '').strip()
            is_admin = Q(role_admin_group=True) | Q(user__is_superuser=True)
            if role == 'patient':
                persons = persons.filter(role_patient=True)
            elif role == 'doctor':
                persons = persons.filter(role_doctor=True)
            elif role == 'admin':
                persons = persons.filter(is_admin)
            elif role == 'none':
                persons = persons.filter(role_patient=False, role_doctor=False).exclude(is_admin)
            else:
                role = ''
            data['page_obj'] = page_of(request, persons.order_by('lastnames', 'names', 'id'))
            data['persons'] = list(data['page_obj'].object_list)
            for person in data['persons']:
                roles = person_roles(person)
                person.is_patient, person.is_doctor, person.is_admin = roles['patient'], roles['doctor'], roles['admin']
                person.has_user = person.user_id is not None
                person.username = person.user.username if person.user else ''
                person.is_active = person.user.is_active if person.user else False
            highlight = request.GET.get('highlight', '').strip()
            data['highlight'] = highlight if highlight.isdigit() else ''
            data['q'] = q
            data['role'] = role
            return render(request, "admin_persons.html", data)
        except Exception as ex:
            return HttpResponseRedirect(f"/panel?action=adminappointments&info={quote(ex.__str__())}")

    elif action == 'adminpersonform':
        try:
            from apps.core.models import Person, Country, Province, Canton, Parish, Specialty
            add_panel_data(request, data, action, 'Nueva persona')
            person = None
            person_id = request.GET.get('id', '')
            if person_id:
                person = persons_with_roles().select_related('country', 'province', 'canton', 'parish').filter(
                    id=person_id if person_id.isdigit() else 0).first()
                if not person:
                    raise NameError('La persona no existe')
                data['title'] = 'Editar persona'
            # La cabecera ya se calculó con header_*: 'person' pasa a ser la persona editada (o None en un alta)
            data['person'] = person
            data['person_user'] = person.user if person else None
            data['roles'] = person_roles(person) if person else {role: False for role in ROLES}
            doctor = person.profilemedical_set.filter(status=True).first() if person else None
            data['specialities'] = Specialty.objects.filter(status=True).order_by('title')
            data['doctor_speciality_ids'] = [str(value) for value in doctor.specialtyprofile_set.filter(status=True).values_list('specialty_id', flat=True)] if doctor else []
            data['sex_choices'] = Person.SEX
            data['typedocument_choices'] = Person.TYPEDOCUMENT
            data['countries'] = Country.objects.filter(status=True).order_by('name')
            data['provinces'] = Province.objects.filter(status=True, country_id=person.country_id).order_by('name') if person and person.country_id else Province.objects.none()
            data['cantons'] = Canton.objects.filter(status=True, province_id=person.province_id).order_by('name') if person and person.province_id else Canton.objects.none()
            data['parishes'] = Parish.objects.filter(status=True, canton_id=person.canton_id).order_by('name') if person and person.canton_id else Parish.objects.none()
            return render(request, "admin_person_form.html", data)
        except Exception as ex:
            return HttpResponseRedirect(f"/panel?action=adminpersons&info={quote(ex.__str__())}")

    elif action == 'searchpatients':
        from apps.patientprofile.models import ProfilePatient
        q = request.GET.get('q', '').strip()
        if len(q) < 2:
            return JsonResponse({"results": []})
        patients = ProfilePatient.objects.filter(status=True).select_related('person')
        for term in q.split():
            patients = patients.filter(Q(person__names__icontains=term) | Q(person__lastnames__icontains=term) |
                                       Q(person__document__icontains=term) | Q(medical_record_number__icontains=term))
        patients = patients.order_by('person__lastnames', 'person__names')[:PAGE_SIZE]
        return JsonResponse({"results": [{'id': patient.id, 'text': patient_label(patient), 'document': patient.person.document,
                                          'hc': patient.medical_record_number} for patient in patients]})

    return JsonResponse({"data": [], 'message': 'error'}, safe=False)


def admin_post(request, data, action):
    if action == 'adminsaveperson':
        try:
            return save_person(request, data)
        except Exception as ex:
            return bad(ex)

    elif action == 'adminaddappointment':
        try:
            from apps.appointment.models import Appointment
            from apps.core.models import Specialty
            from apps.patientprofile.models import ProfilePatient
            patient_id = request.POST.get('patient', '')
            patient = ProfilePatient.objects.filter(status=True, id=patient_id).select_related('person').first() if patient_id.isdigit() else None
            if not patient:
                raise NameError('Debe elegir un paciente')
            speciality_id = request.POST.get('speciality', '')
            speciality = Specialty.objects.filter(status=True, id=speciality_id).first() if speciality_id.isdigit() else None
            if not speciality:
                raise NameError('Debe elegir una especialidad')
            doctor = resolve_doctor(request, speciality)
            if doctor.person_id == patient.person_id:
                raise NameError('El paciente no puede tener una cita consigo mismo como médico.')
            date = parse_date(request.POST.get('date'))
            time = parse_time(request.POST.get('time'))
            schedule = dict(free_slots(doctor.id, date)).get(time)
            if not schedule:
                raise NameError('El turno seleccionado no está disponible')
            appointment = Appointment(patient=patient, doctor=doctor, speciality=speciality, consultation_schedule=schedule,
                                      appointment_date=date, appointment_time=time, reason=request.POST.get('reason', '').strip() or None,
                                      status=Appointment.STATUS_CONFIRMED if request.POST.get('confirm') == '1' else Appointment.STATUS_PENDING)
            appointment.full_clean()
            appointment.save(request)
            return JsonResponse({"result": "ok", "mensaje": "Cita agendada correctamente",
                                 "data": {"id": appointment.id, "date": date.strftime('%Y-%m-%d'), "time": time.strftime('%H:%M'),
                                          "patient": patient.person.full_name(), "doctor": doctor.person.full_name()}})
        except Exception as ex:
            return bad(ex)

    elif action == 'adminconfirmappointment':
        try:
            appointment = get_appointment(request.POST.get('id'))
            if appointment.status != appointment.STATUS_PENDING:
                raise NameError('Solo se pueden confirmar citas pendientes')
            appointment.status = appointment.STATUS_CONFIRMED
            appointment.save(request)
            return JsonResponse({"result": "ok", "mensaje": "Cita confirmada correctamente"})
        except Exception as ex:
            return bad(ex)

    elif action == 'adminrescheduleappointment':
        try:
            appointment = get_appointment(request.POST.get('id'))
            if appointment.status not in appointment.ACTIVE_STATUSES or appointment.diagnosis:
                raise NameError('Solo se pueden reprogramar citas pendientes o confirmadas sin diagnóstico')
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
        except Exception as ex:
            return bad(ex)

    elif action == 'admincancelappointment':
        try:
            appointment = get_appointment(request.POST.get('id'))
            if appointment.status not in appointment.ACTIVE_STATUSES:
                raise NameError('Solo se pueden cancelar citas pendientes o confirmadas')
            reason = request.POST.get('reason', '').strip()
            if not reason:
                raise NameError('Debe indicar el motivo de la cancelación')
            appointment.status = appointment.STATUS_CANCELLED
            appointment.cancelled_by = appointment.CANCELLED_BY_ADMIN
            appointment.cancel_reason = reason[:255]
            appointment.save(request)
            return JsonResponse({"result": "ok", "mensaje": "Cita cancelada correctamente"})
        except Exception as ex:
            return bad(ex)

    return JsonResponse({"result": "bad", "mensaje": u"Solicitud Incorrecta."})


def save_person(request, data):
    """ Alta o edición de una persona con su cuenta de acceso y sus roles (todo o nada: view() es atómica) """
    from apps.core.models import Person
    from apps.medicalprofile.models import ProfileMedical
    person_id = request.POST.get('id', '').strip()
    if person_id:
        person = Person.objects.select_related('user').filter(id=person_id if person_id.isdigit() else 0).first()
        if not person:
            raise NameError('La persona no existe')
    else:
        person = Person()
    is_self = person.id is not None and person.id == data['person'].id
    apply_personal(request, person)
    apply_contact(request, person, ADMIN_CONTACT_FIELDS)
    roles = {role for role in request.POST.getlist('roles') if role in ROLES}
    is_active = request.POST.get('is_active', '1') == '1'

    # Validaciones de roles antes de escribir nada
    user = person.user if person.id else None
    wants_user = user is not None or request.POST.get('create_user') == '1'
    if roles & {'doctor', 'admin'} and not wants_user:
        raise NameError('Para asignar el rol médico o administrativo la persona necesita una cuenta de acceso')
    if is_self and 'admin' not in roles:
        raise NameError('No puede quitarse a sí mismo el rol administrativo')
    if is_self and not is_active:
        raise NameError('No puede desactivar su propia cuenta')
    specialities = parse_specialities(request) if 'doctor' in roles else []
    if person.id:
        current_doctor = person.profilemedical_set.filter(status=True).first()
        if current_doctor and 'doctor' not in roles:
            pending = future_active_appointments(doctor=current_doctor).count()
            if pending:
                raise NameError(f'Tiene {pending} citas futuras como médico; cancélelas o reasígnelas primero')
        current_patient = get_patient(person)
        if current_patient and 'patient' not in roles:
            pending = future_active_appointments(patient=current_patient).count()
            if pending:
                raise NameError(f'Tiene {pending} citas futuras como paciente; cancélelas o reasígnelas primero')

    # Cuenta de acceso: usuario y contraseña los genera el sistema (se ignora lo que llegue en el POST).
    # La contraseña en claro solo viaja en esta respuesta y obliga a cambiarla en el primer ingreso.
    credentials = None
    if user is None and request.POST.get('create_user') == '1':
        user = User(username=generate_username(person), email=person.email)
        password = generate_password(user)
        user.set_password(password)
        credentials = {'username': user.username, 'password': password}
    elif user is not None and request.POST.get('reset_password') == '1':
        password = generate_password(user)
        user.set_password(password)
        credentials = {'username': user.username, 'password': password}
    if user is not None:
        user.email = person.email
        user.first_name = person.names[:150]
        user.last_name = person.lastnames[:150]
        user.is_active = is_active
        user.save()
        person.user = user
    if credentials:
        person.must_change_password = True
    person.save(request)

    # Roles
    if 'patient' in roles:
        get_patient(person, create=True, request=request)
    else:
        current_patient = get_patient(person)
        if current_patient:
            current_patient.status = False
            current_patient.save(request)
    doctor_group, _ = Group.objects.get_or_create(name=DOCTOR_GROUP)
    admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
    if 'doctor' in roles:
        user.groups.add(doctor_group)
        doctor = ProfileMedical.objects.filter(person=person).order_by('-status', 'id').first() or ProfileMedical(person=person)
        doctor.status = True
        doctor.isprincipal = True
        doctor.save(request)
        sync_specialities(request, doctor, specialities)
    else:
        if user:
            user.groups.remove(doctor_group)
        for doctor in ProfileMedical.objects.filter(person=person, status=True):
            doctor.status = False
            doctor.save(request)
    if user:
        if 'admin' in roles:
            user.groups.add(admin_group)
        else:
            user.groups.remove(admin_group)

    if is_self:
        request.session['person'] = person
        if credentials:
            update_session_auth_hash(request, user)
    mensaje = "Persona guardada correctamente"
    if credentials:
        mensaje += ". Entregue las credenciales: la contraseña es temporal y se pedirá cambiarla en el primer ingreso"
    return JsonResponse({"result": "ok", "mensaje": mensaje, "data": {"id": person.id, "credentials": credentials}})


def _ascii_word(value):
    """ Texto sin tildes ni ñ, en minúsculas y solo [a-z0-9] """
    import unicodedata
    normalized = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    return ''.join(ch for ch in normalized.lower() if ch.isascii() and ch.isalnum())


def generate_username(person):
    """ Inicial del primer nombre + primer apellido ("María Fernanda López Silva" → "mlopez"); sufijo 2, 3… si existe """
    names = (person.names or '').split()
    lastnames = (person.lastnames or '').split()
    base = (_ascii_word(names[0][:1] if names else '') + _ascii_word(lastnames[0] if lastnames else ''))[:140]
    if not base:
        base = ('u' + _ascii_word(person.document))[:140]
    candidate, number = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        number += 1
        candidate = f'{base}{number}'
    return candidate


PASSWORD_ALPHABET = {
    'upper': 'ABCDEFGHJKLMNPQRSTUVWXYZ',
    'lower': 'abcdefghijkmnpqrstuvwxyz',
    'digit': '23456789',
}


def generate_password(user=None, length=10):
    """ Contraseña aleatoria (secrets) con mayúscula, minúscula y dígito, sin caracteres ambiguos (0 O o 1 l I),
        que pase los validadores de Django """
    import secrets
    alphabet = ''.join(PASSWORD_ALPHABET.values())
    while True:
        chars = [secrets.choice(group) for group in PASSWORD_ALPHABET.values()]
        chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        password = ''.join(chars)
        try:
            validate_password(password, user=user)
            return password
        except ValidationError:
            continue
