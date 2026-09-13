import uuid
from django.db import models


class Change(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    proposer = models.CharField(max_length=100)
    approver = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    payload = models.JSONField()
    state = models.CharField(max_length=40, default="awaiting_approval")
    error = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "proposer", "idempotency_key"], name="change_idempotency")]
