from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.utils import timezone
from .models import Researchers, Request, RequestResearchers
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseBadRequest
from typing import Optional

@login_required
def researchers_view(request):
    query: str = request.GET.get('researcherName', '')  # Получаем запрос на поиск
    if query:
        # Фильтруем исследователей по имени
        filtered_researchers = Researchers.objects.filter(name__icontains=query, status='active')
    else:
        # Выводим всех активных исследователей
        filtered_researchers = Researchers.objects.filter(status='active')
    
    # Собираем все открытия, исключая удаленные заявки
    all_discoveries = RequestResearchers.objects.filter(
        explorer__in=filtered_researchers
    ).exclude(
        request__status='deleted'
    ).values_list('explorer__major_discovery', flat=True).distinct()
    
    count: int = RequestResearchers.objects.exclude(request__status='deleted').count()

    return render(request, 'cards_home.html', {
        'id_application': get_application_id(request.user),
        'researchers': filtered_researchers,
        'query': query,
        'all_discoveries': all_discoveries,
        'count': count,
    })

@login_required
def researcher_detail_view(request, id: int):
    researcher: Researchers = get_object_or_404(Researchers, id=id, status='active')
    count: int = RequestResearchers.objects.exclude(request__status='deleted').count()

    return render(request, 'card_info.html', {
        'researcher': researcher,
        'id_application': get_application_id(request.user),
        'count': count,
    })

@login_required
def getOrders(request, id: int):
    # Предполагается, что 'id' — это ID заявки
    user_request: Request = get_object_or_404(Request, id=id, creator=request.user, status='draft')
    services = user_request.requestresearchers_set.exclude(request__status='deleted')
    count: int = services.count()

    return render(request, 'order.html', {
        'order': user_request,
        'services': services,
        'id_application': user_request.id,
        'count': count,
    })

def get_application_id(user: User) -> Optional[int]:
    draft_request: Optional[Request] = Request.objects.filter(creator=user, status='draft').first()
    return draft_request.id if draft_request else None
    
@login_required
def add_service_to_request(request):
    if request.method == 'POST':
        service_id: str = request.POST.get('service_id')

        try:
            service: Researchers = Researchers.objects.get(id=service_id, status='active')
            user_request, created = Request.objects.get_or_create(
                creator=request.user,
                status='draft',
                defaults={'created_at': timezone.now(), 'region': 'Не указано'}
            )

            req_service, created = RequestResearchers.objects.get_or_create(
                request=user_request,
                explorer=service,
            )
            if not created:
                req_service.save()
            
            # Убедитесь, что user_request.id существует
            if user_request.id is not None:
                return redirect('backet_view', id=user_request.id)
            else:
                return redirect('researchers')  # Если ID отсутствует, перенаправляем на researchers

        except Researchers.DoesNotExist:
            return HttpResponseBadRequest("Услуга не найдена или недоступна.")
    else:
        return HttpResponseBadRequest("Неверный метод запроса.")
    
@login_required
def delete_request(request):
    if request.method == 'POST':
        user_request: Optional[Request] = Request.objects.filter(creator=request.user, status='draft').first()
        if user_request:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE discovery_request SET status = %s WHERE id = %s AND status = %s",
                    ['deleted', user_request.id, 'draft']
                )
        # Перенаправляем пользователя на страницу исследователей
        return redirect('researchers')
    else:
        return HttpResponseBadRequest("Неверный метод запроса.")