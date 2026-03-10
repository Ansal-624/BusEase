from django.urls import path
from . import views
from . import views as main_views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    # ...other routes...

#     path('notifications/fetch/', main_views.fetch_notifications, name='fetch_notifications'),
#     path('notifications/mark-read/<int:notif_id>/', main_views.mark_notification_read, name='mark_notification_read'),
#     path('conversations/<int:conv_id>/send/', main_views.send_message, name='send_message'),
#     path('conversations/create/', main_views.create_conversation, name='create_conversation'),
# path('notifications/', views.inbox, name='main_inbox'),
#     path('notifications/<int:pk>/', views.notification_detail, name='main_notification_detail'),
#     path('notifications/fetch/', views.notifications_fetch, name='main_notifications_fetch'),
#     path('notifications/<int:pk>/mark-read/', views.mark_read, name='main_mark_read'),

#     path('compose/', views.admin_compose, name='main_admin_compose'),           # admin only
#     path('reply/<int:pk>/', views.owner_reply, name='main_owner_reply'),      # owner replies to admin msg
#     path('complaint/', views.file_complaint, name='main_file_complaint'),     # traveller complaint
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("reset-password/", views.reset_password, name="reset_password"),
]
