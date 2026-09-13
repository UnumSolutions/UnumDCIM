import uuid
from django.db import models


class Outbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True)


class Inbox(models.Model):
    event_id = models.UUIDField(primary_key=True)
    tenant = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)


class AuditHead(models.Model):
    chain = models.CharField(max_length=300, primary_key=True)
    tenant = models.CharField(max_length=100)
    sequence = models.PositiveBigIntegerField(default=0)
    digest = models.CharField(max_length=64, default="0" * 64)


class AuditEntry(models.Model):
    chain = models.CharField(max_length=300)
    tenant = models.CharField(max_length=100)
    sequence = models.PositiveBigIntegerField()
    payload = models.JSONField()
    previous = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["chain", "sequence"], name="audit_chain_sequence")]
