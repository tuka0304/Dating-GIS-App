from django.contrib import admin
from django.urls import path
from dating_app import views 
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- TRANG CHỦ ---
    path('', views.map_search_view, name='home'),
    
    # --- AUTH & CÀI ĐẶT ---
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings_view, name='settings'), 
    
    # --- API CHAT ---
    path('api/chat/history/<int:user_id>/', views.get_messages, name='chat_history'),
    path('api/chat/send/', views.send_message, name='chat_send'),
    path('api/chat/list/', views.get_conversations, name='chat_list'),

    # --- API KẾT BẠN ---
    path('api/friend/send/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('api/friend/accept/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('api/friend/reject/<int:request_id>/', views.reject_friend_request, name='reject_friend_request'),
    path('api/friend/cancel/<int:user_id>/', views.cancel_friend_request, name='cancel_friend_request'),
    path('api/friend/list_requests/', views.get_friend_requests, name='get_friend_requests'),
    
    # --- API HẸN HÒ MỚI ---
    path('api/dating/send/<int:user_id>/', views.send_dating_request, name='send_dating_request'),
    path('api/dating/cancel/<int:user_id>/', views.cancel_dating_request, name='cancel_dating_request'),
    path('api/dating/accept/<int:user_id>/', views.accept_dating_request, name='accept_dating_request'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)