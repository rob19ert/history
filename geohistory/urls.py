from django.contrib import admin
from rest_framework import permissions
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from discovery.views import (
    DiscovererList, DiscoverersDetail, DiscoveryList, DiscoveryListDetail, DiscoverySubmitView,
    UserViewSet, UserUpdate, login_view, logout_view,
    CompleteOrRejectDiscovery, UploadImageForDiscover, UpdateDiscoveryDiscoverer, RemoveDiscovererFromDiscovery,
    AddDiscovererToDraft
)

# Создание роутера и регистрация UserViewSet
router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

# Создание схемы Swagger
schema_view = get_schema_view(
   openapi.Info(
      title="Geographical Discoveries API",  # Измените название на более подходящее
      default_version='v1',
      description="API for managing geographical discoveries and explorers",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@geodiscoveries.com"),  # Замените на актуальный контакт
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/', include(router.urls)),
    # path('api/token-auth/', obtain_auth_token, name='api_token_auth'),  # Включите, если необходимо
    path('discoverers/', DiscovererList.as_view(), name='discoverer-list'),
    path('discoverers/<int:pk>/', DiscoverersDetail.as_view(), name='discoverer-detail'),
    path('discoveries/', DiscoveryList.as_view(), name='discovery-list'),
    path('discoveries/<int:pk>/', DiscoveryListDetail.as_view(), name='discovery-detail'),
    path('discoveries/add-discoverer/', AddDiscovererToDraft.as_view(), name='add-discoverer-to-draft'),
    path('discoveries/<int:pk>/submit/', DiscoverySubmitView.as_view(), name='discovery-submit'),
    path('discoveries/<int:pk>/complete_or_reject/', CompleteOrRejectDiscovery.as_view(), name='discovery-complete-reject'),
    path('discoverers/<int:pk>/upload-image/', UploadImageForDiscover.as_view(), name='upload-image'),
    #path('register/', UserViewSet.as_view(), name='register'),
    path('api/login/', login_view, name='login'),
    path('update-profile/', UserUpdate.as_view(), name='user-update'),
    path('api/', include(router.urls)),  # Роуты для пользователей через роутер
    path('logout/', logout_view, name='logout'),
    path('discoveries/<int:discovery_id>/explorers/<int:discoverer_id>/update/', UpdateDiscoveryDiscoverer.as_view(), name='update-discovery-discoverer'),
    path('discoveries/<int:discovery_id>/explorers/<int:discoverer_id>/remove/', RemoveDiscovererFromDiscovery.as_view(), name='remove-discovery-discoverer'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
