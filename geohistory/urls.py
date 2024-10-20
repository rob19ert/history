from django.contrib import admin
from django.urls import path
from discovery import views
from django.shortcuts import redirect  # Импортируем функцию редиректа

from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('discoverers', permanent=False), name='home'),
    path('discoverers/', views.discoverers_view, name='discoverers'),
    path('discoverer/<int:id>/', views.discoverer_detail_view, name='discoverer_detail'),
    path('discovery/<int:id>/', views.getOrders, name='discovery_view'),
    path('add_service/', views.add_service_to_request, name='add_service_to_request'),
    path('delete_request/', views.delete_request, name='delete_request'),
    
]

