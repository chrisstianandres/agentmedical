from django import forms
from django.contrib.auth.forms import AuthenticationForm

from apps.core.models import Specialty
from apps.medicalprofile.models import ProfileMedical


class AppointmentForm(forms.Form):
    speciality = forms.ModelChoiceField(queryset=Specialty.objects.filter(status=True), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    doctor = forms.ModelChoiceField(queryset=ProfileMedical.objects.none(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    date = forms.DateField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control fecha-input'})
    )
    turn = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Usuario', 'autofocus': True})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Contraseña'})
    )

    error_messages = {
        'invalid_login': 'Usuario o contraseña incorrectos.',
        'inactive': 'Esta cuenta está inactiva.',
    }
