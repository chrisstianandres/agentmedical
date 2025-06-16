from django.contrib import admin
from apps.medicalprofile.models import ProfileMedical, TypeProfileMedical, SpecialtyProfile

admin.site.register(ProfileMedical)
admin.site.register(TypeProfileMedical)
admin.site.register(SpecialtyProfile)

