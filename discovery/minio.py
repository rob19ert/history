from django.conf import settings
from geohistory import settings
from minio import Minio
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework.response import *

def process_file_upload(file_object: InMemoryUploadedFile, client, image_name):
    try:
        client.put_object('geogistory', image_name, file_object, file_object.size)
        return f"http://localhost:9000/geogistory/{image_name}"
    except Exception as e:
        return {"error": str(e)}


def delete_image(image_name):
    client = Minio(           
        endpoint=settings.AWS_S3_ENDPOINT_URL,
        access_key=settings.AWS_ACCESS_KEY_ID,
        secret_key=settings.AWS_SECRET_ACCESS_KEY,
        secure=settings.AWS_S3_USE_SSL
    )
    try:
        client.remove_object('geogistory', image_name)
        return {"message": "Image deleted successfully"}
    except Exception as e:
        return {"error": str(e)}
    
    
def add_pic(new_stock, pic):
    client = Minio(           
           endpoint=settings.AWS_S3_ENDPOINT_URL,
           access_key=settings.AWS_ACCESS_KEY_ID,
           secret_key=settings.AWS_SECRET_ACCESS_KEY,
           secure=settings.AWS_S3_USE_SSL
    )
    i = new_stock.id
    img_obj_name = f"{i}.jpg"

    if not pic:
        return Response({"error": "Нет файла для изображения логотипа."})
    result = process_file_upload(pic, client, img_obj_name)


    if isinstance(result, dict) and "error" in result:
        return Response(result, status=400)
    new_stock.image_url = result  # поле называется image_url
    new_stock.save()

    return Response({"message": "success"})