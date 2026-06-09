from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Oportunidade, Tarefa, NotaHistorico, Cliente, Comercial
from .forms import OportunidadeForm, ClienteForm, AgenciaForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib.auth.models import Group
import json
import logging
from collections import defaultdict

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

# ================================
# FILTROS CENTRALIZADOS
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

def pode_editar(user, op):
    return is_admin(user) or is_diretoria(user) or op.vendedor_responsavel.user == user

def pode_acessar(user, op):
    return pode_editar(user, op)

# ================================
# DASHBOARD
# ================================

@login_required(login_url='account_login')
def dashboard_view(request):

    oportunidades = get_oportunidades_usuario(request.user, request)
    ativas = oportunidades.exclude(estagio_funil__in=['FECHADO', 'PERDIDO'])
    hoje = timezone.now().date()

    dados_grafico = []

    grupo_comercial = Group.objects.filter(name='Comercial').first()

    if is_admin(request.user) or is_diretoria(request.user):
        vendedores = Comercial.objects.filter(user__groups=grupo_comercial, ativo=True) if grupo_comercial else Comercial.objects.none()
    else:
        vendedores = Comercial.objects.filter(user=request.user)

    # ✅ PERFORMANCE (query única)
    ops = Oportunidade.objects.filter(vendedor_responsavel__in=vendedores)

    dados = defaultdict(lambda: {'fechado': 0, 'perdido': 0, 'aberto': 0})

    for op in ops:
        nome = op.vendedor_responsavel.nome

        if op.estagio_funil == 'FECHADO':
            dados[nome]['fechado'] += 1
        elif op.estagio_funil == 'PERDIDO':
            dados[nome]['perdido'] += 1
        else:
            dados[nome]['aberto'] += 1

    dados_grafico = [{'nome': k, **v} for k, v in dados.items()]

    context = {
        'kpi_ativas': ativas.count(),
        'kpi_pipeline': ativas.aggregate(total=Sum('valor_estimado'))['total'] or 0,
        'kpi_ganhos': oportunidades.filter(estagio_funil='FECHADO')
            .aggregate(total=Sum('valor_estimado'))['total'] or 0,
        'ultimas_movimentacoes': oportunidades.order_by('-id')[:5],
        'followups_atrasados': oportunidades.filter(data_followup__lt=hoje).count(),

        'ranking': oportunidades.values(
            'vendedor_responsavel__nome'
        ).annotate(
            total=Sum('valor_estimado')
        ).order_by('-total')[:5],

        'vendedores_lista': vendedores,
        'estagios': Oportunidade.ESTAGIO_CHOICES,
        'request': request,
        'form': OportunidadeForm(user=request.user),

        'is_admin': is_admin(request.user),
        'is_diretoria': is_diretoria(request.user),

        'grafico_funil': dados_grafico,
    }

    return render(request, 'comercial/dashboard.html', context)

# ================================
# KANBAN
# ================================

@login_required(login_url='account_login')
def kanban_view(request):

    comercial = None

    if is_comercial(request.user):
        try:
            comercial = Comercial.objects.get(user=request.user)
        except Comercial.DoesNotExist:
            return redirect('kanban')

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

            if is_comercial(request.user):
                oportunidade.vendedor_responsavel = comercial

            if not oportunidade.vendedor_responsavel:
                oportunidade.vendedor_responsavel = comercial

            is_new = oportunidade._state.adding
            oportunidade.save()

            # ✅ EMAIL
            if oportunidade.estagio_funil == 'SOLICITACAO' and is_new:
                try:
                    valor = oportunidade.valor_estimado if oportunidade.valor_estimado else 'A definir'

                    html_message = f"""
                    <html><body>
                        <h2 style="color:#00A5B5;">📩 Nova Solicitação de Proposta</h2>
                        <p><strong>Cliente:</strong> {oportunidade.cliente.nome}</p>
                        <p><strong>Comercial:</strong> {oportunidade.vendedor_responsavel.nome}</p>
                        <p><strong>Data:</strong> {timezone.now().strftime('%d/%m/%Y')}</p>
                        <p><strong>Formato:</strong> {oportunidade.get_produto_formato_display()}</p>
                        <p><strong>Valor:</strong> R$ {valor}</p>
                        <p><strong>Briefing:</strong><br>{oportunidade.descricao or 'Não informado'}</p>
                    </body></html>
                    """

                    email = EmailMessage(
                        subject=f'Solicitação de Proposta - {oportunidade.cliente.nome}',
                        body=html_message,
                        from_email='sistema@somosmc4.com.br',
                        to=settings.EMAIL_ORCAMENTO_PARA,
                        cc=settings.EMAIL_ORCAMENTO_CC,
                    )

                    email.content_subtype = "html"
                    email.send(fail_silently=True)

                except Exception as e:
                    logger.error(f"Erro ao enviar email: {e}")

            return redirect('kanban')

        else:
            logger.warning(f"Erros do form: {form.errors}")

    else:
        form = OportunidadeForm(user=request.user)

    oportunidades = get_oportunidades_usuario(request.user, request)

    context = {
        'prospeccao': oportunidades.filter(estagio_funil='PROSPECCAO'),
        'solicitacao': oportunidades.filter(estagio_funil='SOLICITACAO'),
        'proposta': oportunidades.filter(estagio_funil='PROPOSTA'),
        'negociacao': oportunidades.filter(estagio_funil='NEGOCIACAO'),
        'fechado': oportunidades.filter(estagio_funil='FECHADO'),
        'perdido': oportunidades.filter(estagio_funil='PERDIDO'),

        'vendedores_lista': Comercial.objects.all(),
        'estagios': Oportunidade.ESTAGIO_CHOICES,
        'request': request,
        'form': form,

        'is_admin': is_admin(request.user),
        'is_diretoria': is_diretoria(request.user),
    }

    return render(request, 'comercial/kanban.html', context)

# ================================
# CLIENTES
# ================================

@login_required(login_url='account_login')
def clientes_view(request):

    if is_admin(request.user) or is_diretoria(request.user):
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(vendedor_responsavel__user=request.user)

    busca = request.GET.get('busca')

    if busca:
        clientes = clientes.filter(nome__icontains=busca)

    if request.method == 'POST':
        tipo = request.POST.get('tipo_cadastro')
        form = ClienteForm(request.POST) if tipo == 'anunciante' else AgenciaForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)

            if is_comercial(request.user):
                obj.vendedor_responsavel = request.user.comercial

            obj.save()
            return redirect('clientes')

    context = {
        'anunciantes': clientes.filter(tipo='CLIENTE_FINAL')
            .annotate(total_negocios=Count('oportunidades')),

        'agencias': clientes.filter(tipo='AGENCIA')
            .annotate(total_negocios=Count('oportunidades_agencia')),

        'form_cliente': ClienteForm(),
        'form_agencia': AgenciaForm(),
        'request': request
    }

    return render(request, 'comercial/clientes.html', context)

# ================================
# AJAX ENDPOINTS
# ================================

@require_http_methods(["POST"])
@login_required(login_url='account_login')
def excluir_oportunidade_ajax(request):

    try:
        data = json.loads(request.body)
        op = get_object_or_404(Oportunidade, id=data.get('id'))

        if not is_admin(request.user):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        op.delete()
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.error(str(e))
        return JsonResponse({'erro': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required(login_url='account_login')
def atualizar_estagio_ajax(request):

    try:
        data = json.loads(request.body)
        op = get_object_or_404(Oportunidade, id=data.get('id'))

        if not pode_acessar(request.user, op):
            return JsonResponse({'erro': 'Sem permissão'}, status=403)

        op.estagio_funil = data.get('estagio')
        op.save()

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.error(str(e))
        return JsonResponse({'erro': str(e)}, status=400)


login_required(login_url='account_login')
def comercial_view(request):
    vendedores = Comercial.objects.all()

    return render(request, 'comercial/comercial.html', {
        'vendedores': vendedores
    })
