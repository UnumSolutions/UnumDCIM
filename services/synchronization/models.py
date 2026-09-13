import uuid
from django.db import models


class Conflict(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    entity = models.CharField(max_length=100)
    field = models.CharField(max_length=100)
    owner = models.CharField(max_length=100)
    baseline = models.JSONField(null=True)
    candidates = models.JSONField()
    state = models.CharField(max_length=40, default="conflict")
    resolution = models.JSONField(null=True)
    revision = models.PositiveIntegerField(default=1)
    observed_at = models.DateTimeField(auto_now_add=True)


class Connection(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    label = models.CharField(max_length=100)
    state = models.CharField(max_length=40, default="unconfigured")
    capabilities = models.JSONField(default=dict)
    last_success = models.DateTimeField(null=True)
