from django import forms
from .models import Oportunidade, Cliente, Comercial

class OportunidadeForm(forms.ModelForm):
    class Meta:
        model = Oportunidade
        # Apenas os campos que existem no seu modelo atual
        fields = [
            'cliente', 
            'agencia', 
            'vendedor_responsavel', 
            'produto_formato', 
            'valor_estimado', 
            'estagio_funil',
            'descricao', 
            'data_followup'
        ]
        widgets = {
            # Força o HTML a renderizar um calendário nativo
            'data_followup': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detalhes do briefing ou proposta...'}),
        }

   
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # ✅ recebe user
        super().__init__(*args, **kwargs)

        
        # ✅ Bootstrap em todos os campos
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Filtros de seleção no formulário
        self.fields['agencia'].queryset = Cliente.objects.filter(tipo='AGENCIA')
        self.fields['agencia'].required = False
        self.fields['cliente'].queryset = Cliente.objects.exclude(tipo='AGENCIA')

        
        # ✅ RESOLVE O PROBLEMA DE SALVAR CARD COM LOGIN COMERCIAL
        if user and user.groups.filter(name='Comercial').exists():
            self.fields.pop('vendedor_responsavel', None)


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        
        fields = [
                'nome',
                'contato',  # ✅ NOVO
                'segmento',
                'tipo',
                'vendedor_responsavel'
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'vendedor_responsavel': forms.Select(attrs={'class': 'form-control'}),
        }

class AgenciaForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'vendedor_responsavel']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'vendedor_responsavel': forms.Select(attrs={'class': 'form-control'}),
        }