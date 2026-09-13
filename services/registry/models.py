from django.db import models


class PluginGrant(models.Model):
    plugin = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    approved_by = models.CharField(max_length=100)
    enabled = models.BooleanField(default=False)
