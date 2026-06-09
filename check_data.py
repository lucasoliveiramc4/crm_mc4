from comercial.models import Comercial, Cliente, Oportunidade

print('=== DADOS NO BANCO LOCAWEB ===')
print()
print(f'Comerciais (Vendedores): {Comercial.objects.count()}')
print(f'Clientes: {Cliente.objects.count()}')
print(f'Oportunidades: {Oportunidade.objects.count()}')

if Comercial.objects.exists():
    print('\nVendedores:')
    for v in Comercial.objects.all()[:3]:
        print(f'  - {v.nome} ({v.email})')

if Cliente.objects.exists():
    print('\nClientes:')
    for c in Cliente.objects.all()[:3]:
        print(f'  - {c.nome} ({c.get_tipo_display()})')

if Oportunidade.objects.exists():
    print('\nOportunidades:')
    for o in Oportunidade.objects.all()[:3]:
        print(f'  - {o.cliente.nome} - R$ {o.valor_estimado} ({o.get_estagio_funil_display()})')
