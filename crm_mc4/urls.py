from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static


def root_redirect(request):
    return redirect('account_login')


urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('accounts/', include('allauth.urls')),

    # API
    path('api-auth/', include('rest_framework.urls')),

    # App CRM
    path('crm/', include('comercial.urls')),

    # PWA
    path('pwa/', include('pwa.urls')),

    # Root
    path('', root_redirect),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
