from django.core.management.base import BaseCommand

from apps.appointment.functions import expire_appointments


class Command(BaseCommand):
    help = 'Cancela las citas pendientes/confirmadas vencidas sin atención (programable con cron o el Programador de tareas)'

    def handle(self, *args, **options):
        total = expire_appointments()
        self.stdout.write(self.style.SUCCESS(f'Citas vencidas canceladas: {total}'))
