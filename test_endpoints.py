import os
import sys
import django
from django.test import Client
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_mc4.settings')
django.setup()

User = get_user_model()

# Criar um cliente HTTP
client = Client()

# Fazer login
login_success = client.login(username='admin', password='admin')
print(f"✅ Login successful: {login_success}")

# Testar endpoints
endpoints = [
    '/crm/',
    '/crm/kanban/',
    '/crm/clientes/',
    '/crm/comercial/',
]

print("\n=== TESTE DE ENDPOINTS ===")
for endpoint in endpoints:
    response = client.get(endpoint)
    status = "✅" if response.status_code in [200, 302] else "❌"
    template = response.template_name if hasattr(response, 'template_name') else "redirect"
    print(f"{status} {endpoint:<20} Status: {response.status_code:<3} Template: {template}")
