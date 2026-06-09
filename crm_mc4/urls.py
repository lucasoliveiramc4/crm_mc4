from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('accounts/', include('allauth.urls')),

    # API
    path('api-auth/', include('rest_framework.urls')),

    # App CRM
    path('crm/', include('comercial.urls')),

    # ✅ PWA (mantém root funcionando)
    path('pwa/', include('pwa.urls')),

    # ✅ ROOT REDIRECT (CORRETO)
    path('', lambda request: redirect('/accounts/login/')),
]

# ✅ apenas para desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)