from django.db import models

class Service(models.Model):  
    name = models.CharField(max_length=200)
    description = models.TextField()
    image = models.URLField()  # Ссылка на изображение
    discoveries = models.TextField()

    def __str__(self):
        return self.name

class Cart(models.Model):
    user = models.CharField(max_length=100)
    services = models.ManyToManyField(Service, related_name='carts')  # связь многие ко многим (услуга - заявка)

    def __str__(self):
        return f"Корзина {self.user}"

    def service_count(self):
        return self.services.count()  # Подсчет количества услуг в корзине
