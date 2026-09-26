import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agentmedical.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = "admin"
email = "tu-correo@gmail.com"
password = "TuClaveSegura123!"

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    print("Superusuario creado")
else:
    print("El superusuario ya existe")