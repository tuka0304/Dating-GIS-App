import random
import requests
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone 
from geopy.geocoders import Nominatim

from .models import UserProfile, Message, PROVINCE_CHOICES, FriendRequest
from .gis_tools import DatingGISTool
from .forms import RegisterForm, ProfileUpdateForm

# ==========================================
# 1. HÀM HỖ TRỢ TÌM NHẠC TRÊN DEEZER
# ==========================================
def get_deezer_track_id(song_name):
    try:
        url = "https://api.deezer.com/search"
        params = {'q': song_name, 'limit': 1}
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if 'data' in data and len(data['data']) > 0:
            return data['data'][0]['id']
    except Exception as e:
        print(f"Lỗi Deezer: {e}")
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

    # --- Xử lý tham số tìm kiếm ---
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

    # --- Lọc danh sách ứng viên ---
    candidates = UserProfile.objects.exclude(id=my_profile.id)
    if gender_filter != 'ALL':
        candidates = candidates.filter(gender=gender_filter)

    if province_filter != 'ALL':
        candidates = candidates.filter(province=province_filter)
        final_calc_radius = 50000 
    else:
        final_calc_radius = search_radius

    # --- Tính toán GIS ---
    nearby_users = DatingGISTool.find_users_in_radius(my_location, candidates, final_calc_radius)
    random.shuffle(nearby_users)

    # --- Đóng gói JSON ---
    results_json = []
    song_cache = {} 

    for u in nearby_users:
        gallery_images = [p.image.url for p in u.gallery.all()] if hasattr(u, 'gallery') else []
        
        # --- THÊM ĐOẠN LOGIC KIỂM TRA TRẠNG THÁI NÀY ---
        rel_status = 'none'
        if request.user.profile.friends.filter(id=u.id).exists():
            rel_status = 'friends'
        elif FriendRequest.objects.filter(sender=request.user, receiver=u.user, status='pending').exists():
            rel_status = 'pending_sent'
        elif FriendRequest.objects.filter(sender=u.user, receiver=request.user, status='pending').exists():
            rel_status = 'pending_received'
        
        # Xử lý Playlist nhạc
        processed_playlist = []
        if u.music_playlist:
            song_lines = [s.strip() for s in u.music_playlist.split('\n') if s.strip()]
            for song in song_lines:
                if song in song_cache:
                    track_id = song_cache[song]
                else:
                    track_id = get_deezer_track_id(song)
                    song_cache[song] = track_id
                
                if track_id:
                    processed_playlist.append({'type': 'deezer', 'value': track_id})
                else:
                    processed_playlist.append({'type': 'text', 'value': song})
        
        results_json.append({
            'id': u.user.id,
            'name': u.full_name,
            'gender': u.gender,
            'age': u.get_age(),
            'marital_status': u.marital_status,
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
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

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
            
            # ƯU TIÊN 1: Lấy tọa độ chính xác từ GPS trình duyệt (nếu có)
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
            
            # ƯU TIÊN 2: Nếu không bấm GPS, tự động tìm bằng Geopy (Đã khoá VN)
            if not gps_success:
                address_string = f"{user_profile.address}, {user_profile.get_province_display()}, Việt Nam"
                try:
                    geolocator = Nominatim(user_agent="dating_gis_app_v1")
                    location = geolocator.geocode(address_string, country_codes='vn')
                    
                    if location:
                        user_profile.latitude = location.latitude
                        user_profile.longitude = location.longitude
                    else:
                        # Dự phòng: Chỉ tìm theo Tỉnh
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
            print("--- LỖI FORM KHÔNG HỢP LỆ ---")
            print(form.errors)
    else:
        form = ProfileUpdateForm(instance=profile)
    
    return render(request, 'settings.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

# ==========================================
# 5. API KẾT BẠN & HẸN HÒ
# ==========================================

@login_required
def send_friend_request(request, user_id):
    """Gửi lời mời kết bạn"""
    try:
        receiver = User.objects.get(id=user_id)
        if request.user == receiver:
            return JsonResponse({'status': 'error', 'message': 'Không thể tự kết bạn với chính mình!'})
        
        # Kiểm tra xem đã là bạn bè chưa
        if request.user.profile.friends.filter(id=receiver.profile.id).exists():
            return JsonResponse({'status': 'error', 'message': 'Hai người đã là bạn bè!'})
            
        # Tạo lời mời kết bạn (dùng get_or_create để tránh spam gửi nhiều lần)
        freq, created = FriendRequest.objects.get_or_create(
            sender=request.user, 
            receiver=receiver,
            defaults={'status': 'pending'}
        )
        
        if created:
            return JsonResponse({'status': 'ok', 'message': 'Đã gửi lời mời kết bạn!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Bạn đã gửi lời mời rồi, đang chờ người ta đồng ý!'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Người dùng không tồn tại'})


@login_required
def accept_friend_request(request, request_id):
    """Chấp nhận lời mời kết bạn"""
    try:
        freq = FriendRequest.objects.get(id=request_id, receiver=request.user, status='pending')
        freq.status = 'accepted'
        freq.save()
        
        # Thêm vào danh sách bạn bè của nhau (symmetrical=True nên chỉ cần add 1 phía, DB tự gán phía kia)
        request.user.profile.friends.add(freq.sender.profile)
        
        return JsonResponse({'status': 'ok', 'message': 'Đã trở thành bạn bè!'})
    except FriendRequest.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Lời mời không tồn tại hoặc đã bị hủy'})


@login_required
def reject_friend_request(request, request_id):
    """Từ chối lời mời kết bạn"""
    try:
        freq = FriendRequest.objects.get(id=request_id, receiver=request.user, status='pending')
        freq.delete() # Xóa luôn cho nhẹ Database
        return JsonResponse({'status': 'ok', 'message': 'Đã từ chối lời mời'})
    except FriendRequest.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý'})


@login_required
def set_dating_partner(request, user_id):
    """Xác nhận Hẹn hò (Chỉ 1 người duy nhất)"""
    try:
        partner = User.objects.get(id=user_id)
        my_profile = request.user.profile
        
        # Cập nhật trạng thái và "đánh dấu chủ quyền"
        my_profile.dating_with = partner.profile
        my_profile.marital_status = 'Đang hẹn hò'
        my_profile.save()
        
        return JsonResponse({'status': 'ok', 'message': f'Đã xác nhận hẹn hò với {partner.profile.full_name}! ❤️'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Người dùng không tồn tại'})
    
@login_required
def cancel_friend_request(request, user_id):
    """Gỡ lời mời kết bạn đã gửi"""
    try:
        receiver = User.objects.get(id=user_id)
        FriendRequest.objects.filter(sender=request.user, receiver=receiver, status='pending').delete()
        return JsonResponse({'status': 'ok', 'message': 'Đã thu hồi lời mời kết bạn'})
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý'})

@login_required
def get_friend_requests(request):
    """Lấy danh sách người khác xin kết bạn với mình"""
    requests = FriendRequest.objects.filter(receiver=request.user, status='pending')
    data = []
    for req in requests:
        avatar_url = req.sender.profile.avatar.url if req.sender.profile.avatar else ""
        data.append({
            'req_id': req.id,
            'sender_id': req.sender.id,
            'name': req.sender.profile.full_name,
            'avatar': avatar_url
        })
    return JsonResponse({'requests': data})