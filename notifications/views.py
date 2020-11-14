from django.shortcuts import render
from django.views.generic import (ListView, DetailView)
from .models import Notificacion
# Create your views here.


class NotificacionList(ListView):
    model = Notificacion
    context_object_name = 'notificacion'
    template_name='notifications/main_box.html'

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user).order_by('-date')
    