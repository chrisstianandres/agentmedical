from django.urls import path
from django.views.generic import RedirectView

from apps.core.views import view, login_view, logout_view, PanelPasswordChangeView

urlpatterns = [
    path('panel', view, name='panel'),
    path('login', login_view, name='login'),
    path('logout', logout_view, name='logout'),
    path('password_change', PanelPasswordChangeView.as_view(), name='password_change'),
    path('password_change/done', RedirectView.as_view(url='/panel?action=settings'), name='password_change_done'),
]
