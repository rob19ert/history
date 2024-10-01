from django.contrib import admin
from .models import Researchers, Request, RequestResearchers

@admin.register(Researchers)
class ResearchersAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'years_of_life', 'nationality')
    search_fields = ('name', 'nationality', 'major_discovery')
    list_filter = ('status', 'nationality')

@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'creator', 'status', 'created_at', 'region')
    search_fields = ('creator__username', 'region', 'status')
    list_filter = ('status', 'created_at', 'region')

@admin.register(RequestResearchers)
class RequestResearchersAdmin(admin.ModelAdmin):
    list_display = ('request', 'explorer', 'is_primary')
    search_fields = ('request__id', 'explorer__name')
    list_filter = ('is_primary',)
