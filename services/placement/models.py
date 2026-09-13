from django.db import models


class Room(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    site_name = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, default="", choices=[
        ("AMER", "AMER"), ("EMEA", "EMEA"), ("APAC", "APAC")])
    country = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    room_type = models.CharField(max_length=20, default="room", choices=[
        ("room", "Room"), ("data_hall", "Data hall"), ("mdf", "MDF"), ("idf", "IDF")])


class Rack(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    label = models.CharField(max_length=100)
    x = models.FloatField()
    y = models.FloatField()
    height_u = models.PositiveIntegerField(default=42)
    budget_watts = models.PositiveIntegerField(default=8000)


class Placement(models.Model):
    asset_id = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    rack = models.ForeignKey(Rack, on_delete=models.PROTECT)
    u = models.PositiveIntegerField()
    height_u = models.PositiveIntegerField()
    face = models.CharField(max_length=10, default="front")
    owner = models.CharField(max_length=100, default="unum")
    revision = models.PositiveIntegerField(default=1)


class Authority(models.Model):
    site = models.CharField(max_length=100, primary_key=True)
    tenant = models.CharField(max_length=100)
    epoch = models.PositiveIntegerField(default=1)
    local = models.BooleanField(default=True)
    connected = models.BooleanField(default=True)


class Reservation(models.Model):
    request_id = models.UUIDField(primary_key=True)
    tenant = models.CharField(max_length=100)
    asset_id = models.CharField(max_length=100)
    rack = models.ForeignKey(Rack, on_delete=models.PROTECT)
    u = models.PositiveIntegerField()
    height_u = models.PositiveIntegerField()
    face = models.CharField(max_length=10)
    expected_revision = models.PositiveIntegerField()
    authority_epoch = models.PositiveIntegerField()
    state = models.CharField(max_length=40, default="held")
    expires_at = models.DateTimeField()
    committed_revision = models.PositiveIntegerField(null=True)
