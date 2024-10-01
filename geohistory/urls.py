from django.contrib import admin
from django.urls import path
from discovery import views
from django.shortcuts import redirect  # Импортируем функцию редиректа

from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('researchers', permanent=False), name='home'),
    path('researchers/', views.researchers_view, name='researchers'),
    path('researcher/<int:id>/', views.researcher_detail_view, name='researcher_detail'),
    path('backet/<int:id>/', views.getOrders, name='backet_view'),
    path('add_service/', views.add_service_to_request, name='add_service_to_request'),
    path('delete_request/', views.delete_request, name='delete_request'),
    
]

