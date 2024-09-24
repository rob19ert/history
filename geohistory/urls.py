from django.contrib import admin
from django.urls import path
from discovery import views
from django.shortcuts import redirect  # Импортируем функцию редиректа

urlpatterns = [
    path('', lambda request: redirect('researchers', permanent=False), name='home'),  # Редирект на /researchers/
    path('researchers/', views.researchers_view, name='researchers'),  # Страница всех исследователей
    path('researcher/<int:id>/', views.researcher_detail_view, name='researcher_detail'),  # Детали исследователя
    path('backet/<int:id>/', views.getOrders, name='backet_view'),  # Страница корзины
]
