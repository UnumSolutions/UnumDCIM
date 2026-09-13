from django.urls import path
from . import views
urlpatterns = [path("assets", views.assets), path("assets/<str:asset_id>", views.asset)]
