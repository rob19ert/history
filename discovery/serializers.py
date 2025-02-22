from rest_framework import serializers
from .models import Discoverers, Discovery, DiscoveryDiscoverers
from django.contrib.auth.models import User
from collections import OrderedDict
from rest_framework.authtoken.admin import User
from django.contrib.auth.hashers import make_password
from django.utils.timezone import localtime
import pytz

class DiscoverersSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255)
    bio = serializers.CharField()
    long_description = serializers.CharField()
    status = serializers.ChoiceField(choices=[('active', 'Действует'), ('deleted', 'Неактивен')])
    image_url = serializers.URLField(required=False, allow_null=True)
    years_of_life = serializers.CharField(max_length=50)
    nationality = serializers.CharField(max_length=100)
    major_discovery = serializers.CharField(max_length=255)

    class Meta:
        model = Discoverers
        fields = ['id', 'name', 'bio', 'long_description', 'status', 'image_url', 'years_of_life', 'nationality', 'major_discovery']

    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.required = False
        return fields

class DiscoverySerializer(serializers.ModelSerializer):
    creator_login = serializers.CharField(source='creator.username', read_only=True)
    moderator_login = serializers.CharField(source='moderator.username', read_only=True, allow_null=True)
    region = serializers.CharField(max_length=255)
    discoverers = DiscoverersSerializer(many=True, read_only=True)

    created_at = serializers.SerializerMethodField()
    formed_at = serializers.SerializerMethodField()
    completed_at = serializers.SerializerMethodField()

    def get_local_time(self, dt):
        """Конвертирует время в московский часовой пояс и форматирует в стиль 'дд.мм.гггг чч:мм:сс'."""
        if dt:
            moscow_tz = pytz.timezone("Europe/Moscow")
            return localtime(dt, moscow_tz).strftime("%d.%m.%Y %H:%M:%S")  # Российский формат
        return None

    def get_created_at(self, obj):
        return self.get_local_time(obj.created_at)

    def get_formed_at(self, obj):
        return self.get_local_time(obj.formed_at)

    def get_completed_at(self, obj):
        return self.get_local_time(obj.completed_at)

    class Meta:
        model = Discovery
        fields = ['id', 'status', 'created_at', 'formed_at', 'completed_at', 'creator_login', 'moderator_login', 'region', 'discoverers', 'qr']
        read_only_fields = ['created_at', 'formed_at', 'completed_at', 'creator_login', 'moderator_login']

class DiscoveryDiscoverersSerializer(serializers.ModelSerializer):
    explorer = DiscoverersSerializer()
    is_primary = serializers.BooleanField(default=False)

    class Meta:
        model = DiscoveryDiscoverers
        fields = ['id', 'request', 'explorer', 'is_primary']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    is_staff = serializers.BooleanField(default=False)

    class Meta:
        model = User
        fields = ['id','username', 'password', 'email', 'first_name', 'last_name', 'is_staff']

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data.get('email'),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_staff=validated_data.get('is_staff', False),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'password']
        extra_kwargs = {'password': {'write_only': True, 'required': False}}

    def update(self, instance, validated_data):
        if 'password' in validated_data and validated_data['password']:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)




class UserSerializer(serializers.ModelSerializer):
    is_staff = serializers.BooleanField(default=False, required=False)
    is_superuser = serializers.BooleanField(default=False, required=False)
    class Meta:
        model = User
        fields = ['id','username', 'email', 'password', 'is_staff', 'is_superuser']

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            is_staff=validated_data['is_staff'],
            is_superuser=validated_data['is_superuser']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user
    

class AddDiscovererToDraftSerializer(serializers.ModelSerializer):
    explorer_id = serializers.PrimaryKeyRelatedField(
        queryset=Discoverers.objects.filter(status='active'),
        source='explorer',
        write_only=True
    )
    discovery_id = serializers.PrimaryKeyRelatedField(
        queryset=Discovery.objects.filter(status='draft'),
        source='request',
        write_only=True
    )
    is_primary = serializers.BooleanField(default=False)

    class Meta:
        model = DiscoveryDiscoverers
        fields = ['explorer_id', 'discovery_id', 'is_primary']

    def validate(self, data):
        explorer = data.get('explorer')
        discovery = data.get('request')

        # Дополнительные проверки, если нужно
        if not discovery:
            raise serializers.ValidationError({"discovery_id": "Черновик открытия не найден или не указан."})

        if not explorer:
            raise serializers.ValidationError({"explorer_id": "Исследователь не найден или не указан."})

        # Проверка, чтобы не добавлять дубликаты
        if DiscoveryDiscoverers.objects.filter(request=discovery, explorer=explorer).exists():
            raise serializers.ValidationError({"detail": "Этот исследователь уже добавлен в черновик."})

        return data

    def create(self, validated_data):
        return DiscoveryDiscoverers.objects.create(**validated_data)
