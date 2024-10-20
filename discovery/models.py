from django.db import models
from django.contrib.auth.models import User

class Discoverers(models.Model):
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    long_description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('deleted', 'Deleted')])
    image_url = models.CharField(max_length=100, blank=True, null=True)
    years_of_life = models.CharField(max_length=50)
    nationality = models.CharField(max_length=50)
    major_discovery = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class Discovery(models.Model):
    STATUS_CHOICES = [
        ('draft','Draft'),
        ('deleted','Deleted'),
        ('formed', 'Formes'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    formed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_requests')
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='moderator_requests', blank=True)
    region = models.CharField(max_length=100)
    

    def __str__(self):
        return f"Request by {self.creator} - Status: {self.status}"
    
class DiscoveryDiscoverers(models.Model):
    request = models.ForeignKey(Discovery, on_delete=models.CASCADE)
    explorer = models.ForeignKey(Discoverers, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.explorer.name} in request {self.request.id}"

