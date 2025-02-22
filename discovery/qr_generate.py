import segno
import base64
from io import BytesIO

def generate_discovery_qr(discovery):
    """Генерирует QR-код с информацией о заявке Discovery"""
    discoverers = discovery.discoverers.all()  # Получаем всех первооткрывателей

    # Формируем информацию для QR-кода
    info = (
        f"Заявка №{discovery.id}\n"
        f"Статус: {discovery.status}\n"
        f"Регион: {discovery.region}\n"
        f"Создатель: {discovery.creator.username}\n"
        f"Дата создания: {discovery.created_at.strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        "Первооткрыватели:\n"
    )

    for discoverer in discoverers:
        info += f"  - {discoverer.name}\n"

    # Генерация QR-кода
    qr = segno.make(info)
    buffer = BytesIO()
    qr.save(buffer, kind="png")
    buffer.seek(0)

    # Конвертация изображения в base64
    qr_image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

    return qr_image_base64
