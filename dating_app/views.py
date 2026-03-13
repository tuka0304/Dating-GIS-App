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

from .models import UserProfile, Message, PROVINCE_CHOICES, FriendRequest, DatingRequest
from .gis_tools import DatingGISTool
from .forms import RegisterForm, ProfileUpdateForm

# ==========================================
# 1. HÀM LẤY MÁY PHÁT NHẠC SOUNDCLOUD (OEMBED)
# ==========================================
def get_soundcloud_embed(track_url):
    try:
        url = f"https://soundcloud.com/oembed?format=json&url={track_url}&maxheight=166"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json().get('html')
    except Exception as e:
        print(f"Lỗi SoundCloud: {e}")
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

        # --- ĐÁNH DẤU CHỦ QUYỀN (@TÊN) ---
        display_marital = u.marital_status
        if u.dating_with:
            display_marital = f"Đang hẹn hò với @{u.dating_with.full_name} 💍"
        
        # Xử lý Playlist nhạc SoundCloud
        processed_playlist = []
        if u.music_playlist:
            song_lines = [s.strip() for s in u.music_playlist.split('\n') if s.strip()]
            for song in song_lines:
                if 'soundcloud.com' in song:
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


# --- BỘ HÀM XỬ LÝ TRUNG TÂM THÔNG BÁO ---
@login_required
def get_all_requests(request):
    """Gộp chung cả Lời mời kết bạn và Lời hẹn hò vào 1 API"""
    # 1. Lấy lời mời kết bạn
    f_reqs = FriendRequest.objects.filter(receiver=request.user, status='pending')
    friend_data = [{'req_id': req.id, 'sender_id': req.sender.id, 'name': req.sender.profile.full_name, 'avatar': req.sender.profile.avatar.url if req.sender.profile.avatar else ""} for req in f_reqs]

    # 2. Lấy lời mời hẹn hò
    d_reqs = DatingRequest.objects.filter(receiver=request.user, status='pending')
    dating_data = [{'sender_id': req.sender.id, 'name': req.sender.profile.full_name, 'avatar': req.sender.profile.avatar.url if req.sender.profile.avatar else ""} for req in d_reqs]

    return JsonResponse({'friend_requests': friend_data, 'dating_requests': dating_data})


# --- BỘ HÀM XỬ LÝ HẸN HÒ ---
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
        
        # 1. Chuyển status request
        req = DatingRequest.objects.get(sender=partner, receiver=request.user, status='pending')
        req.status = 'accepted'
        req.save()
        
        # 2. Gắn chủ quyền cho cả 2 người
        my_profile.dating_with = partner_profile
        my_profile.marital_status = 'Đang hẹn hò'
        my_profile.save()
        
        partner_profile.dating_with = my_profile
        partner_profile.marital_status = 'Đang hẹn hò'
        partner_profile.save()
        
        # 3. Xóa các request rác khác (nếu có)
        DatingRequest.objects.filter(Q(sender=request.user) | Q(receiver=request.user), status='pending').delete()
        
        return JsonResponse({'status': 'ok', 'message': f'Chúc mừng! Bạn và {partner_profile.full_name} đã chính thức hẹn hò 💕'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý hoặc lời mời không tồn tại'})

@login_required
def reject_dating_request(request, user_id):
    """Từ chối lời hẹn hò từ trong thông báo"""
    try:
        sender = User.objects.get(id=user_id)
        DatingRequest.objects.filter(sender=sender, receiver=request.user, status='pending').delete()
        return JsonResponse({'status': 'ok', 'message': 'Đã từ chối khéo người ta rồi nhé 💔'})
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Lỗi xử lý'})