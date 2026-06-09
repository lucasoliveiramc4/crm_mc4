from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Comercial


@receiver(post_save, sender=User)
def criar_comercial_automatico(sender, instance, created, **kwargs):

    if created:
        Comercial.objects.create(
            user=instance,
            nome=instance.username,
            email=instance.email or f"{instance.username}@email.com"
        )