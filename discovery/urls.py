from django.urls import path
from . import views

urlpatterns = [
    path('', views.researchers_view, name='researchers'),
    path('cart/', views.cart_view, name='cart_view'),
]
