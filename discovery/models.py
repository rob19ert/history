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
    region = models.CharField(max_length=100, blank=True, null=True)
    discoverers = models.ManyToManyField(Discoverers, through='DiscoveryDiscoverers', related_name='discoveries')
    qr = models.TextField(null=True, blank=True)
    

    def __str__(self):
        return f"Request by {self.creator} - Status: {self.status}"
    
class DiscoveryDiscoverers(models.Model):
    request = models.ForeignKey(Discovery, on_delete=models.CASCADE)
    explorer = models.ForeignKey(Discoverers, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.explorer.name} in request {self.request.id}"
    

'''
class NewUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('User must have an email address')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self.db)
        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(("email адрес"), unique=True)
    password = models.CharField(max_length=50, verbose_name="Пароль")
    is_staff = models.BooleanField(default=False, verbose_name="Является ли пользователь менеджером?")
    is_superuser = models.BooleanField(default=False, verbose_name="Является ли пользователь админом?")
    groups = models.ManyToManyField(Group, related_name='customuser_set', blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name='customuser_set', blank=True)
    USERNAME_FIELD = 'email'

    objects = NewUserManager()
'''

