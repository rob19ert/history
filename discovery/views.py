from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.utils import timezone
from .models import Discoverers, Discovery, DiscoveryDiscoverers
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseBadRequest
from typing import Optional

@login_required
def discoverers_view(request):
    query: str = request.GET.get('discovererName', '')  # Получаем запрос на поиск
    if query:
        # Фильтруем исследователей по имени
        filtered_discoverers = Discoverers.objects.filter(name__icontains=query, status='active')
    else:
        # Выводим всех активных исследователей
        filtered_discoverers = Discoverers.objects.filter(status='active')
    
    # Собираем все открытия, исключая удаленные заявки
    all_discoveries = DiscoveryDiscoverers.objects.filter(
        explorer__in=filtered_discoverers
    ).exclude(
        request__status='deleted'
    ).values_list('explorer__major_discovery', flat=True).distinct()
    
    count: int = DiscoveryDiscoverers.objects.exclude(request__status='deleted').count()

    return render(request, 'cards_home.html', {
        'id_application': get_application_id(request.user),
        'discoverers': filtered_discoverers,
        'query': query,
        'all_discoveries': all_discoveries,
        'count': count,
    })

@login_required
def discoverer_detail_view(request, id: int):
    discoverer: Discoverers = get_object_or_404(Discoverers, id=id, status='active')
    count: int = DiscoveryDiscoverers.objects.exclude(request__status='deleted').count()

    return render(request, 'card_info.html', {
        'discoverer': discoverer,
        'id_application': get_application_id(request.user),
        'count': count,
    })

@login_required
def getOrders(request, id: int):
    # Предполагается, что 'id' — это ID заявки
    user_request: Discovery = get_object_or_404(Discovery, id=id, creator=request.user, status='draft')
    services = user_request.discoverydiscoverers_set.exclude(request__status='deleted')
    count: int = services.count()

    return render(request, 'order.html', {
        'order': user_request,
        'services': services,
        'id_application': user_request.id,
        'count': count,
    })

def get_application_id(user: User) -> Optional[int]:
    draft_request: Optional[Discovery] = Discovery.objects.filter(creator=user, status='draft').first()
    return draft_request.id if draft_request else None
    
@login_required
def add_service_to_request(request):
    if request.method == 'POST':
        service_id: str = request.POST.get('service_id')

        try:
            service: Discoverers = Discoverers.objects.get(id=service_id, status='active')
            user_request, created = Discovery.objects.get_or_create(
                creator=request.user,
                status='draft',
                defaults={'created_at': timezone.now(), 'region': 'Не указано'}
            )

            req_service, created = DiscoveryDiscoverers.objects.get_or_create(
                request=user_request,
                explorer=service,
            )
            if not created:
                req_service.save()
            
            # Убедитесь, что user_request.id существует
            if user_request.id is not None:
                return redirect('discovery_view', id=user_request.id)
            else:
                return redirect('discoverers')  # Если ID отсутствует, перенаправляем на Discoverers

        except Discoverers.DoesNotExist:
            return HttpResponseBadRequest("Услуга не найдена или недоступна.")
    else:
        return HttpResponseBadRequest("Неверный метод запроса.")
    
@login_required
def delete_request(request):
    if request.method == 'POST':
        user_request: Optional[Discovery] = Discovery.objects.filter(creator=request.user, status='draft').first()
        if user_request:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE discovery_discovery SET status = %s WHERE id = %s AND status = %s",
                    ['deleted', user_request.id, 'draft']
                )
        # Перенаправляем пользователя на страницу исследователей
        return redirect('discoverers')
    else:
        return HttpResponseBadRequest("Неверный метод запроса.")