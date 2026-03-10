from django.urls import path
from . import views


urlpatterns = [
   
    path("add/", views.add_complaint, name="add_complaint"),
    path("my/", views.my_complaints, name="my_complaints"),
     path('admin/complaints/', views.admin_complaints, name='admin_complaints'),
    path('admin/complaint/<int:pk>/update/', views.update_complaint_status, name='update_complaint_status'),
    
]
