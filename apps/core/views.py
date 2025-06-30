from datetime import datetime

from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.defaultfilters import first
from pyexpat.errors import messages

from apps.functions import add_data_session


# Create your views here.
# -*- coding: UTF-8 -*-



@login_required(redirect_field_name='ret', login_url='/login')
# @secure_module
# @last_access
@transaction.atomic()
def view(request):
    data = {}
    #
    add_data_session(request, data)
    data['person'] = request.session['person']
    if request.method == 'POST':
        action = request.POST['action']

        if action == 'addeventoqr':
            try:
                return JsonResponse({"result": "ok"})
            except Exception as ex:
                transaction.set_rollback(True)
                return JsonResponse({"result": "bad", "mensaje": f"Error: {ex.__str__()}"})
        return JsonResponse({"result": False, "message": u"Solicitud Incorrecta."})

    else:
        if 'action' in request.GET:
            action = request.GET['action']
            data['action'] = action

            if action == 'appointment':
                try:
                    from .forms import AppointmentForm
                    data['title'] = 'Reservar una cita médica'
                    data['form'] = AppointmentForm()
                    return render(request, "appointment.html", data)
                except Exception as ex:
                    pass

            elif action == 'searchdoctorbyspeciality':
                try:
                    from apps.medicalprofile.models import SpecialtyProfile
                    id_speciality = request.GET.get('id_speciality', None)
                    if not id_speciality:
                        raise NameError('Debe elegir una espcialidad')
                    doctors = SpecialtyProfile.objects.filter(status=True, specialty_id=id_speciality).select_related('specialty', 'profilemedical__person')
                    results = [{'id': doctor.profilemedical_id, 'text': doctor.profilemedical.person.full_name(), 'image_url': doctor.profilemedical.person.get_photo()} for doctor in doctors]
                    return JsonResponse({"results": results}, safe=False)

                except Exception as ex:
                    pass
            elif action == 'getdoctorinfo':
                try:
                    from apps.medicalprofile.models import ProfileMedical
                    id_doctor = request.GET.get('id_doctor', None)
                    if not id_doctor:
                        raise NameError('Debe elegir una espcialidad')
                    doctor = ProfileMedical.objects.filter(status=True, id=id_doctor).select_related('person').first()
                    person = doctor.person
                    results = {'photo_doctor': person.get_photo(), 'name_doctor': person.full_name(), 'age': 45, 'front_page_card': person.get_front_page_card(),
                               'country_doctor': person.full_residence_country(), 'specialities_doctor': ' - '.join(doctor.specialtyprofile_set.select_related('specialty').filter(status=True).values_list('specialty__title', flat=True)[:2])}
                    # Devolvemos la respuesta en el formato que espera Select2
                    return JsonResponse({"data": results, 'display': True, 'message': 'ok'}, safe=False)

                except Exception as ex:
                    return JsonResponse({"data": [], 'display': False, 'message': f'{ex}'})

            elif action == 'getdatesavalies':
                from apps.medicalprofile.models import ConsultationSchedule
                from datetime import datetime, timedelta
                if not 'doctor_id' in request.GET:
                    raise NameError('Debe elegir un doctor')
                doctor_id = request.GET.get('doctor_id', None)
                if not doctor_id:
                    raise NameError('Debe elegir un doctor')
                today = datetime.now().date()
                # Calcular el rango de fechas que deseas mostrar en el calendario (por ejemplo, próximo mes)
                start_date = today
                end_date = today + timedelta(days=30)  # 30 días en el futuro

                # Obtener los horarios disponibles del doctor para los próximos 30 días
                consultation_schedules = ConsultationSchedule.objects.filter(doctor_id=doctor_id)

                # Listar los días disponibles para el doctor
                available_days = []
                for schedule in consultation_schedules:
                    # Obtener los días disponibles (lunes, martes, etc.)
                    days = schedule.available_days.split(',')
                    for day in days:
                        available_days.append(day)

                # Ahora generamos una lista de fechas que son días disponibles en el calendario
                available_dates = []
                current_date = start_date
                while current_date <= end_date:
                    # Si el día actual es uno de los días disponibles
                    if current_date.strftime('%A').lower() in available_days:
                        available_dates.append(current_date)
                    current_date += timedelta(days=1)

                return JsonResponse({"data": available_dates, 'message': 'ok'}, safe=False)

            return JsonResponse({"data": [], 'message': 'error'}, safe=False)
        else:
            try:
                data['title'] = 'Pagina principal'
                return render(request, "base.html", data)
            except Exception as ex:
                return HttpResponseRedirect(f"/adm_eventos_qr?info={ex.__str__()}")

