from django.db import models


class Asset(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    name = models.CharField(max_length=160)
    manufacturer = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    serial = models.CharField(max_length=100)
    asset_tag = models.CharField(max_length=100)
    height_u = models.PositiveIntegerField(default=2)
    watts = models.PositiveIntegerField(default=400)
    lifecycle = models.CharField(max_length=40, default="in_service")
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
