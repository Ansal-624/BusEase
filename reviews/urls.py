from django.urls import path
from . import views
from .views import add_app_review

urlpatterns = [
    path('add/', add_app_review, name='add_app_review'),
    path("bus/<int:bus_id>/review/", views.add_bus_review, name="add_bus_review"),

]
