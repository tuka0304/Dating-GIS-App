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
    path('settings/', views.settings_view, name='settings'), # <--- Trang cài đặt
    
    # --- API CHAT ---
    path('api/chat/history/<int:user_id>/', views.get_messages, name='chat_history'),
    path('api/chat/send/', views.send_message, name='chat_send'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)