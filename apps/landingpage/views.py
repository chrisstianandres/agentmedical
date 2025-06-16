from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.defaultfilters import first


# Create your views here.
# -*- coding: UTF-8 -*-



# @login_required(redirect_field_name='ret', login_url='/login')
# @secure_module
# @last_access
@transaction.atomic()
def view(request):
    global ex
    data = {}
    # persona = request.session['persona']
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

            if action == 'gestionar':
                try:
                    data['title'] = u'Configurar Población'
                    return render(request, "eventos_qr/configuracion/poblacion/view.html", data)
                except Exception as ex:
                    pass

            return HttpResponseRedirect(f"/adm_eventos_qr?info=No se encuenta esta accion")
        else:
            try:
                from apps.core.models import FrequentlyQuestion, AboutUsEntity, AboutUsDetail, Specialty, Service
                from apps.functions import get_entity
                data['title'] = 'Pagina principal'
                data['questions'] = FrequentlyQuestion.objects.all().only('question', 'answer').order_by('-id')
                data['about_us'] = about_us = AboutUsEntity.objects.filter(status=True).only('id','decription', 'urlvideo').order_by('-id').first()
                data['about_us_details'] = AboutUsDetail.objects.filter(status=True, aboutus=about_us).only('id','title', 'decription', 'icon').order_by('id')
                data['entity'] = get_entity()
                data['specialities'] = Specialty.objects.filter(status=True).only('id', 'title', 'description', 'image').order_by('id')
                data['services'] = Service.objects.filter(status=True).only('id', 'title', 'description', 'icon').order_by('id')
                return render(request, "index.html", data)
            except Exception as ex:
                return HttpResponseRedirect(f"/adm_eventos_qr?info={ex.__str__()}")

