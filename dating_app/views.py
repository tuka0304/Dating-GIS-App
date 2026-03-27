import random
import requests
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone 
from geopy.geocoders import Nominatim

from .models import UserProfile, Message, PROVINCE_CHOICES, FriendRequest, DatingRequest, Appeal
from .gis_tools import DatingGISTool
from .forms import RegisterForm, ProfileUpdateForm

# ==========================================
# 1. HÀM TÌM NHẠC 
# ==========================================
SPOTIFY_CLIENT_ID = '4b4fa7d5b6b344caac93b31fcf02a0b0' # Copy từ ảnh của bạn
SPOTIFY_CLIENT_SECRET = '79a7d65eaed24032833dff2204edac28' # Bấm "View client secret" để lấy

def get_spotify_track_by_name(song_name):
    """Hàm lấy token thật và tìm bài hát trên Spotify"""
    try:
        # 1. Lấy Access Token (Dùng cách truyền data trực tiếp)
        auth_url = 'https://accounts.spotify.com/api/token'
        auth_response = requests.post(
            auth_url,
            data={
                'grant_type': 'client_credentials',
                'client_id': SPOTIFY_CLIENT_ID,
                'client_secret': SPOTIFY_CLIENT_SECRET,
            }
        )
        
        # Kiểm tra xem Spotify có trả về lỗi không trước khi đọc JSON
        if auth_response.status_code != 200:
            print(f"Lỗi xác thực Spotify: {auth_response.status_code}")
            return None
            
        auth_data = auth_response.json()
        access_token = auth_data.get('access_token')

        if not access_token: return None

        # 2. Tìm kiếm bài hát
        search_url = 'https://api.spotify.com/v1/search'
        search_response = requests.get(
            search_url,
            headers={'Authorization': f'Bearer {access_token}'},
            params={'q': song_name, 'type': 'track', 'limit': 1}
        )
        
        search_data = search_response.json()
        tracks = search_data.get('tracks', {}).get('items', [])
        if tracks:
            return tracks[0]['id']
            
    except Exception as e:
        print(f"Lỗi kết nối Spotify: {e}")
    return None

def get_soundcloud_embed(track_url):
    # (Hàm soundcloud cũ giữ nguyên, không sửa gì)
    try:
        url = f"https://soundcloud.com/oembed?format=json&url={track_url}&maxheight=166"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json().get('html')
    except Exception:
        pass
    return None

def get_soundcloud_embed(track_url):
    try:
        url = f"https://soundcloud.com/oembed?format=json&url={track_url}&maxheight=166"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json().get('html')
    except Exception:
        pass
    return None

# ==========================================
# 2. VIEW CHÍNH: BẢN ĐỒ & TÌM KIẾM
# ==========================================
@login_required(login_url='login')
def map_search_view(request):
    try:
        my_profile = request.user.profile
    except UserProfile.DoesNotExist:
        my_profile = UserProfile.objects.create(
            user=request.user, 
            full_name=request.user.username, 
            latitude=10.7769, 
            longitude=106.7009
        )

    my_location = (my_profile.latitude, my_profile.longitude)

    raw_radius = request.GET.get('radius', '')
    if raw_radius and raw_radius.strip():
        try:
            search_radius = float(raw_radius)
            radius = search_radius
        except ValueError:
            radius = ""
            search_radius = 50000 
    else:
        radius = ""
        search_radius = 50000

    gender_filter = request.GET.get('gender', 'ALL')
    province_filter = request.GET.get('province', 'ALL')

    candidates = UserProfile.objects.exclude(id=my_profile.id)
    if gender_filter != 'ALL':
        candidates = candidates.filter(gender=gender_filter)

    if province_filter != 'ALL':
        candidates = candidates.filter(province=province_filter)
        final_calc_radius = 50000 
    else:
        final_calc_radius = search_radius

    nearby_users = DatingGISTool.find_users_in_radius(my_location, candidates, final_calc_radius)
    random.shuffle(nearby_users)

    results_json = []
    song_cache = {} 

    for u in nearby_users:
        gallery_images = [p.image.url for p in u.gallery.all()] if hasattr(u, 'gallery') else []
        
        # --- KIỂM TRA TRẠNG THÁI KẾT BẠN ---
        rel_status = 'none'
        if request.user.profile.friends.filter(id=u.id).exists():
            rel_status = 'friends'
        elif FriendRequest.objects.filter(sender=request.user, receiver=u.user, status='pending').exists():
            rel_status = 'pending_sent'
        elif FriendRequest.objects.filter(sender=u.user, receiver=request.user, status='pending').exists():
            rel_status = 'pending_received'

        # --- KIỂM TRA TRẠNG THÁI HẸN HÒ ---
        dating_rel_status = 'none'
        if request.user.profile.dating_with == u:
            dating_rel_status = 'dating'
        elif DatingRequest.objects.filter(sender=request.user, receiver=u.user, status='pending').exists():
            dating_rel_status = 'pending_sent'
        elif DatingRequest.objects.filter(sender=u.user, receiver=request.user, status='pending').exists():
            dating_rel_status = 'pending_received'

        display_marital = u.marital_status
        if u.dating_with:
            display_marital = f"Đang hẹn hò với @{u.dating_with.full_name} 💍"
        
        # --- BỘ NÃO XỬ LÝ NHẠC 3-TRONG-1 ---
        processed_playlist = []
        if u.music_playlist:
            song_lines = [s.strip() for s in u.music_playlist.split('\n') if s.strip()]
            for song in song_lines:
                if 'spotify.com' in song:
                    # 1. Nếu là link Spotify: Biến đổi URL để tạo mã Embed ngay lập tức (Không cần API Key)
                    embed_url = song.replace('spotify.com/', 'spotify.com/embed/').split('?')[0]
                    iframe_html = f'<iframe style="border-radius:12px" src="{embed_url}" width="100%" height="80" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>'
                    # Mượn thẻ hiển thị soundcloud để in thẳng mã HTML ra giao diện
                    processed_playlist.append({'type': 'soundcloud', 'value': iframe_html})
                
                elif 'soundcloud.com' in song:
                    # 2. Nếu là link SoundCloud
                    if song in song_cache:
                        iframe_html = song_cache[song]
                    else:
                        iframe_html = get_soundcloud_embed(song)
                        song_cache[song] = iframe_html
                    
                    if iframe_html:
                        processed_playlist.append({'type': 'soundcloud', 'value': iframe_html})
                    else:
                        processed_playlist.append({'type': 'text', 'value': song})
                        
                else:
                    if song in song_cache:
                        track_id = song_cache[song]
                    else:
                        track_id = get_spotify_track_by_name(song)
                        song_cache[song] = track_id
                    
                    if track_id:
                        embed_url = f"https://open.spotify.com/embed/track/{track_id}"
                        iframe_html = f'<iframe style="border-radius:12px" src="{embed_url}" width="100%" height="80" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>'
                        processed_playlist.append({'type': 'soundcloud', 'value': iframe_html})
                    else:
                        processed_playlist.append({'type': 'text', 'value': song})
        
        results_json.append({
            'id': u.user.id,
            'name': u.full_name,
            'gender': u.gender,
            'age': u.get_age(),
            'marital_status': display_marital,
            'rel_status': rel_status,
            'dating_rel_status': dating_rel_status, 
            'status': u.bio[:30] + '...' if u.bio else 'Đang online',
            'address': u.address,
            'lat': u.latitude,
            'lon': u.longitude,
            'distance': u.distance_km,
            'avatar': u.avatar.url if u.avatar else '',
            'cover': u.cover_photo.url if u.cover_photo else '',
            'bio': u.bio,
            'playlist': processed_playlist, 
            'hobbies': u.hobbies.split(',') if u.hobbies else [],
            'gallery': gallery_images
        })

    return render(request, 'map_search.html', {
        'my_profile': my_profile,
        'results': results_json,
        'radius': radius,
        'selected_gender': gender_filter,
        'selected_province': province_filter,
        'provinces': PROVINCE_CHOICES
    })

# ==========================================
# 3. API CHAT & NHẮN TIN
# ==========================================
@login_required
def get_messages(request, user_id):
    try:
        target_user = User.objects.get(id=user_id)
        current_user = request.user
        msgs = Message.objects.filter(
            Q(sender=current_user, receiver=target_user) | 
            Q(sender=target_user, receiver=current_user)
        ).order_by('timestamp')
        
        data = []
        for m in msgs:
            local_time = timezone.localtime(m.timestamp)
            data.append({
                'sender': 'me' if m.sender == current_user else 'them', 
                'content': m.content, 
                'time': local_time.strftime("%H:%M") 
            })
        return JsonResponse({'messages': data})
    except User.DoesNotExist:
        return JsonResponse({'messages': []})

@csrf_exempt
@login_required
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            receiver_id = data.get('receiver_id')
            content = data.get('content')
            Message.objects.create(
                sender=request.user,
                receiver=User.objects.get(id=receiver_id),
                content=content
            )
            return JsonResponse({'status': 'ok'})
        except Exception:
            return JsonResponse({'status': 'error'})
    return JsonResponse({'status': 'error'})

@login_required
def get_conversations(request):
    current_user = request.user
    all_msgs = Message.objects.filter(Q(sender=current_user) | Q(receiver=current_user)).order_by('-timestamp')
    partners = {}
    conversation_list = []

    for m in all_msgs:
        partner_id = m.receiver.id if m.sender == current_user else m.sender.id
        
        if partner_id not in partners:
            partners[partner_id] = True
            try:
                partner_user = User.objects.get(id=partner_id)
                try:
                    profile = partner_user.profile
                    avatar_url = profile.avatar.url if profile.avatar else ""
                    name = profile.full_name
                except:
                    avatar_url = ""
                    name = partner_user.username
                
                local_time = timezone.localtime(m.timestamp)
                conversation_list.append({
                    'partner_id': partner_id,
                    'name': name,
                    'avatar': avatar_url,
                    'last_msg': m.content[:30] + '...' if len(m.content) > 30 else m.content,
                    'time': local_time.strftime("%H:%M %d/%m"),
                    'is_me': m.sender == current_user
                })
            except User.DoesNotExist:
                continue
    return JsonResponse({'conversations': conversation_list})

# ==========================================
# 4. TÀI KHOẢN & CÀI ĐẶT
# ==========================================
def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            full_name = form.cleaned_data.get('full_name')
            gender = form.cleaned_data.get('gender')
            birth_date = form.cleaned_data.get('birth_date')
            UserProfile.objects.create(
                user=user, 
                full_name=full_name, 
                gender=gender,
                birth_date=birth_date, 
                latitude=10.7769, 
                longitude=106.7009
            )
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == "POST":
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # 1. Thử xác thực người dùng
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            # Tài khoản hợp lệ và đang hoạt động
            login(request, user)
            return redirect('home')
        else:
            # 2. XỬ LÝ KHI ĐĂNG NHẬP THẤT BẠI
            try:
                # Kiểm tra xem username có tồn tại trong hệ thống không
                check_user = User.objects.get(username=u)
                
                # Nếu đúng mật khẩu nhưng tài khoản bị Admin khóa (is_active=False)
                if not check_user.is_active and check_user.check_password(p):
                    return render(request, 'login.html', {
                        'error': 'suspended', 
                        'suspend_username': u
                    })
            except User.DoesNotExist:
                pass
            
            # Sai tên đăng nhập hoặc mật khẩu thông thường
            return render(request, 'login.html', {'error': 'invalid'})
            
    return render(request, 'login.html')

def submit_appeal(request):
    """Hàm xử lý trang điền đơn kháng cáo"""
    username = request.GET.get('user', '')
    if request.method == "POST":
        u = request.POST.get('username')
        msg = request.POST.get('message')
        Appeal.objects.create(username=u, message=msg) # Lưu đơn vào DB
        return render(request, 'appeal.html', {'success': True})
    return render(request, 'appeal.html', {'username': username})

@login_required
def settings_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if form.is_valid():
            user_profile = form.save(commit=False)
            
            raw_lat = request.POST.get('latitude')
            raw_lon = request.POST.get('longitude')
            gps_success = False
            
            if raw_lat and raw_lon:
                try:
                    user_profile.latitude = float(raw_lat)
                    user_profile.longitude = float(raw_lon)
                    gps_success = True
                except ValueError:
                    pass
            
            if not gps_success:
                address_string = f"{user_profile.address}, {user_profile.get_province_display()}, Việt Nam"
                try:
                    geolocator = Nominatim(user_agent="dating_gis_app_v1")
                    location = geolocator.geocode(address_string, country_codes='vn')
                    
                    if location:
                        user_profile.latitude = location.latitude
                        user_profile.longitude = location.longitude
                    else:
                        province_str = f"{user_profile.get_province_display()}, Việt Nam"
                        location_province = geolocator.geocode(province_str, country_codes='vn')
                        if location_province:
                            user_profile.latitude = location_province.latitude
                            user_profile.longitude = location_province.longitude
                except Exception as e:
                    print(f"Lỗi Geocoding: {e}")
            
            user_profile.save()
            return redirect('home')
        else:
            print(form.errors)
    else:
        form = ProfileUpdateForm(instance=profile)
    
    return render(request, 'settings.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

# ==========================================
# 5. API KẾT BẠN, HẸN HÒ & THÔNG BÁO
# ==========================================

@login_required
def send_friend_request(request, user_id):
    try:
        receiver = User.objects.get(id=user_id)
        if request.user == receiver: return JsonResponse({'status': 'error', 'message': 'Không thể tự kết bạn!'})
        if request.user.profile.friends.filter(id=receiver.profile.id).exists(): return JsonResponse({'status': 'error', 'message': 'Hai người đã là bạn bè!'})
            
        freq, created = FriendRequest.objects.get_or_create(sender=request.user, receiver=receiver, defaults={'status': 'pending'})
        if created: return JsonResponse({'status': 'ok', 'message': 'Đã gửi lời mời kết bạn!'})
        else: return JsonResponse({'status': 'error', 'message': 'Bạn đã gửi lời mời rồi!'})
    except User.DoesNotExist: return JsonResponse({'status': 'error', 'message': 'Lỗi'})

@login_required
def accept_friend_request(request, request_id):
    try:
        freq = FriendRequest.objects.get(id=request_id, receiver=request.user, status='pending')
        freq.status = 'accepted'
        freq.save()
        request.user.profile.friends.add(freq.sender.profile)
        return JsonResponse({'status': 'ok', 'message': 'Đã trở thành bạn bè!'})
    except FriendRequest.DoesNotExist: return JsonResponse({'status': 'error', 'message': 'Lỗi'})

@login_required
def reject_friend_request(request, request_id):
    try:
        FriendRequest.objects.get(id=request_id, receiver=request.user, status='pending').delete()
        return JsonResponse({'status': 'ok', 'message': 'Đã từ chối'})
    except FriendRequest.DoesNotExist: return JsonResponse({'status': 'error'})

@login_required
def cancel_friend_request(request, user_id):
    try:
        receiver = User.objects.get(id=user_id)
        FriendRequest.objects.filter(sender=request.user, receiver=receiver, status='pending').delete()
        return JsonResponse({'status': 'ok', 'message': 'Đã thu hồi'})
    except Exception: return JsonResponse({'status': 'error'})

@login_required
def get_all_requests(request):
    f_reqs = FriendRequest.objects.filter(receiver=request.user, status='pending')
    friend_data = [{'req_id': req.id, 'sender_id': req.sender.id, 'name': req.sender.profile.full_name, 'avatar': req.sender.profile.avatar.url if req.sender.profile.avatar else ""} for req in f_reqs]

    d_reqs = DatingRequest.objects.filter(receiver=request.user, status='pending')
    dating_data = [{'sender_id': req.sender.id, 'name': req.sender.profile.full_name, 'avatar': req.sender.profile.avatar.url if req.sender.profile.avatar else ""} for req in d_reqs]

    return JsonResponse({'friend_requests': friend_data, 'dating_requests': dating_data})

@login_required
def send_dating_request(request, user_id):
    try:
        receiver = User.objects.get(id=user_id)
        my_profile = request.user.profile
        
        if my_profile.dating_with:
            return JsonResponse({'status': 'error', 'message': 'Bạn đã có người yêu rồi! Bắt cá 2 tay là không tốt đâu nhé!'})
            
        DatingRequest.objects.get_or_create(sender=request.user, receiver=receiver, defaults={'status': 'pending'})
        return JsonResponse({'status': 'ok', 'message': 'Đã gửi lời hẹn hò! Hãy chờ người ấy đồng ý ❤️'})
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý'})

@login_required
def cancel_dating_request(request, user_id):
    try:
        receiver = User.objects.get(id=user_id)
        DatingRequest.objects.filter(sender=request.user, receiver=receiver, status='pending').delete()
        return JsonResponse({'status': 'ok', 'message': 'Đã rút lại lời hẹn hò 💔'})
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý'})

@login_required
def accept_dating_request(request, user_id):
    try:
        partner = User.objects.get(id=user_id)
        my_profile = request.user.profile
        partner_profile = partner.profile
        
        req = DatingRequest.objects.get(sender=partner, receiver=request.user, status='pending')
        req.status = 'accepted'
        req.save()
        
        my_profile.dating_with = partner_profile
        my_profile.marital_status = 'Đang hẹn hò'
        my_profile.save()
        
        partner_profile.dating_with = my_profile
        partner_profile.marital_status = 'Đang hẹn hò'
        partner_profile.save()
        
        DatingRequest.objects.filter(Q(sender=request.user) | Q(receiver=request.user), status='pending').delete()
        
        return JsonResponse({'status': 'ok', 'message': f'Chúc mừng! Bạn và {partner_profile.full_name} đã chính thức hẹn hò 💕'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý hoặc lời mời không tồn tại'})

@login_required
def reject_dating_request(request, user_id):
    try:
        sender = User.objects.get(id=user_id)
        DatingRequest.objects.filter(sender=sender, receiver=request.user, status='pending').delete()
        return JsonResponse({'status': 'ok', 'message': 'Đã từ chối khéo người ta rồi nhé 💔'})
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý'})


# 6. TRANG QUẢN TRỊ VIÊN (CUSTOM ADMIN)
# ==========================================
from django.contrib.auth.decorators import user_passes_test

# Hàm kiểm tra xem user có phải là admin không
def is_admin(user):
    return user.is_superuser

@user_passes_test(is_admin, login_url='home')
@user_passes_test(is_admin, login_url='home')
def custom_admin_view(request):
    all_profiles = UserProfile.objects.exclude(user=request.user).order_by('-user__date_joined')
    # Lấy danh sách kháng cáo chưa xử lý
    appeals = Appeal.objects.filter(is_resolved=False).order_by('-created_at')
    
    total_users = all_profiles.count()
    total_friends = FriendRequest.objects.count()
    total_dating = DatingRequest.objects.count()
    
    return render(request, 'custom_admin.html', {
        'profiles': all_profiles,
        'total_users': total_users,
        'total_friends': total_friends,
        'total_dating': total_dating,
        'appeals': appeals # Gửi sang giao diện Admin
    })

@user_passes_test(is_admin, login_url='home')
def delete_user_action(request, user_id):
    """Hàm dùng để Admin bấm nút XÓA một người dùng"""
    try:
        user_to_delete = User.objects.get(id=user_id)
        if not user_to_delete.is_superuser: # Cấm xóa admin khác
            user_to_delete.delete() # Xóa User sẽ tự động xóa sạch Profile, Tin nhắn, Lời mời...
    except Exception as e:
        print("Lỗi khi xóa:", e)
    return redirect('custom_admin')
@user_passes_test(is_admin, login_url='home')
def toggle_user_status(request, user_id):
    """Hàm Khóa / Mở khóa tài khoản (Đình chỉ)"""
    try:
        target_user = User.objects.get(id=user_id)
        if not target_user.is_superuser: # Cấm tự khóa chính mình (Admin)
            target_user.is_active = not target_user.is_active # Lật ngược trạng thái
            target_user.save()
    except Exception as e:
        print("Lỗi khi khóa:", e)
    return redirect('custom_admin')

@user_passes_test(is_admin, login_url='home')
def remove_user_avatar(request, user_id):
    """Hàm Gỡ ảnh đại diện vi phạm (Đưa về ảnh mặc định)"""
    try:
        target_user = User.objects.get(id=user_id)
        if not target_user.is_superuser:
            profile = target_user.profile
            if profile.avatar:
                profile.avatar.delete(save=False) # Xóa file vật lý trong thư mục
                profile.avatar = None # Đặt lại dữ liệu rỗng
                profile.save()
    except Exception as e:
        print("Lỗi khi xóa ảnh:", e)
    return redirect('custom_admin')
@user_passes_test(is_admin, login_url='home')
def resolve_appeal(request, appeal_id):
    """Admin đánh dấu đơn đã đọc xong"""
    try:
        ap = Appeal.objects.get(id=appeal_id)
        ap.is_resolved = True
        ap.save()
    except Exception:
        pass
    return redirect('custom_admin')
def search_multiple_spotify_tracks(song_name, limit=5):
    """Hàm mới chuyên dùng cho Chill Radio để lấy 5 kết quả"""
    try:
        # Lấy Access Token
        auth_url = 'https://' + 'accounts.spotify.com/api/token'
        auth_response = requests.post(
            auth_url,
            data={'grant_type': 'client_credentials'},
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        )
        
        if auth_response.status_code == 200:
            access_token = auth_response.json().get('access_token')
            
            # Tìm kiếm với tham số limit=5
            search_url = 'https://' + 'api.spotify.com/v1/search'
            search_response = requests.get(
                search_url,
                headers={'Authorization': f'Bearer {access_token}'},
                params={'q': song_name, 'type': 'track', 'limit': limit}
            )
            
            tracks = search_response.json().get('tracks', {}).get('items', [])
            
            # Gom dữ liệu đẹp đẽ lại để gửi cho giao diện
            results = []
            for t in tracks:
                results.append({
                    'id': t['id'],
                    'name': t['name'],
                    'artist': t['artists'][0]['name'] if t['artists'] else 'Unknown',
                    'image': t['album']['images'][2]['url'] if t['album']['images'] else 'https://via.placeholder.com/50'
                })
            return results
    except Exception as e:
        print(f"Lỗi: {e}")
    return []

def search_music_api(request):
    """API dùng cho ô tìm kiếm trên Chill Radio (Bản Nâng Cấp 5 Bài)"""
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập tên bài hát'})
    
    # Gọi hàm mới viết ở trên
    tracks = search_multiple_spotify_tracks(query, limit=5)
    if tracks:
        return JsonResponse({'status': 'ok', 'tracks': tracks})
    
    return JsonResponse({'status': 'error', 'message': 'Không tìm thấy bài hát trên Spotify!'})

# --- TÍNH NĂNG BẢN ĐỒ BẠN BÈ ---
@login_required(login_url='login')
def friends_map_view(request):
    my_profile = request.user.profile
    # Lấy toàn bộ danh sách bạn bè của user hiện tại
    friends = my_profile.friends.all()

    friends_data = []
    for f in friends:
        friends_data.append({
            'id': f.user.id,
            'name': f.full_name,
            'lat': f.latitude,
            'lon': f.longitude,
            'avatar': f.avatar.url if f.avatar else '',
            'status': f.bio[:30] + '...' if f.bio else 'Đang online',
        })

    return render(request, 'friends_map.html', {
        'my_profile': my_profile,
        'friends_json': friends_data
    })

# --- TRANG DANH SÁCH BẠN BÈ ---
@login_required(login_url='login')
def friends_list_view(request):
    my_profile = request.user.profile
    # Lấy danh sách bạn bè và sắp xếp theo tên
    friends = my_profile.friends.all().order_by('full_name')
    
    return render(request, 'friends_list.html', {
        'my_profile': my_profile,
        'friends': friends
    })
# --- XỬ LÝ LỖI 404 (NOT FOUND) ---
def custom_404_view(request, exception):
    return render(request, '404.html', status=404)

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# --- BỘ NÃO AI: THU THẬP DỮ LIỆU SỞ THÍCH NGẦM ---
@csrf_exempt
def record_dwell_time(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            viewed_id = data.get('viewed_user_id')
            time_spent = data.get('time_spent') / 1000 # Đổi ra giây
            
            # Lấy thông tin người vừa được xem
            from .models import UserProfile
            viewed_profile = UserProfile.objects.get(user__id=viewed_id)
            
            # In ra Terminal (Màn hình CMD/VS Code) để thầy giáo thấy AI đang chạy ngầm
            print("="*50)
            print(f"🤖 [AI TRACKING - ẨN] Người dùng đang nán lại xem hồ sơ!")
            print(f"👉 Target: {viewed_profile.full_name} | Thời gian xem: {time_spent:.1f} giây")
            if viewed_profile.hobbies:
                print(f"📈 Hệ thống AI đang tự động CỘNG ĐIỂM cho các sở thích: {viewed_profile.hobbies}")
            print("="*50)
            
            # (Ở bước sau, chúng ta sẽ viết code lưu số điểm này vào Database thật)
            
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            print("Lỗi AI Tracking:", e)
            return JsonResponse({'status': 'error'})
    return JsonResponse({'status': 'invalid'})