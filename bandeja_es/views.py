import pathlib
import os.path
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.forms import formset_factory
from django.core.exceptions import ValidationError
from django.urls import (reverse_lazy, reverse)
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.generic.base import TemplateView, RedirectView, View
from django.core.files.storage import FileSystemStorage
from django.views.generic import (ListView, DetailView, CreateView, UpdateView, DeleteView, FormView)
from formtools.wizard.views import SessionWizardView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError

from panel_carga.views import ProyectoMixin
from .models import Version, Paquete, BorradorPaquete, PrevVersion, PrevPaquete, PrevPaqueteDocumento, PaqueteDocumento
from .forms import VersionDocPreview,PreviewVersionSet, VersionDocPreview, CreatePaqueteForm, VersionFormset, PaquetePreviewForm, PrevVersionForm
from .filters import PaqueteFilter, PaqueteDocumentoFilter, BorradorFilter
from panel_carga.filters import DocFilter
from panel_carga.models import Documento
from panel_carga.choices import TYPES_REVISION
from .serializers import PrevVersionSerializer

# Create your views here.

class InBoxView(ProyectoMixin, ListView):
    model = Paquete
    template_name = 'bandeja_es/baes.html'
    context_object_name = 'paquetes'
    paginate_by = 15

    def get_queryset(self):
        pkg =  Paquete.objects.filter(destinatario=self.request.user)
        lista_paquetes_filtrados = PaqueteFilter(self.request.GET, queryset=pkg)
        return  lista_paquetes_filtrados.qs.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = PaqueteFilter(self.request.GET, queryset=self.get_queryset())
        return context
    
class EnviadosView(ProyectoMixin, ListView):
    model = Paquete
    template_name = 'bandeja_es/baes_Enviado.html'
    context_object_name = 'paquetes'
    paginate_by = 10

    def get_queryset(self):
        pkg =  Paquete.objects.filter(owner=self.request.user)
        lista_paquetes_filtrados = PaqueteFilter(self.request.GET, queryset=pkg)
        return  lista_paquetes_filtrados.qs.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = PaqueteFilter(self.request.GET, queryset=self.get_queryset())
        return context

class PaqueteDetail(ProyectoMixin, DetailView):
    model = Paquete
    template_name = 'bandeja_es/paquete-detail.html'
    context_object_name = 'paquete'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paquete = Paquete.objects.get(pk=self.kwargs['pk'])
        versiones = PaqueteDocumento.objects.filter(paquete=paquete)
        context['versiones'] = versiones
        return context

class PaqueteUpdate(ProyectoMixin, UpdateView):
    model = Paquete
    template_name = 'bandeja_es/paquete-update.html'
    form_class = CreatePaqueteForm
    success_url = reverse_lazy('paquete-detalle')
class PaqueteDelete(ProyectoMixin, DeleteView):
    model = Paquete
    template_name = 'bandeja_es/paquete-delete.html'
    success_url = reverse_lazy('Bandejaeys')
    context_object_name = 'paquete'

class BorradorList(ProyectoMixin, ListView):
    template_name = 'bandeja_es/borrador.html'
    paginate_by = 15

    def get_queryset(self):
        qs =  BorradorPaquete.objects.filter(owner=self.request.user)
        lista_borradores_filtrados = BorradorFilter(self.request.GET, queryset=qs)
        return  lista_borradores_filtrados.qs.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        draft = BorradorPaquete.objects.filter(owner=self.request.user)
        context["filter"] = BorradorFilter(self.request.GET, queryset=self.get_queryset())
        borrador_paquete = BorradorPaquete.objects.all().filter(owner=self.request.user).order_by('-fecha_creacion')
        context['borrador_paquete'] = borrador_paquete
        return context

def create_borrador(request, paquete_pk):
    prev_paquete = PrevPaquete.objects.get(pk=paquete_pk)
    try:
        borrador = BorradorPaquete(
            owner= request.user,
            prev_paquete= prev_paquete
        )
        borrador.save()
        # integrar mensaje de success
    except IntegrityError:
        pass 
        # integrar mensaje de error
    return HttpResponseRedirect(reverse_lazy('Borradores'))

class BorradorDelete(ProyectoMixin, DeleteView):
    model = BorradorPaquete
    success_url = reverse_lazy('Bandejaeys')
    pass

def create_paquete(request, paquete_pk, versiones_pk):
    context = {}
    if request.method == 'GET':

    #########################################################
    #             Transformación de str                     #
    #                a Lista de Pk's                        #
        lista_nueva = versiones_pk.lstrip("[").rstrip("]")
        new_list = lista_nueva.replace(',', "")
        versiones_pk_1 = list(new_list.split())
        versiones_pk_list = list(map(int, versiones_pk_1))
    #                                                       #
    #                                                       #
    #########################################################

        paquete_prev = PrevPaquete.objects.get(pk=paquete_pk)
        paquete = Paquete(
            asunto = paquete_prev.prev_asunto,
            descripcion = paquete_prev.prev_descripcion,
            destinatario = paquete_prev.prev_receptor,
            owner = paquete_prev.prev_propietario,
        )
        paquete.save()
        for v in versiones_pk_list:
            vertion = PrevVersion.objects.get(pk=v)
            vertion_f = Version(
                owner= vertion.prev_owner,
                documento_fk= vertion.prev_documento_fk,
                archivo= vertion.prev_archivo,
                comentario= vertion.prev_comentario,
                revision= vertion.prev_revision,
                estado_cliente= vertion.prev_estado_cliente,
                estado_contratista= vertion.prev_estado_contratista,
            )
            vertion_f.save()
            paquete.version.add(vertion_f)


        return HttpResponseRedirect(reverse_lazy('Bandejaeys'))

def verificar_nombre_archivo(nombre_documento, nombre_archivo):
    try:
        index = nombre_archivo.index('.')
    except ValueError:
        index = len(nombre_archivo)

    cleaned_name = nombre_archivo[:index]
    extencion = nombre_archivo[index:]

    if nombre_documento == cleaned_name:
        return True, extencion
    else:
        return False, extencion

# URL PARA SELECT2
def documentos_ajax(request):
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        terms = request.GET.get('term')
        documentos = Documento.objects.filter(proyecto=request.session.get('proyecto'), Codigo_documento__icontains=terms)
        response_content = list(documentos.values()) 
    # return JsonResponse(response_content,safe=False)
    return JsonResponse(response_content, safe=False)

def version_prev(request, paquete_pk):
    context = {}

    if request.method == 'GET':
        form = VersionDocPreview()
        context['form'] = form
        context['paquete'] = paquete_pk
        lista_versiones_pk = []
        package = PrevPaquete.objects.get(pk=paquete_pk)
        pkg_versiones = PrevPaqueteDocumento.objects.filter(prev_paquete=package)
        for version in pkg_versiones:
            pk = version.prev_version.pk
            lista_versiones_pk.append(pk)
        versiones = PrevVersion.objects.filter(pk__in=lista_versiones_pk)
        response_content = list(versiones.values())
    return render(request, 'bandeja_es/tabla-versiones-form.html', context)
    #### AJAX Request ####

def vue_version(request, paquete_pk):
    #### GET request para   ####        
    ####  Obtener las versiones ####        
    if request.method == 'GET':
        lista_versiones_pk = []
        package = PrevPaquete.objects.get(pk=paquete_pk)
        pkg_versiones = PrevPaqueteDocumento.objects.filter(prev_paquete=package)
        for version in pkg_versiones:
            pk = version.prev_version.pk
            lista_versiones_pk.append(pk)
        versiones = PrevVersion.objects.filter(pk__in=lista_versiones_pk)
        response_content = list(versiones.values())
        
    return JsonResponse(response_content, safe=False)

class PrevPaqueteView(ProyectoMixin, FormView):
    template_name = 'bandeja_es/crear-pkg-modal.html'
    form_class = PaquetePreviewForm

    def form_valid(self, form, **kwargs):
        paquete = form.save(commit=False)
        paquete.prev_propietario = self.request.user
        paquete.save()
        paquete_pk = paquete.pk
        return redirect('nueva-version', paquete_pk=paquete_pk)

class TablaPopupView(ProyectoMixin, ListView):
    model = PrevVersion
    template_name = 'bandeja_es/tabla-versiones-form.html'

    def get_context_data(self, **kwargs):
        versiones = []
        context = super().get_context_data(**kwargs)
        paquete = PrevPaquete.objects.get( pk=self.kwargs['paquete_pk'] )
        vertions = PrevPaqueteDocumento.objects.filter(prev_paquete=paquete).order_by('-prev_fecha_creacion')
        for version in vertions:
            versiones.append(version.prev_version)
        print(versiones)
        context['versiones'] = versiones
        context["paquete_pk"] = self.kwargs['paquete_pk']
        return context
    
    def post(self, request, *args, **kwargs):
        context={}
        versiones = []
        versiones_pk = []
        paquete = PrevPaquete.objects.get( pk=self.kwargs['paquete_pk'] )
        context['paquete'] = paquete
        vertions = PrevPaqueteDocumento.objects.filter(prev_paquete=paquete)
        for version in vertions:
            versiones.append(version.prev_version)
        for v in versiones:
            versiones_pk.append(v.pk)
        context['versiones'] = versiones
        context['versiones_pk'] = versiones_pk
        return render(request, 'bandeja_es/create-paquete.html', context)

class PrevVersionView(ProyectoMixin, FormView):
    model = PrevVersion
    template_name = 'bandeja_es/popup-archivo.html'
    form_class = PrevVersionForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paquete = PrevPaquete.objects.get(pk= self.kwargs['paquete_pk'])
        context["paquete_pk"] = paquete
        return context
    
    def form_valid(self, form, **kwargs):
        version = form.save(commit=False)
        version.prev_owner = self.request.user
        version.save()
        paquete = PrevPaquete.objects.get(pk=self.kwargs['paquete_pk'])
        paquete.prev_documento.add(version)
        return HttpResponse('<script type="text/javascript"> window.opener.location.reload(); window.close(); </script>')
