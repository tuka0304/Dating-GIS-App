from django.contrib import admin
from django.urls import path
from dating_app import views 
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve
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
    path('api/messages/unread/', views.check_unread_messages, name='check_unread_messages'),

   # --- API KẾT BẠN & THÔNG BÁO ---
    path('api/friend/send/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('api/friend/accept/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('api/friend/reject/<int:request_id>/', views.reject_friend_request, name='reject_friend_request'),
    path('api/friend/cancel/<int:user_id>/', views.cancel_friend_request, name='cancel_friend_request'),
    path('api/requests/list/', views.get_all_requests, name='get_all_requests'),
    path('friends-map/', views.friends_map_view, name='friends_map'),
    path('friends-list/', views.friends_list_view, name='friends_list'),
    
    # --- API HẸN HÒ ---
    path('api/dating/send/<int:user_id>/', views.send_dating_request, name='send_dating_request'),
    path('api/dating/cancel/<int:user_id>/', views.cancel_dating_request, name='cancel_dating_request'),
    path('api/dating/accept/<int:user_id>/', views.accept_dating_request, name='accept_dating_request'),
    path('api/dating/reject/<int:user_id>/', views.reject_dating_request, name='reject_dating_request'),
    
    # --- LINK TRANG CUSTOM ADMIN ---
    path('quan-ly/', views.custom_admin_view, name='custom_admin'),
    path('quan-ly/xoa/<int:user_id>/', views.delete_user_action, name='admin_delete_user'),
    path('quan-ly/trang-thai/<int:user_id>/', views.toggle_user_status, name='admin_toggle_status'),
    path('quan-ly/xoa-anh/<int:user_id>/', views.remove_user_avatar, name='admin_remove_avatar'),

    # --- API KHÁNG CÁO ---
    path('khang-cao/', views.submit_appeal, name='submit_appeal'),
    path('quan-ly/khang-cao/xong/<int:appeal_id>/', views.resolve_appeal, name='admin_resolve_appeal'),
    path('appeal/', views.submit_appeal, name='appeal'),

    # --- API TÌM KIẾM NHẠC ---
    path('api/music/search/', views.search_music_api, name='search_music_api'),

    # --- API GHI NHẬN THỜI GIAN XEM HỒ SƠ ---
    path('api/ai/record-dwell/', views.record_dwell_time, name='record_dwell_time'),

    # --- API QUÊN MẬT KHẨU ---
    path('quen-mat-khau/', views.forgot_password_view, name='forgot_password'),
    path('xac-nhan-otp/', views.verify_otp_view, name='verify_otp'),
    path('dat-lai-mat-khau/', views.reset_password_view, name='reset_password'),

    # --- API BẢNG TIN ---
    path('bang-tin/', views.feed_view, name='feed'),
    path('bang-tin/like/<int:post_id>/', views.toggle_like_post, name='toggle_like_post'),
    path('api/post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('api/post/<int:post_id>/report/', views.report_post, name='report_post'),
    path('api/post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('quan-ly/resolve-report/<int:report_id>/', views.resolve_report, name='admin_resolve_report'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# Khai báo hàm xử lý lỗi 404 tùy chỉnh
handler404 = 'dating_app.views.custom_404_view'
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        re_path(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]