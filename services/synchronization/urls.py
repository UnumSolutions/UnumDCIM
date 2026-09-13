from django.urls import path
from . import views
urlpatterns = [path("status", views.status), path("rehearsal", views.rehearsal),
               path("conflicts/<uuid:conflict_id>/resolve", views.resolve)]
