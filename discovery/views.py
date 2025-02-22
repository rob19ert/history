from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from minio import Minio, S3Error
from django.conf import settings
from .models import Discoverers, Discovery, DiscoveryDiscoverers
from .serializers import DiscoverersSerializer, DiscoverySerializer, DiscoveryDiscoverersSerializer, RegisterSerializer, UserUpdateSerializer, UserSerializer,AddDiscovererToDraftSerializer
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
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import permission_classes
from rest_framework import viewsets
from rest_framework import status, permissions
from rest_framework.decorators import authentication_classes
from .minio import add_pic, delete_image, process_file_upload
from drf_yasg import openapi
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
import redis
import uuid
from .qr_generate import generate_discovery_qr


session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

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

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        random_key = str(uuid.uuid4())
        session_storage.set(random_key, username)
        request.session['random_key'] = random_key

        return Response({'status': 'ok', 'id': user.id, 'username': user.username, 'is_superuser': user.is_superuser, 'is_staff': user.is_staff})
    else:
        return Response({'status': 'error', 'error': 'login failed'}, status=400)
    
@api_view(['POST'])
def logout_view(request):
    logout(request._request)
    return Response({'status': 'Success'})


class DiscovererList(APIView):
    
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
        discoverer_name = request.query_params.get('discovererName')
        if discoverer_name:
            discoverers = discoverers.filter(name__icontains=discoverer_name)

        # Сериализация данных
        serializer = DiscoverersSerializer(discoverers, many=True)

        draft_id = None
        draft_count = 0

        # Получение черновика для текущего пользователя
        if request.user.is_authenticated:
            draft_discovery = Discovery.objects.filter(creator=request.user, status='draft').first()
            if draft_discovery:
                draft_id = draft_discovery.id 
                draft_count = draft_discovery.discoverydiscoverers_set.count()

        
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
    @method_permission_classes([IsAdmin])
    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#Подробная информация о первооткрывателях
class DiscoverersDetail(APIView):
    
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

    @method_permission_classes([IsAdmin])
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
    @method_permission_classes([IsAdmin])
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
    
class AddDiscovererToDraft(APIView):  # Добавление исследователя в черновик
    model_class = DiscoveryDiscoverers  # Указываем модель, с которой работаем
    serializer_class = AddDiscovererToDraftSerializer  # Указываем сериализатор
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Добавление исследователя в черновик",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'explorer_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID исследователя"),
            },
            required=['explorer_id']
        ),
        responses={
            201: "Успешно добавлено",
            400: "Некорректные данные",
            404: "Исследователь не найден",
        }
    )
    def post(self, request, format=None):
        # Получаем исследователя или создаём черновик
        try:
            discovery = Discovery.objects.get(creator=request.user, status='draft')
        except Discovery.DoesNotExist:
            discovery = Discovery.objects.create(
                creator=request.user,
                status='draft',
                region=None,
                completed_at=None,
                formed_at=None,
                moderator=None,
            )

        # Добавляем ID черновика в данные для сериализатора
        request.data["discovery_id"] = discovery.id

        # Используем сериализатор для валидации данных
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Исследователь успешно добавлен",
                "discovery_id": discovery.id
            }, status=status.HTTP_201_CREATED)

        # Возвращаем ошибки валидации
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DiscoveryList(APIView):
    permission_classes = [IsAuthenticated]
    model_class = Discovery
    serializer_class = DiscoverySerializer

    @swagger_auto_schema(
        operation_summary="Получить список открытий",
        manual_parameters=[
            openapi.Parameter(
                'status', openapi.IN_QUERY,
                description="Фильтрация по статусу открытия",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'start_date', openapi.IN_QUERY,
                description="Фильтрация по начальной дате",
                type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE
            ),
            openapi.Parameter(
                'end_date', openapi.IN_QUERY,
                description="Фильтрация по конечной дате",
                type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE
            ),
        ],
        responses={
            200: openapi.Response(
                description="Список открытий",
                schema=DiscoverySerializer(many=True)
            ),
            400: openapi.Response(description="Некорректные параметры фильтрации")
        }
    )
    def get(self, request, format=None):
        status_filter = request.query_params.get('status', None)
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)

        # Исключаем черновики и удаленные записи
        if request.user.is_staff:
            discoveries = self.model_class.objects.exclude(status__in=['draft', 'deleted']).all()
        else:
            discoveries = self.model_class.objects.exclude(status__in=['draft', 'deleted']).filter(creator=request.user).all()

        # Применение фильтров
        if status_filter:
            discoveries = discoveries.filter(status=status_filter)
        
        if start_date and end_date:
            try:
                start_date = parse_date(start_date)
                end_date = parse_date(end_date)
                discoveries = discoveries.filter(submit_sate__range=[start_date, end_date])
            except (ValueError, TypeError):
                return Response({"error": "Некорректный формат дат"}, status=status.HTTP_400_BAD_REQUEST)

        # Сериализация и возврат данных
        serializer = self.serializer_class(discoveries, many=True)
        resp = serializer.data
        return Response(resp)



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
        discovery.status = "formed"
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


    @method_permission_classes([IsAdmin])
    def put(self, request, pk):
        try:
            discovery = Discovery.objects.get(pk=pk, status='formed')
        except Discovery.DoesNotExist:
            return Response({"error": "Заявка не найдена или не находится в статусе ожидания модерации"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff:
            return Response({"error": "Доступ запрещен, вы не являетесь модератором"}, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        if action not in ['completed', 'rejected']:
            return Response({"error": "Неверное действие. Ожидается 'completed' или 'rejected'"}, status=status.HTTP_400_BAD_REQUEST)

        discovery.moderator = request.user
        discovery.completed_at = timezone.now()
        if action == 'completed':
            discovery.status = 'completed'
        elif action == 'rejected':
            discovery.status = 'rejected'
        discovery.save()
        serializer = DiscoverySerializer(discovery)

        discovery.qr = generate_discovery_qr(discovery)
        discovery.save()

        return Response({
            "message": f"Заявка успешно {('завершена' if action == 'completed' else 'отклонена')}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

class UploadImageForDiscover(APIView):
    model_class = Discoverers
    serializer_class = DiscoverersSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Upload or update an image for a discoverer",
        manual_parameters=[
            openapi.Parameter("pk", openapi.IN_PATH, description="ID of the discoverer", type=openapi.TYPE_INTEGER),
        ],
        request_body=DiscoverersSerializer,
        responses={
            200: openapi.Response(description="Image successfully updated", schema=DiscoverersSerializer),
            400: openapi.Response(description="Invalid data provided"),
            403: openapi.Response(description="Forbidden, user is not authorized"),
        },
    )
    @method_permission_classes([IsManager])
    def post(self, request, pk, format=None):
        discoverer = get_object_or_404(self.model_class, pk=pk)
        serializer = self.serializer_class(discoverer, data=request.data, partial=True)

        if "image" in request.FILES:
            image_file = request.FILES["image"]

            # Загружаем новое изображение
            upload_result = add_pic(discoverer, image_file)
            if "error" in upload_result.data:
                return upload_result

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
        return self.request.user  # Только текущий пользователь

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


