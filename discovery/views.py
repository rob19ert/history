from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from minio import Minio, S3Error
from django.conf import settings
from .models import Discoverers, Discovery, DiscoveryDiscoverers
from .serializers import DiscoverersSerializer, DiscoverySerializer, DiscoveryDiscoverersSerializer, RegisterSerializer, UserUpdateSerializer, UserSerializer
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
from .utils import add_image, delete_image
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import permission_classes
from rest_framework import viewsets
from rest_framework import status, permissions
from rest_framework.decorators import authentication_classes
from drf_yasg import openapi
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
#import redis
import uuid

#session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

# Permissions
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Manager').exists()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [AllowAny]
        elif self.action in ['list']:
            permission_classes = [IsAdmin | IsManager]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

def method_permission_classes(classes):
    def decorator(func):
        def decorated_func(self, *args, **kwargs):
            self.permission_classes = classes        
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)
        return decorated_func
    return decorator

@permission_classes([AllowAny])  # разрешаем доступ любому пользователю
@authentication_classes([])  # не используем аутентификацию для этого эндпоинта
@csrf_exempt  # отключаем CSRF для тестов с Postman или Swagger
@swagger_auto_schema(method='post', request_body=UserSerializer())
@api_view(['POST'])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    # Попытка аутентификации пользователя
    user = authenticate(request, username=username, password=password)
    if user is not None:
        # Вход пользователя в систему
        login(request, user)  # Django автоматически установит cookie для сессии
        random_key = str(uuid.uuid4())
        session_storage.set(random_key, username)
        request.session['random_key'] = random_key
        # Ответ с успешным логином
        return Response({'status': 'ok'})
    else:
        # Ошибка логина
        return Response({'status': 'error', 'error': 'login failed'}, status=400)

@api_view(['POST'])
def logout_view(request):
    logout(request._request)
    return Response({'status': 'Success'})

# Настройка MinIO клиента
minio_client = Minio(
    settings.MINIO_STORAGE_ENDPOINT,
    access_key=settings.MINIO_STORAGE_ACCESS_KEY,
    secret_key=settings.MINIO_STORAGE_SECRET_KEY,
    secure=settings.MINIO_STORAGE_USE_HTTPS
)

class DiscovererList(APIView):
    permission_classes = [IsAuthenticated]
    model_class = Discoverers
    serializer_class = DiscoverersSerializer

    @swagger_auto_schema(
        operation_summary="Получить список первооткрывателей",
        responses={200: DiscoverersSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter(
                'name', 
                openapi.IN_QUERY, 
                description="Имя первооткрывателя", 
                type=openapi.TYPE_STRING, 
                required=False
            )
        ]
    )
    def get(self, request):
        # Получение списка всех активных первооткрывателей
        discoverers = Discoverers.objects.filter(status='active')

        # Фильтрация по имени, если оно передано в запросе
        name = request.query_params.get('name')
        if name:
            discoverers = discoverers.filter(name__icontains=name)

        # Сериализация данных
        serializer = DiscoverersSerializer(discoverers, many=True)

        # Получение черновика для текущего пользователя
        draft_discovery = Discovery.objects.filter(creator=request.user, status='draft').first()
        draft_id = draft_discovery.id if draft_discovery else None
        draft_count = draft_discovery.discoverydiscoverers_set.count() if draft_discovery else 0

        # Ответ с данными
        return Response({
            'discoverers': serializer.data,
            'draft_id': draft_id,
            'draft_count': draft_count
        })
    

    # Добавляет нового первооткрывателя
    @swagger_auto_schema(
        operation_summary="Создать первооткрывателя",
        request_body=DiscoverersSerializer,
        responses={201: DiscoverersSerializer, 400: "Ошибка валидации"},
    )
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

    @swagger_auto_schema(
        operation_summary="Получить первооткрывателя",
        responses={200: DiscoverersSerializer, 404: "Не найден"},
    )

    # Возвращает информацию о конкретном первооткрывателе
    def get(self, request, pk, format=None):
        try:
            discoverer = Discoverers.objects.get(pk=pk, status = 'active')
        except Discoverers.DoesNotExist:
            return Response({"Данного первооткрывателя не сущесвует"})
        serializer = self.serializer_class(discoverer)
        return Response(serializer.data)
       

    @swagger_auto_schema(
        operation_summary="Обновить данные первооткрывателя",
        request_body=DiscoverersSerializer,
        responses={200: DiscoverersSerializer, 400: "Ошибка валидации", 404: "Не найден"},
    )

    # Обновляет информацию о первооткрывателе (только активные записи)
    def put(self, request, pk, format=None):
        discoverer = get_object_or_404(self.model_class, pk=pk)
        serializer = self.serializer_class(discoverer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="Удалить первооткрывателя",
        responses={204: "Удалено", 404: "Не найден"},
    )

    # Удаляет первооткрывателя (мягкое удаление, ставит статус 'deleted')
    def delete(self, request, pk, format=None):
        discoverer = get_object_or_404(self.model_class, pk=pk)
        discoverer.status = 'deleted'
        discoverer.save()
        if discoverer.image_url:
            parsed_url = urlparse(discoverer.image_url)
            object_name = parsed_url.path.lstrip('/')
            delete_image(object_name)
       
        
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

    @swagger_auto_schema(
        operation_summary="Получить список открытий",
        responses={200: DiscoverySerializer(many=True)},
        manual_parameters=[
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Фильтрация по статусу открытия",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'start_date',
                openapi.IN_QUERY,
                description="Фильтрация по начальной дате",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False
            ),
            openapi.Parameter(
                'end_date',
                openapi.IN_QUERY,
                description="Фильтрация по конечной дате",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
                required=False
            ),
        ]
    )

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

    @swagger_auto_schema(
        operation_summary="Создать открытие",
        responses={201: DiscoverySerializer, 400: "Ошибка валидации"},
    )   

    # Возвращает информацию о заявке
    def get(self, request, pk, format=None):
        discovery = get_object_or_404(self.model_class, pk=pk)
        serializer = self.serializer_class(discovery)
        return Response(serializer.data)
    

    @swagger_auto_schema(
        operation_description="Update a specific disability request (only 'draft' status can be updated).",
        request_body=DiscoverySerializer,
        responses={
            200: openapi.Response(description="Disability request successfully updated"),
            400: openapi.Response(description="Invalid data provided"),
            404: openapi.Response(description="Disability not found or not in 'draft' status"),
        }
    )
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
    

    @swagger_auto_schema(
        operation_description="Soft delete a specific disability request (marks it as 'deleted').",
        responses={
            200: openapi.Response(description="Disability request successfully deleted"),
            400: openapi.Response(description="Invalid data provided"),
            404: openapi.Response(description="Disability not found"),
        }
    )
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

    @swagger_auto_schema(
        operation_description="Submit a disability request, updating its status to 'formed' and setting the data_compilation date.",
        request_body=DiscoverySerializer,
        responses={
            200: openapi.Response(description="Disability request successfully submitted", schema=DiscoverySerializer),
            400: openapi.Response(description="Bad request, missing required fields (phone or address)"),
            404: openapi.Response(description="Disability request not found or incorrect status"),
        }
    )

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
    @swagger_auto_schema(
        operation_description="Complete or reject a disability request. Based on the action parameter, update the status to 'completed' or 'rejected'.",
        manual_parameters=[
            openapi.Parameter('action', openapi.IN_QUERY, description="Action to perform, either 'completed' or 'rejected'.", type=openapi.TYPE_STRING, enum=['completed', 'rejected']),
        ],
        request_body=DiscoverySerializer,
        responses={
            200: openapi.Response(description="Disability request successfully updated", schema=DiscoverySerializer),
            400: openapi.Response(description="Invalid data or action parameter"),
            403: openapi.Response(description="Forbidden, user is not staff"),
            404: openapi.Response(description="Disability request not found or incorrect status"),
        }
    )


    @method_permission_classes([IsManager])
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
    @swagger_auto_schema(
        operation_description="Update patronage image (logo) for a specific patronage",
        manual_parameters=[
            openapi.Parameter('id', openapi.IN_PATH, description="ID of the patronage", type=openapi.TYPE_INTEGER),
        ],
        request_body=DiscoverersSerializer,
        responses={
            200: openapi.Response(description="Patronage image successfully updated", schema=DiscoverersSerializer),
            400: openapi.Response(description="Invalid data provided"),
            403: openapi.Response(description="Forbidden, user is not staff"),
        }
    )

    @method_permission_classes(IsAdmin)
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
    


class UserUpdate(UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self):
        return self.request.user


