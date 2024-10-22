from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from minio import Minio, S3Error
from django.conf import settings
from .models import Discoverers, Discovery, DiscoveryDiscoverers
from .serializers import DiscoverersSerializer, DiscoverySerializer, DiscoveryDiscoverersSerializer, RegisterSerializer, UserUpdateSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.generics import UpdateAPIView
from urllib.parse import urlparse
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth.models import update_last_login
from .utils import add_image

# Настройка MinIO клиента
minio_client = Minio(
    settings.MINIO_STORAGE_ENDPOINT,
    access_key=settings.MINIO_STORAGE_ACCESS_KEY,
    secret_key=settings.MINIO_STORAGE_SECRET_KEY,
    secure=settings.MINIO_STORAGE_USE_HTTPS
)

def get_creator():
   return User.objects.get(username=settings.CREATOR_USERNAME)

class DiscovererList(APIView):
    permission_classes = [IsAuthenticated]
    model_class = Discoverers
    serializer_class = DiscoverersSerializer

    # Возвращает список всех активных первооткрывателей
    def get(self, request):
        discoverers = Discoverers.objects.filter(status='active')
        name = request.query_params.get('name')
        if name:
            discoverers = discoverers.filter(name__icontains = name)

        serializer = DiscoverersSerializer(discoverers, many=True)

        draft_discovery = Discovery.objects.filter(creator=request.user, status='draft').first()
        draft_id = draft_discovery.id if draft_discovery else None
        draft_count = draft_discovery.discoverydiscoverers_set.count() if draft_discovery else 0

        return Response ({
            'discoverers':serializer.data,
            'draft_id': draft_id,
            'draft_count': draft_count
        })
    # Добавляет нового первооткрывателя
    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#Подробная информация о первооткрывателях
class DiscoverersDetail(APIView):
    permission_classes = [IsAuthenticated]
    model_class = Discoverers
    serializer_class = DiscoverersSerializer

    # Возвращает информацию о конкретном первооткрывателе
    def get(self, request, pk, format=None):
        try:
            discoverer = Discoverers.objects.get(pk=pk, status = 'active')
        except Discoverers.DoesNotExist:
            return Response({"Данного первооткрывателя не сущесвует"})
        serializer = self.serializer_class(discoverer)
        return Response(serializer.data)

    # Обновляет информацию о первооткрывателе (только активные записи)
    def put(self, request, pk, format=None):
        discoverer = get_object_or_404(self.model_class, pk=pk)
        serializer = self.serializer_class(discoverer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Удаляет первооткрывателя (мягкое удаление, ставит статус 'deleted')
    def delete(self, request, pk, format=None):
        discoverer = get_object_or_404(self.model_class, pk=pk)
        if discoverer.image_url:
            try:
                parsed_url = urlparse(discoverer.image_url)
                object_name = parsed_url.path.lstrip('/')
                minio_client.remove_object(settings.MINIO_STORAGE_BUCKET_NAME, object_name)
            except S3Error as e:
                return Response({'error': f"Ошибка при удалении из Minio: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
       
        discoverer.delete()
        return Response({'message': "Первооткрыватель успешно добавлен"}, status=status.HTTP_204_NO_CONTENT)
    
class AddDiscovererToDraft(APIView):  # Изменено имя класса на более подходящее
    permission_classes = [IsAuthenticated]

    def post(self, request):
        creator = request.user  # Получаем текущего аутентифицированного пользователя
        explorer_id = request.data.get('explorer_id')

        # Проверка наличия explorer_id в запросе
        if not explorer_id:
            return Response({"error": "Не предоставлен explorer_id"}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка существования исследователя
        try:
            discoverer = Discoverers.objects.get(id=explorer_id)
        except Discoverers.DoesNotExist:
            return Response({"error": "Исследователь не найден"}, status=status.HTTP_404_NOT_FOUND)

        # Получение или создание запроса в статусе 'draft'
        discovery, created = Discovery.objects.get_or_create(
            creator=creator,
            status='draft',
            defaults={
                'region': None,
                'completed_at': None,
                'formed_at': None,
                'moderator': None,
            }
        )

        # Проверка на наличие исследователя в запросе
        if DiscoveryDiscoverers.objects.filter(request=discovery, explorer=discoverer).exists():
            return Response({'error': 'Исследователь уже добавлен'}, status=status.HTTP_400_BAD_REQUEST)

        # Добавление исследователя в запрос
        DiscoveryDiscoverers.objects.create(
            request=discovery,
            explorer=discoverer,
            is_primary=True  # Здесь можно установить значение по умолчанию
        )

        return Response({
            "message": "Исследователь успешно добавлен",
            "discovery_id": discovery.id  # Возвращаем ID запроса для дальнейшего использования
        }, status=status.HTTP_201_CREATED)

class DiscoveryList(APIView):
    permission_classes=[IsAuthenticated]
    model_class = Discovery
    serializer_class = DiscoverySerializer

    # Возвращает список заявок, кроме удаленных и черновика
    def get(self, request, format=None):
        discoveries = self.model_class.objects.exclude(status__in = ['deleted', 'draft'])
        status_filter = request.query_params.get('status', None)
        start_date = request.query_params.get('start_date',None)
        end_date = request.query_params.get('end_date', None)

        if status_filter:
            discoveries = discoveries.filter(status = status_filter)

        if start_date and end_date:
            start_date = parse_date(start_date)
            end_date = parse_date(end_date)
            discoveries = discoveries.filter(submit_sate__range=[start_date, end_date])

        serializer = self.serializer_class(discoveries, many=True)
        return Response(serializer.data)


class DiscoveryListDetail(APIView):
    permission_classes=[IsAuthenticated]
    model_class = Discovery
    serializer_class = DiscoverySerializer

    # Возвращает информацию о заявке
    def get(self, request, pk, format=None):
        discovery = get_object_or_404(self.model_class, pk=pk)
        serializer = self.serializer_class(discovery)
        return Response(serializer.data)

    # Обновляет заявку (только создатель или модератор)
    def put(self, request, pk, format=None):
        discovery = get_object_or_404(self.model_class, pk=pk)
        region = request.data.get('region')
        if region == None:
            return Response({"error": "Поле region не может быть пустым"}, status=status.HTTP_400_BAD_REQUEST)
        discovery.region = region
        discovery.save()
        serializer = self.serializer_class(discovery)
        return Response(serializer.data)

    # Мягкое удаление заявки
    def delete(self, request, pk, format=None):
        try:
             discovery = self.model_class.objects.get(pk=pk)
        except self.model_class.DoesNotExist:
             return Response({"error": "Заявка не найдена"}, status=status.HTTP_404_NOT_FOUND)
    
        if discovery.status == 'deleted':
            return Response({"error": "Заявка уже удалена"}, status=status.HTTP_400_BAD_REQUEST)
    
        discovery.status = 'deleted'
        discovery.completed_at = timezone.now()
        discovery.save()
    
        return Response({"message": "Заявка успешно удалена"}, status=status.HTTP_200_OK)


class DiscoverySubmitView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self,request,pk):
        discovery = get_object_or_404(Discovery,pk=pk)
        if discovery.creator != request.user:
            return Response("Вы должны быть создателем заявки",status=status.HTTP_400_BAD_REQUEST)
        if discovery.status != 'draft':
            return Response("Заявка уже была сформированна",status=status.HTTP_400_BAD_REQUEST)
        if discovery.region == None:
            return Response("Поле region обязательно должно быть заполнено",status=status.HTTP_400_BAD_REQUEST)

        discovery.formed_at = timezone.now()
        discovery.status = "submitted"
        discovery.save()
        serializer = DiscoverySerializer(discovery)
        return Response(serializer.data)
    

class CompleteOrRejectDiscovery(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            discovery = Discovery.objects.get(pk=pk, status='submitted')
        except Discovery.DoesNotExist:
            return Response({"error": "Заявка не найдена или не находится в статусе ожидания модерации"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff:
            return Response({"error": "Доступ запрещен, вы не являетесь модератором"}, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        if action not in ['complete', 'reject']:
            return Response({"error": "Неверное действие. Ожидается 'complete' или 'reject'"}, status=status.HTTP_400_BAD_REQUEST)

        discovery.moderator = request.user
        discovery.completed_at = timezone.now()
        if action == 'complete':
            discovery.status = 'completed'
        elif action == 'reject':
            discovery.status = 'rejected'

        discovery.save()
        serializer = DiscoverySerializer(discovery)

        return Response({
            "message": f"Заявка успешно {('завершена' if action == 'complete' else 'отклонена')}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

class UploadImageForDiscover(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        discoverer = get_object_or_404(Discoverers, pk=pk)

        if discoverer.image_url:
            try:
                parsed_url = urlparse(discoverer.image_url)
                object_name = parsed_url.path.lstrip('/')
                minio_client.remove_object(settings.MINIO_STORAGE_BUCKET_NAME, object_name)
            except S3Error as e:
                return Response({'error': f'Ошибка в удалении старого изображения {str(e)}'},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        image = request.FILES.get('image')
        if not image:
            return Response({'error': 'Нет предоставленного изображения'}, status=status.HTTP_400_BAD_REQUEST)

        image_result = add_image(discoverer, image)
        if 'error' in image_result.data:
            return image_result

        return Response({'message': 'Изображение успешно загружено', 'image_url': discoverer.image_url},
                        status=status.HTTP_200_OK)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Пользователь успешно зарегистрирован",
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_staff": user.is_staff
                }
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UserLogin(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = AuthTokenSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            update_last_login(None, user)
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff,
                }
            }, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class UserUpdate(UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self):
        return self.request.user
    
class UserLogout(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = request.auth
            token.delete()
            return Response({"message": "Вы успешно вышли из системы."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class UpdateDiscoveryDiscoverer(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, discovery_id, discoverer_id):
        # Получение поля для обновления из тела запроса
        is_primary = request.data.get('is_primary', None)

        # Получение записи через M2M модель
        discovery_discoverer = get_object_or_404(DiscoveryDiscoverers, request_id=discovery_id, explorer_id=discoverer_id)

        # Обновление значения поля
        if is_primary is not None:
            discovery_discoverer.is_primary = is_primary
        
        discovery_discoverer.save()

        # Сериализация и возврат обновленных данных
        serializer = DiscoveryDiscoverersSerializer(discovery_discoverer)
        return Response(serializer.data, status=status.HTTP_200_OK)

class RemoveDiscovererFromDiscovery(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, discovery_id, discoverer_id):
        # Получаем M2M связь через модель DiscoveryDiscoverers
        relation = get_object_or_404(DiscoveryDiscoverers, request_id=discovery_id, explorer_id=discoverer_id)

        # Удаляем запись
        relation.delete()

        return Response({"message": "Путешественник успешно удален из открытия."}, status=status.HTTP_200_OK)

