from rest_framework import serializers
from .models import Discoverers, Discovery, DiscoveryDiscoverers
from django.contrib.auth.models import User

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


class DiscoverySerializer(serializers.ModelSerializer):
    creator_login = serializers.CharField(source='creator.username', read_only=True)
    moderator_login = serializers.CharField(source='moderator.username', read_only=True, allow_null=True)
    region = serializers.CharField(max_length=255)
    discoverers = DiscoverersSerializer(many=True, read_only=True)
    
    class Meta:
        model = Discovery
        fields = ['id', 'status', 'created_at', 'formed_at', 'completed_at', 'creator_login', 'moderator_login', 'region', 'discoverers']
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
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 'is_staff']

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
        fields = ['username', 'email', 'first_name', 'last_name', 'is_staff']
