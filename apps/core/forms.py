from django import forms

from apps.core.models import Specialty
from apps.medicalprofile.models import ProfileMedical


class AppointmentForm(forms.Form):
    speciality = forms.ModelChoiceField(queryset=Specialty.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    doctor = forms.ModelChoiceField(queryset=ProfileMedical.objects.none(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    turn = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
