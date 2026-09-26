from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q


def expire_appointments(now=None):
    """ Cancela las citas pendientes/confirmadas sin diagnóstico cuya hora de fin + margen ya pasó.
        Devuelve cuántas citas se cancelaron. """
    from apps.appointment.models import Appointment
    now = now or datetime.now()
    grace = timedelta(minutes=getattr(settings, 'APPOINTMENT_EXPIRE_GRACE_MINUTES', 120))
    # En BD solo las candidatas (hasta hoy); la hora de fin se calcula en Python
    candidates = Appointment.objects.filter(appointment_date__lte=now.date(), status__in=Appointment.ACTIVE_STATUSES).filter(
        Q(diagnosis__isnull=True) | Q(diagnosis='')).values_list('id', 'appointment_date', 'appointment_time', 'consultation_schedule__consultation_duration')
    expired = [appointment_id for appointment_id, date, time, duration in candidates
               if datetime.combine(date, time) + (duration or timedelta(0)) + grace < now]
    if expired:
        Appointment.objects.filter(id__in=expired).update(status=Appointment.STATUS_CANCELLED, cancelled_by=Appointment.CANCELLED_BY_SYSTEM,
                                                          cancel_reason='Vencida sin atención', fecha_modificacion=now)
    return len(expired)
