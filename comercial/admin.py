from django.contrib import admin
from .models import Comercial, Cliente, Oportunidade

@admin.register(Comercial)
class ComercialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'email')

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'segmento', 'vendedor_responsavel')
    list_filter = ('tipo', 'vendedor_responsavel')
    search_fields = ('nome', 'segmento')

@admin.register(Oportunidade)
class OportunidadeAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'vendedor_responsavel', 'produto_formato', 'valor_estimado', 'estagio_funil', 'data_entrada')
    list_filter = ('estagio_funil', 'produto_formato', 'vendedor_responsavel')
    search_fields = ('cliente__nome', 'motivo_perda')