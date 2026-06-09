import os
import sys
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_mc4.settings')
django.setup()

client = Client()

# Fazer login
login_response = client.post('/accounts/login/', {
    'login': 'admin',
    'password': 'admin123'
}, follow=True)

print(f"Login response: {login_response.status_code}")

# Testar endpoints autenticados
endpoints = [
    ('/crm/', 'Dashboard'),
    ('/crm/kanban/', 'Kanban'),
    ('/crm/clientes/', 'Clientes'),
    ('/crm/comercial/', 'Comercial'),
]

print("\n=== TESTE DE ENDPOINTS COM LOGIN ===")
for endpoint, name in endpoints:
    response = client.get(endpoint)
    status_icon = "✅" if response.status_code == 200 else "⚠️" if response.status_code == 302 else "❌"
    print(f"{status_icon} {name:<15} ({endpoint:<20}): {response.status_code}")
