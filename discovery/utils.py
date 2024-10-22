from minio import Minio, S3Error
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status


def add_image(discoverer, image):
    try:
        minio_client = Minio(
            settings.MINIO_STORAGE_ENDPOINT,
            access_key=settings.MINIO_STORAGE_ACCESS_KEY,
            secret_key=settings.MINIO_STORAGE_SECRET_KEY,
            secure=False
        )
        bucket_name = settings.MINIO_STORAGE_BUCKET_NAME
        file_name = f"{discoverer.id}/{image.name}"

        minio_client.put_object(bucket_name, file_name, image, len(image))
        discoverer.image_url = f"{settings.MINIO_STORAGE_ENDPOINT}/{bucket_name}/{file_name}"
        discoverer.save()

        return Response({'message': 'Image uploaded successfully'}, status=status.HTTP_200_OK)
    except S3Error as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)