from urllib import request

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib.auth.models import Group

from .models import Oportunidade, Tarefa, NotaHistorico, Cliente, Comercial
from .forms import OportunidadeForm, ClienteForm, AgenciaForm

import json
import logging
from collections import defaultdict
from datetime import timedelta

logger = logging.getLogger(__name__)

# ================================
# PERMISSÕES
# ================================

def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()

def is_diretoria(user):
    return user.groups.filter(name='Diretoria').exists()

def is_comercial(user):
    return user.groups.filter(name='Comercial').exists()

def pode_editar(user, op):
    return is_admin(user) or is_diretoria(user) or op.vendedor_responsavel.user == user

def pode_acessar(user, op):
    return pode_editar(user, op)


# ================================
# FILTROS
# ================================

def get_oportunidades_usuario(user, request=None):
    qs = Oportunidade.objects.select_related('cliente', 'vendedor_responsavel')

    if not (is_admin(user) or is_diretoria(user)):
        qs = qs.filter(vendedor_responsavel__user=user)

    if request:
        vendedor = request.GET.get('vendedor')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        estagio = request.GET.get('estagio')

        if vendedor:
            qs = qs.filter(vendedor_responsavel_id=vendedor)

        if data_inicio:
            qs = qs.filter(data_entrada__gte=data_inicio)

        if data_fim:
            qs = qs.filter(data_entrada__lte=data_fim)

        if estagio:
            qs = qs.filter(estagio_funil=estagio)

    return qs


# ================================
# DASHBOARD
# ================================

@login_required(login_url='account_login')
def dashboard_view(request):

    hoje = timezone.now().date()
    primeiro_dia_mes = hoje.replace(day=1)

    ultimos_30_dias = hoje - timedelta(days=30)
    primeiro_dia_ano = hoje.replace(month=1, day=1)

    # ✅ filtro default
    if not request.GET.get('data_inicio') and not request.GET.get('data_fim'):
        request.GET = request.GET.copy()
        request.GET['data_inicio'] = str(primeiro_dia_mes)
        request.GET['data_fim'] = str(hoje)

    oportunidades = get_oportunidades_usuario(request.user, request)

    ativas = oportunidades.exclude(estagio_funil__in=['FECHADO', 'PERDIDO'])

    # ================================
    # VENDEDORES
    # ================================

    grupo_comercial = Group.objects.filter(name='Comercial').first()
    grupo_diretoria = Group.objects.filter(name='Diretoria').first()

    grupos = [g for g in [grupo_comercial, grupo_diretoria] if g]

    if is_admin(request.user) or is_diretoria(request.user):

        vendedores = Comercial.objects.select_related('user').filter(
            user__groups__in=grupos,
            ativo=True
        ).exclude(
            user__is_superuser=True
        ).distinct()

    else:
        vendedores = Comercial.objects.filter(user=request.user)

    ops = oportunidades.filter(vendedor_responsavel__in=vendedores)

    # ================================
    # GRÁFICO
    # ================================

    dados = defaultdict(lambda: {'fechado': 0, 'perdido': 0, 'aberto': 0})

    for op in ops:
        nome = op.vendedor_responsavel.nome

        if op.estagio_funil == 'FECHADO':
            dados[nome]['fechado'] += 1
        elif op.estagio_funil == 'PERDIDO':
            dados[nome]['perdido'] += 1
        else:
            dados[nome]['aberto'] += 1

    dados_grafico = [
        {'nome': k, **v}
        for k, v in dados.items()
        if v['fechado'] > 0 or v['aberto'] > 0 or v['perdido'] > 0
    ]

    # ================================
    # CONTEXT
    # ================================

    context = {
        'kpi_ativas': ativas.count(),
        'kpi_pipeline': ativas.aggregate(total=Sum('valor_estimado'))['total'] or 0,
        'kpi_ganhos': oportunidades.filter(estagio_funil='FECHADO')
            .aggregate(total=Sum('valor_estimado'))['total'] or 0,
        'ultimas_movimentacoes': oportunidades.order_by('-id')[:5],
        'followups_atrasados': oportunidades.filter(data_followup__lt=hoje).count(),

        'ranking': oportunidades.values('vendedor_responsavel__nome')
            .annotate(total=Sum('valor_estimado'))
            .order_by('-total')[:5],

        'vendedores_lista': vendedores,
        'estagios': Oportunidade.ESTAGIO_CHOICES,
        'form': OportunidadeForm(user=request.user),

        'is_admin': is_admin(request.user),
        'is_diretoria': is_diretoria(request.user),

        'grafico_funil': dados_grafico,

        # datas para botões
        'primeiro_dia_mes': primeiro_dia_mes,
        'ultimos_30_dias': ultimos_30_dias,
        'primeiro_dia_ano': primeiro_dia_ano,
        'hoje': hoje,
    }

    return render(request, 'comercial/dashboard.html', context)


# ================================
# KANBAN
# ================================

# ================================
# KANBAN
# ================================

@login_required(login_url='account_login')
def kanban_view(request):

    hoje = timezone.now().date()
    primeiro_dia_mes = hoje.replace(day=1)

    ultimos_30_dias = hoje - timedelta(days=30)
    primeiro_dia_ano = hoje.replace(month=1, day=1)

    # ✅ filtro padrão (igual dashboard)
    if not request.GET.get('data_inicio') and not request.GET.get('data_fim'):
        request.GET = request.GET.copy()
        request.GET['data_inicio'] = str(primeiro_dia_mes)
        request.GET['data_fim'] = str(hoje)

    comercial = None

    if is_comercial(request.user):
        comercial = getattr(request.user, 'comercial', None)

    # ================================
    # POST (EDITAR / CRIAR)
    # ================================

    if request.method == 'POST':
        oportunidade_id = request.POST.get('oportunidade_id')

        if oportunidade_id:
            instancia = get_object_or_404(Oportunidade, id=oportunidade_id)

            if not pode_editar(request.user, instancia):
                return redirect('kanban')

            form = OportunidadeForm(request.POST, instance=instancia, user=request.user)
        else:
            form = OportunidadeForm(request.POST, user=request.user)

        if form.is_valid():
            oportunidade = form.save(commit=False)

            if is_comercial(request.user) and comercial:
                oportunidade.vendedor_responsavel = comercial

            if not oportunidade.vendedor_responsavel:
                oportunidade.vendedor_responsavel = comercial

            is_new = oportunidade.pk is None
            oportunidade.save()

            # EMAIL
            if oportunidade.estagio_funil == 'SOLICITACAO' and is_new:
                try:
                    valor = oportunidade.valor_estimado or 'A definir'

                    email = EmailMessage(
                        subject=f'Solicitação - {oportunidade.cliente.nome}',
                        body=f"""
                        <h2>Nova Solicitação</h2>
                        <p>Cliente: {oportunidade.cliente.nome}</p>
                        <p>Comercial: {oportunidade.vendedor_responsavel.nome}</p>
                        <p>Valor: R$ {valor}</p>
                        """,
                        from_email='sistema@somosmc4.com.br',
                        to=settings.EMAIL_ORCAMENTO_PARA,
                        cc=settings.EMAIL_ORCAMENTO_CC,
                    )

                    email.content_subtype = "html"
                    email.send(fail_silently=True)

                except Exception:
                    logger.exception("Erro ao enviar email")

            return redirect('kanban')

        else:
            logger.warning(f"Form inválido: {form.errors}")

    else:
        form = OportunidadeForm(user=request.user)

    # ✅ agora respeita filtros (incluindo datas)
    oportunidades = get_oportunidades_usuario(request.user, request)

    # ================================
    # CONTEXT
    # ================================

    context = {
        'prospeccao': oportunidades.filter(estagio_funil='PROSPECCAO'),
        'solicitacao': oportunidades.filter(estagio_funil='SOLICITACAO'),
        'proposta': oportunidades.filter(estagio_funil='PROPOSTA'),
        'negociacao': oportunidades.filter(estagio_funil='NEGOCIACAO'),
        'fechado': oportunidades.filter(estagio_funil='FECHADO'),
        'perdido': oportunidades.filter(estagio_funil='PERDIDO'),

        'vendedores_lista': Comercial.objects.all(),
        'estagios': Oportunidade.ESTAGIO_CHOICES,
        'form': form,

        'is_admin': is_admin(request.user),
        'is_diretoria': is_diretoria(request.user),

        # ✅ necessário para os botões
        'primeiro_dia_mes': primeiro_dia_mes,
        'ultimos_30_dias': ultimos_30_dias,
        'primeiro_dia_ano': primeiro_dia_ano,
        'hoje': hoje,
    }

    return render(request, 'comercial/kanban.html', context)



# ================================
# CLIENTES
# ================================

@login_required(login_url='account_login')
def clientes_view(request):

    print("METHOD:", request.method)
    print("POST:", request.POST)

    clientes = Cliente.objects.all()

    # ✅ BUSCA
    busca = request.GET.get('busca')
    if busca:
        clientes = clientes.filter(nome__icontains=busca)

    # ✅ POST
    if request.method == 'POST':
        tipo = request.POST.get('tipo_cadastro')

        form_cliente = ClienteForm(request.POST)

        if form_cliente.is_valid():
            obj = form_cliente.save(commit=False)

            # ✅ 🔥 CORREÇÃO PRINCIPAL: DEFINIR TIPO
            if tipo == 'anunciante':
                obj.tipo = 'CLIENTE_FINAL'
            else:
                obj.tipo = 'AGENCIA'

            # ✅ VENDEDOR
            comercial = Comercial.objects.filter(user=request.user).first()
            obj.vendedor_responsavel = comercial

            obj.save()

            print(f"✅ SALVOU: {obj.nome} | TIPO: {obj.tipo}")

            return redirect('clientes')

        else:
            print("❌ ERRO FORM:", form_cliente.errors)
    else:
        form_cliente = ClienteForm()

    form_agencia = AgenciaForm()

    # ✅ CONTEXTO
    context = {
        'anunciantes': clientes
            .filter(tipo='CLIENTE_FINAL')
            .annotate(total_negocios=Count('oportunidades'))
            .order_by('nome'),

        'agencias': clientes
            .filter(tipo='AGENCIA')
            .annotate(total_negocios=Count('oportunidades_agencia'))
            .order_by('nome'),

        'form_cliente': form_cliente,
        'form_agencia': form_agencia,
    }

    return render(request, 'comercial/clientes.html', context)

# ================================
# COMERCIAL (CORREÇÃO DE BUG)
# ================================

@login_required(login_url='account_login')
def comercial_view(request):

    base_qs = Comercial.objects.annotate(
        total_leads=Count('oportunidades', distinct=True),
        leads_ativos=Count(
            'oportunidades',
            filter=~Q(oportunidades__estagio_funil__in=['FECHADO', 'PERDIDO']),
            distinct=True
        ),
        pipeline_ativo=Sum(
            'oportunidades__valor_estimado',
            filter=~Q(oportunidades__estagio_funil__in=['FECHADO', 'PERDIDO'])
        ),
        faturamento_fechado=Sum(
            'oportunidades__valor_estimado',
            filter=Q(oportunidades__estagio_funil='FECHADO')
        )
    )

    if is_admin(request.user) or is_diretoria(request.user):
        vendedores = base_qs
    else:
        vendedores = base_qs.filter(user=request.user)

    return render(request, 'comercial/comercial.html', {
        'vendedores': vendedores
    })


# ================================
# AJAX
# ================================

@require_http_methods(["POST"])
@login_required(login_url='account_login')
def excluir_oportunidade_ajax(request):

    try:
        data = json.loads(request.body or '{}')
        op = get_object_or_404(Oportunidade, id=data.get('id'))

        if not is_admin(request.user):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        op.delete()
        return JsonResponse({'status': 'ok'})

    except Exception:
        logger.exception("Erro ao excluir oportunidade")
        return JsonResponse({'erro': 'Erro interno'}, status=400)


@require_http_methods(["POST"])
@login_required(login_url='account_login')
def atualizar_estagio_ajax(request):

    try:
        data = json.loads(request.body or '{}')
        op = get_object_or_404(Oportunidade, id=data.get('id'))

        if not pode_acessar(request.user, op):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        op.estagio_funil = data.get('estagio')
        op.save()

        return JsonResponse({'status': 'ok'})

    except Exception:
        logger.exception("Erro ao atualizar estágio")
        return JsonResponse({'erro': 'Erro interno'}, status=400)


@require_http_methods(["POST"])
@login_required(login_url='account_login')
def adicionar_tarefa_ajax(request):

    try:
        data = json.loads(request.body or '{}')
        op = get_object_or_404(Oportunidade, id=data.get('oportunidade_id'))

        if not pode_acessar(request.user, op):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        tarefa = Tarefa.objects.create(
            oportunidade=op,
            descricao=data.get('descricao')
        )

        return JsonResponse({'id': tarefa.id, 'descricao': tarefa.descricao})

    except Exception:
        logger.exception("Erro ao adicionar tarefa")
        return JsonResponse({'erro': 'Erro interno'}, status=400)


@require_http_methods(["POST"])
@login_required(login_url='account_login')
def alternar_tarefa_ajax(request):

    try:
        data = json.loads(request.body or '{}')
        tarefa = get_object_or_404(Tarefa, id=data.get('id'))

        if not pode_acessar(request.user, tarefa.oportunidade):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        tarefa.concluida = not tarefa.concluida
        tarefa.save()

        return JsonResponse({'concluida': tarefa.concluida})

    except Exception:
        logger.exception("Erro ao alternar tarefa")
        return JsonResponse({'erro': 'Erro interno'}, status=400)


@require_http_methods(["POST"])
@login_required(login_url='account_login')
def adicionar_nota_ajax(request):

    try:
        data = json.loads(request.body or '{}')
        op = get_object_or_404(Oportunidade, id=data.get('oportunidade_id'))

        if not pode_acessar(request.user, op):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        nota = NotaHistorico.objects.create(
            oportunidade=op,
            texto=data.get('texto')
        )

        return JsonResponse({
            'texto': nota.texto,
            'data': nota.criada_em.strftime('%d/%m/%Y %H:%M')
        })

    except Exception:
        logger.exception("Erro ao adicionar nota")
        return JsonResponse({'erro': 'Erro interno'}, status=400)


@login_required(login_url='account_login')
def buscar_detalhes_oportunidade(request, pk):

    try:
        op = get_object_or_404(Oportunidade, pk=pk)

        if not pode_acessar(request.user, op):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        tarefas = list(op.tarefas.values('id', 'descricao', 'concluida'))
        historicos = list(op.historicos.values('texto', 'criada_em'))

        for h in historicos:
            h['criada_em'] = h['criada_em'].strftime('%d/%m/%Y %H:%M')

        return JsonResponse({
            'tarefas': tarefas,
            'historicos': historicos
        })

    except Exception:
        logger.exception("Erro ao buscar detalhes")
        return JsonResponse({'erro': 'Erro interno'}, status=400)