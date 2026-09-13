from django.urls import path
from . import views
urlpatterns = [path("changes", views.changes), path("changes/<uuid:change_id>/approve", views.approve),
               path("changes/<uuid:change_id>/execute", views.execute)]
