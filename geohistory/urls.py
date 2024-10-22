from django.urls import path
from django.contrib import admin
from rest_framework.authtoken.views import obtain_auth_token
from discovery.views import (
    DiscovererList, DiscoverersDetail, DiscoveryList, DiscoveryListDetail, DiscoverySubmitView,
    CompleteOrRejectDiscovery, UploadImageForDiscover, RegisterView, UserLogin, UserUpdate,
    UserLogout, UpdateDiscoveryDiscoverer, RemoveDiscovererFromDiscovery,AddDiscovererToDraft
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token-auth/', obtain_auth_token, name='api_token_auth'),
    path('discoverers/', DiscovererList.as_view(), name='discoverer-list'),
    path('discoverers/<int:pk>/', DiscoverersDetail.as_view(), name='discoverer-detail'),
    path('discoveries/', DiscoveryList.as_view(), name='discovery-list'),
    path('discoveries/<int:pk>/', DiscoveryListDetail.as_view(), name='discovery-detail'),
    path('discoveries/add-discoverer/', AddDiscovererToDraft.as_view(), name='add-discoverer-to-draft'),
    path('discoveries/<int:pk>/submit/', DiscoverySubmitView.as_view(), name='discovery-submit'),
    path('discoveries/<int:pk>/complete_or_reject/', CompleteOrRejectDiscovery.as_view(), name='discovery-complete-reject'),
    path('discoverers/<int:pk>/upload-image/', UploadImageForDiscover.as_view(), name='upload-image'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', UserLogin.as_view(), name='login'),
    path('update-profile/', UserUpdate.as_view(), name='user-update'),
    path('logout/', UserLogout.as_view(), name='logout'),
    path('discoveries/<int:discovery_id>/explorers/<int:discoverer_id>/update/', UpdateDiscoveryDiscoverer.as_view(), name='update-discovery-discoverer'),
    path('discoveries/<int:discovery_id>/explorers/<int:discoverer_id>/remove/', RemoveDiscovererFromDiscovery.as_view(), name='remove-discovery-discoverer'),
    
]
