from django.urls import path
from . import views
urlpatterns = [path("scene", views.scene), path("preview", views.preview),
               path("reservations", views.reserve), path("reservations/<uuid:request_id>/commit", views.commit)]
