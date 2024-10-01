from django.urls import path
from . import views

urlpatterns = [
    path('requests/', views.request_list_view, name='request_list'),
    path('requests/create/', views.create_request_view, name='create_request'),
    path('requests/<int:id>/', views.request_detail_view, name='request_detail'),
]
