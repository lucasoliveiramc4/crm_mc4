from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone



class Comercial(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    
    class Meta:
        verbose_name = "Vendedor / Comercial"
        verbose_name_plural = "Comerciais (Equipe)"

class Cliente(models.Model):
    TIPO_CHOICES = [
        ('CLIENTE_FINAL', 'Cliente Final / Anunciante'),
        ('AGENCIA', 'Agência de Publicidade'),
    ]

    nome = models.CharField(max_length=200)

    # ✅ NOVO CAMPO
    contato = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Nome do contato"
    )

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    segmento = models.CharField(max_length=100, blank=True, null=True)
    vendedor_responsavel = models.ForeignKey(Comercial, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

class Oportunidade(models.Model):
    PRODUTO_CHOICES = [
        ('LED', 'Painel LED'),
        ('BRT', 'BRT'),
        ('CENOGRAFICO', 'Cenografia'),
        ('PROMO', 'Promocional OOH'),
    ]
    
    
    ESTAGIO_CHOICES = [
        ('PROSPECCAO', 'Prospecção'),
        ('SOLICITACAO', 'Solicitação de Proposta'),
        ('PROPOSTA', 'Proposta Enviada'),
        ('NEGOCIACAO', 'Negociação'),
        ('FECHADO', 'Fechado'),
        ('PERDIDO', 'Perdido'),
    ]


    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='oportunidades')
    agencia = models.ForeignKey(Cliente, on_delete=models.SET_NULL, blank=True, null=True, limit_choices_to={'tipo': 'AGENCIA'}, related_name='oportunidades_agencia')
    vendedor_responsavel = models.ForeignKey(Comercial, on_delete=models.PROTECT)
    
    produto_formato = models.CharField(max_length=20, choices=PRODUTO_CHOICES)
    valor_estimado = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)

    estagio_funil = models.CharField(max_length=20, choices=ESTAGIO_CHOICES, default='PROSPECCAO')
    
    data_entrada = models.DateField(auto_now_add=True)
    data_desfecho = models.DateField(blank=True, null=True)
    
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição:")
    
    motivo_perda = models.TextField(blank=True, null=True)

    def clean(self):
        errors = {}

        if self.estagio_funil == 'PERDIDO' and not self.motivo_perda:
            errors['motivo_perda'] = 'O motivo de perda é obrigatório quando o estágio é Perdido.'

        if self.estagio_funil == 'FECHADO' and not self.valor_estimado:
            errors['valor_estimado'] = 'Valor obrigatório para fechar negócio.'

        if errors:
            raise ValidationError(errors)


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente.nome} - {self.get_produto_formato_display()}"
    
    # Garante que a data de criação seja salva automaticamente
    criado_em = models.DateTimeField(auto_now_add=True)
    
    # Novo campo para o próximo contato
    data_followup = models.DateField(null=True, blank=True, verbose_name="Data de Follow-up")

    # Propriedade inteligente para pintar o card no HTML
    @property
    def status_followup(self):
        if not self.data_followup:
            return 'sem_data'
        if self.data_followup < timezone.now().date():
            return 'atrasado' # Vermelho
        return 'no_prazo' # Verde

class Tarefa(models.Model):
    oportunidade = models.ForeignKey(Oportunidade, on_delete=models.CASCADE, related_name='tarefas')
    descricao = models.CharField(max_length=255)
    concluida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

class NotaHistorico(models.Model):
    oportunidade = models.ForeignKey(Oportunidade, on_delete=models.CASCADE, related_name='historicos')
    texto = models.TextField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Notas do Histórico"
        ordering = ['-criada_em']