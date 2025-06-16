from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.defaultfilters import first

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
                    data['title'] = 'Reservar una cita médica'
                    return render(request, "appointment.html", data)
                except Exception as ex:
                    pass

            return HttpResponseRedirect(f"/adm_eventos_qr?info=No se encuenta esta accion")
        else:
            try:
                data['title'] = 'Pagina principal'
                return render(request, "base.html", data)
            except Exception as ex:
                return HttpResponseRedirect(f"/adm_eventos_qr?info={ex.__str__()}")

