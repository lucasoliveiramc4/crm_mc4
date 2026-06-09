from django.urls import path, include
from . import views
from django.contrib.auth.decorators import login_required



urlpatterns = [

    path('accounts/', include('allauth.urls')),

    # ✅ PÁGINAS
    path('', views.dashboard_view, name='dashboard'),
    path('kanban/', views.kanban_view, name='kanban'),
    path('clientes/', views.clientes_view, name='clientes'),
    path('comercial/', views.comercial_view, name='comercial_equipe'),
    

    # ✅ AJAX
    path('atualizar-estagio/', views.atualizar_estagio_ajax, name='atualizar_estagio'),
    path('adicionar-tarefa/', views.adicionar_tarefa_ajax, name='adicionar_tarefa'),
    path('alternar-tarefa/', views.alternar_tarefa_ajax, name='alternar_tarefa'),
    path('adicionar-nota/', views.adicionar_nota_ajax, name='adicionar_nota'),
    path('buscar-detalhes/<int:pk>/', views.buscar_detalhes_oportunidade, name='buscar_detalhes'),

    # ✅ CORRIGIDO (AGORA CASA COM O JS)
    path('excluir-oportunidade/', views.excluir_oportunidade_ajax, name='excluir_oportunidade'),
]