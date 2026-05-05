import random
import requests
import json
import profile
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
from .models import Post
from .forms import PostForm
from .models import UserProfile, Message, PROVINCE_CHOICES, FriendRequest, DatingRequest, Appeal
from .gis_tools import DatingGISTool
from .forms import RegisterForm, ProfileUpdateForm
from django.contrib.admin.views.decorators import staff_member_required
from .models import Post, Comment, Report, PostImage, AdminLog


# ==========================================
# 1. HÀM TÌM NHẠC 
# ==========================================
SPOTIFY_CLIENT_ID = '4b4fa7d5b6b344caac93b31fcf02a0b0' # Copy từ ảnh của bạn
SPOTIFY_CLIENT_SECRET = '3be3b8f1ce4d49ed954d2d3a5909ebce' # Bấm "View client secret" để lấy

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
        gallery_images = []
        # Tự động lấy tất cả ảnh từ các bài đăng (Post) của người dùng này
        # Loại bỏ những bài đăng chỉ có chữ (không có ảnh)
        user_posts_with_images = u.user.posts.exclude(image='').exclude(image__isnull=True)
        for post in user_posts_with_images:
            gallery_images.append(post.image.url)
        
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
        Message.objects.filter(sender=target_user, receiver=current_user, is_read=False).update(is_read=True)
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
        data = json.loads(request.body)
        receiver = User.objects.get(id=data.get('receiver_id'))
        
        # Nhận thêm cờ is_anonymous từ Javascript gửi lên
        is_anon = data.get('is_anonymous', False) 
        
        Message.objects.create(
            sender=request.user, 
            receiver=receiver, 
            content=data.get('content'),
            is_anonymous=is_anon # Lưu trạng thái ẩn danh
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'})

@login_required
def get_conversations(request):
    all_msgs = Message.objects.filter(Q(sender=request.user) | Q(receiver=request.user)).order_by('-timestamp')
    partners = {}
    conv_list = []
    
    for m in all_msgs:
        p_id = m.receiver.id if m.sender == request.user else m.sender.id
        
        # Gộp nhóm dựa trên CẢ partner_id VÀ trạng thái ẩn danh
        # (Để 2 người có thể có 2 đoạn chat song song: 1 thật, 1 ẩn danh)
        key = f"{p_id}_{m.is_anonymous}" 
        
        if key not in partners:
            partners[key] = True
            p_user = User.objects.get(id=p_id)
            
            # LOGIC CHE GIẤU DANH TÍNH CỰC HAY
            if m.is_anonymous and m.sender != request.user:
                # Nếu mình là người nhận và tin nhắn này là ẩn danh
                display_name = "Người lạ ẩn danh 🕵️"
                display_avatar = "/static/images/anonymous.png" # Bạn tải 1 cái ảnh vô danh vào thư mục static nhé
            else:
                # Nếu mình gửi, hoặc là tin nhắn công khai
                display_name = p_user.profile.full_name
                display_avatar = p_user.profile.avatar.url if p_user.profile.avatar else ""
                # Nếu mình là người đi gửi thầm kín, hiện chữ nhắc nhở mình
                if m.is_anonymous and m.sender == request.user:
                    display_name += " (Bạn đang ẩn danh)"

            conv_list.append({
                'partner_id': p_id, 
                'name': display_name, 
                'avatar': display_avatar,
                'last_msg': m.content[:30], 
                'time': timezone.localtime(m.timestamp).strftime("%H:%M %d/%m"), 
                'is_me': m.sender == request.user,
                'is_anonymous': m.is_anonymous # Trả về cờ này để Frontend chia Tab
            })
            
    return JsonResponse({'conversations': conv_list})
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

    # Lưu lại thông tin cũ để làm cơ sở so sánh
    old_address = profile.address or ""
    old_province = profile.province or ""

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if form.is_valid():
            user_profile = form.save(commit=False)
            
            raw_lat = request.POST.get('latitude', '').strip()
            raw_lon = request.POST.get('longitude', '').strip()
            map_interacted = request.POST.get('map_interacted') == 'true'
            
            new_address = user_profile.address or ""
            # Kiểm tra xem người dùng có gõ địa chỉ mới không
            address_changed = (old_address != new_address) or (old_province != user_profile.province)
            
            # --- LUẬT 1: NẾU CÓ CHẠM GHIM -> Lấy theo ghim tuyệt đối ---
            if map_interacted and raw_lat and raw_lon:
                try:
                    user_profile.latitude = float(raw_lat)
                    user_profile.longitude = float(raw_lon)
                except ValueError: pass
                
            # --- LUẬT 2: KHÔNG CHẠM GHIM, NHƯNG CÓ GÕ ĐỊA CHỈ MỚI -> Dịch địa chỉ ---
            elif address_changed:
                address_string = f"{new_address}, {user_profile.get_province_display()}, Việt Nam"
                try:
                    geolocator = Nominatim(user_agent="dating_gis_app_v1")
                    location = geolocator.geocode(address_string, country_codes='vn', timeout=10)
                    if location:
                        user_profile.latitude = location.latitude
                        user_profile.longitude = location.longitude
                    else:
                        province_str = f"{user_profile.get_province_display()}, Việt Nam"
                        loc_prov = geolocator.geocode(province_str, country_codes='vn')
                        if loc_prov:
                            user_profile.latitude = loc_prov.latitude
                            user_profile.longitude = loc_prov.longitude
                except Exception as e:
                    print(f"Lỗi Geocoding: {e}")
                    if raw_lat and raw_lon: # Lỗi mạng thì xài lại tọa độ cũ
                        try:
                            user_profile.latitude = float(raw_lat)
                            user_profile.longitude = float(raw_lon)
                        except ValueError: pass
                        
            # --- LUẬT 3: KHÔNG CHẠM GHIM, CŨNG KHÔNG ĐỔI ĐỊA CHỈ -> Giữ nguyên ghim cũ ---
            else:
                if raw_lat and raw_lon:
                    try:
                        user_profile.latitude = float(raw_lat)
                        user_profile.longitude = float(raw_lon)
                    except ValueError: pass
            
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

# Sửa lại hàm này trong views.py
@user_passes_test(is_admin, login_url='home')
def custom_admin_view(request):
    all_profiles = UserProfile.objects.exclude(user=request.user).order_by('-user__date_joined')
    
    # 1. Lấy danh sách kháng cáo
    appeals = Appeal.objects.filter(is_resolved=False).order_by('-created_at')
    
    # 2. CHÌA KHÓA Ở ĐÂY: Kéo danh sách Report từ Database lên
    reports = Report.objects.filter(is_resolved=False).order_by('-created_at')
    
    total_users = all_profiles.count()
    total_friends = FriendRequest.objects.count()
    total_dating = DatingRequest.objects.count()
    admin_logs = AdminLog.objects.all()[:50] # Lấy 50 hành động gần nhất
    
    return render(request, 'custom_admin.html', {
        'profiles': all_profiles,
        'total_users': total_users,
        'total_friends': total_friends,
        'total_dating': total_dating,
        'appeals': appeals,
        'reports': reports # BẮT BUỘC PHẢI GỬI BIẾN NÀY SANG HTML THÌ MỚI HIỆN BẢNG
    })

@user_passes_test(is_admin, login_url='home')
def delete_user_action(request, user_id):
    """Hàm dùng để Admin bấm nút XÓA một người dùng"""
    try:
        user_to_delete = User.objects.get(id=user_id)
        if not user_to_delete.is_superuser: # Cấm xóa admin khác
            # --- 1. GHI HỘP ĐEN TRƯỚC KHI XÓA ---
            AdminLog.objects.create(
                admin=request.user,
                action_type='WARNING', # Mượn tạm type này hoặc bạn có thể thêm 'DELETE_USER' vào model
                target_info=f"XÓA VĨNH VIỄN tài khoản ID {user_to_delete.id}: '{user_to_delete.username}'",
                reason="Admin thực hiện xóa khỏi hệ thống"
            )
            # --- 2. XÓA ---
            user_to_delete.delete() 
    except Exception as e:
        print("Lỗi khi xóa:", e)
    return redirect('custom_admin')

@user_passes_test(is_admin, login_url='home')
def toggle_user_status(request, user_id):
    """Hàm Khóa / Mở khóa tài khoản (Đình chỉ)"""
    try:
        target_user = User.objects.get(id=user_id)
        if not target_user.is_superuser: # Cấm tự khóa chính mình
            target_user.is_active = not target_user.is_active 
            target_user.save()
            
            # --- GHI HỘP ĐEN ADMINLOG ---
            action = 'SUSPEND_USER' if not target_user.is_active else 'WARNING' 
            status_text = "Khóa tài khoản" if not target_user.is_active else "Mở khóa tài khoản"
            
            AdminLog.objects.create(
                admin=request.user,
                action_type=action,
                target_info=f"Tài khoản ID {target_user.id}: '{target_user.username}'",
                reason=f"Admin thực hiện {status_text} từ trang Quản trị"
            )
            # ---------------------------
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
                # --- GHI HỘP ĐEN ADMINLOG ---
                AdminLog.objects.create(
                    admin=request.user,
                    action_type='DELETE_PHOTO',
                    target_info=f"Ảnh đại diện của tài khoản '{target_user.username}'",
                    reason="Admin gỡ ảnh vi phạm tiêu chuẩn cộng đồng"
                )
                # ---------------------------
                profile.avatar.delete(save=False) 
                profile.avatar = None 
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
        # 1. URL chuẩn để lấy Token của Spotify (đã fix)
        auth_url = 'https://' + 'accounts.spotify.com/api/token' 
        auth_response = requests.post(
            auth_url,
            data={'grant_type': 'client_credentials'},
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        )
        
        if auth_response.status_code == 200:
            access_token = auth_response.json().get('access_token')
            
            # 2. URL chuẩn để tìm kiếm bài hát của Spotify (đã fix)
            search_url = 'https://' + 'api.spotify.com/v1/search' 
            search_response = requests.get(
                search_url,
                headers={'Authorization': f'Bearer {access_token}'},
                params={'q': song_name, 'type': 'track', 'limit': limit}
            )
            
            tracks = search_response.json().get('tracks', {}).get('items', [])
            
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
import csv
import os
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import UserProfile

@csrf_exempt
def record_dwell_time(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            viewed_id = data.get('viewed_user_id')
            time_spent = data.get('time_spent') / 1000 # Đổi ra giây
            
            # --- LUẬT CHỐNG TREO MÁY (AFK) ---
            # 5 phút = 300 giây. Nếu xem lâu hơn 300s thì từ chối ghi nhận!
            if time_spent > 300:
                print(f"🚫 [AI TRACKING] Bỏ qua ({time_spent:.1f}s) - Phát hiện người dùng treo máy!")
                return JsonResponse({'status': 'ignored', 'message': 'Treo máy, từ chối ghi điểm'})
            
            viewed_profile = UserProfile.objects.get(user__id=viewed_id)
            
            # --- LƯU VÀO FILE CSV ẨN ---
            file_path = os.path.join(settings.BASE_DIR, 'ai_tracking_data.csv')
            file_exists = os.path.isfile(file_path)
            
            with open(file_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(['Thoi_Gian', 'Nguoi_Xem', 'Nguoi_Duoc_Xem', 'Thoi_Gian_Xem_Giay', 'So_Thich_Lien_Quan'])
                
                viewer_name = request.user.username if request.user.is_authenticated else "Khach_An_Danh"
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    viewer_name,
                    viewed_profile.full_name,
                    round(time_spent, 1),
                    viewed_profile.hobbies
                ])
                
            print(f"🤖 [AI TRACKING] Đã ghi nhận: Xem '{viewed_profile.full_name}' trong {time_spent:.1f}s")
            return JsonResponse({'status': 'ok'})
            
        except Exception as e:
            print("Lỗi AI Tracking:", e)
            return JsonResponse({'status': 'error'})
    return JsonResponse({'status': 'invalid'})

import random
from django.core.mail import send_mail
from django.conf import settings
from .models import PasswordResetOTP

# ==========================================
# QUÊN MẬT KHẨU
# ==========================================
def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            # 1. Tạo mã OTP ngẫu nhiên 6 số
            otp = str(random.randint(100000, 999999))
            
            # 2. Lưu vào Database
            PasswordResetOTP.objects.create(email=email, otp_code=otp)
            
            # 3. Gửi Email
            subject = 'Mã xác nhận khôi phục mật khẩu - Dating GIS'
            message = f'Chào {user.username},\n\nMã xác nhận khôi phục mật khẩu của bạn là: {otp}\nLưu ý: Mã này chỉ có hiệu lực trong 1 phút.\n\nNếu bạn không yêu cầu, vui lòng bỏ qua email này.'
            try:
                send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
                # Lưu email vào session để dùng ở bước sau
                request.session['reset_email'] = email
                return redirect('verify_otp')
            except Exception as e:
                return render(request, 'forgot_password.html', {'error': 'Lỗi hệ thống khi gửi email!'})
        else:
            return render(request, 'forgot_password.html', {'error': 'Email này chưa được đăng ký trong hệ thống.'})
            
    return render(request, 'forgot_password.html')

def verify_otp_view(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')
        
    if request.method == 'POST':
        otp_input = request.POST.get('otp')
        # Lấy bản ghi OTP mới nhất của email này
        otp_record = PasswordResetOTP.objects.filter(email=email).order_by('-created_at').first()
        
        if otp_record and otp_record.otp_code == otp_input:
            if otp_record.is_valid(): # Hàm kiểm tra 1 phút trong model của bạn
                request.session['otp_verified'] = True # Đánh dấu đã xác thực thành công
                return redirect('reset_password')
            else:
                return render(request, 'verify_otp.html', {'error': 'Mã OTP đã hết hạn (quá 1 phút). Vui lòng yêu cầu mã mới.', 'email': email})
        else:
            return render(request, 'verify_otp.html', {'error': 'Mã OTP không chính xác.', 'email': email})
            
    return render(request, 'verify_otp.html', {'email': email})

def reset_password_view(request):
    # Kiểm tra xem user đã vượt qua bước nhập OTP chưa
    if not request.session.get('otp_verified'):
        return redirect('forgot_password')
        
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password == confirm_password:
            email = request.session.get('reset_email')
            user = User.objects.get(email=email)
            user.set_password(new_password) # Mã hóa mật khẩu mới
            user.save()
            
            # Dọn dẹp session
            del request.session['reset_email']
            del request.session['otp_verified']
            
            return redirect('login')
        else:
            return render(request, 'reset_password.html', {'error': 'Hai mật khẩu không khớp nhau.'})
            
    return render(request, 'reset_password.html')

# 7. BẢNG TIN (FEED) & BÀI VIẾT
# ==========================================
from .models import Post, Comment, Report, PostImage

@login_required(login_url='login')
def feed_view(request):
    my_profile = request.user.profile
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        images = request.FILES.getlist('images')
        
        # --- ĐOẠN NÀY LÀ MÁY QUÉT LỖI (SẼ IN RA TERMINAL) ---
        print("====== HỆ THỐNG KIỂM TRA ĐĂNG BÀI ======")
        print(f"1. Nội dung chữ: '{content}'")
        print(f"2. Số lượng ảnh tải lên: {len(images)} ảnh")
        print("========================================")
        
        if content or images:
            new_post = Post.objects.create(author=request.user, content=content)
            for img in images:
                PostImage.objects.create(post=new_post, image=img)
                
        return redirect('feed')
        
    # NẾU LÀ GET REQUEST
    posts = Post.objects.all().select_related('author__profile').prefetch_related('likes', 'images').order_by('-created_at')
    
    return render(request, 'feed.html', {
        'posts': posts,
        'my_profile': my_profile
    })
# Đặt hàm này ngay bên dưới hàm feed_view trong file views.py
@login_required
def toggle_like_post(request, post_id):
    """Hàm xử lý thả tim / bỏ tim bài viết"""
    try:
        post = Post.objects.get(id=post_id)
        if request.user in post.likes.all():
            post.likes.remove(request.user) # Nếu đã tim rồi thì bấm lại sẽ bỏ tim
        else:
            post.likes.add(request.user) # Thả tim
    except Post.DoesNotExist:
        pass
    return redirect('feed')

# Duplicate settings_view removed — the earlier settings_view (which uses ProfileUpdateForm and geocoding)
# remains in this file and should be used; this removed block prevented a redefinition and
# avoided using an undefined 'profile' variable.

# 1. GỬI BÌNH LUẬN
@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        if content:
            post = Post.objects.get(id=post_id)
            Comment.objects.create(post=post, user=request.user, content=content)
            return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'message': 'Lỗi rỗng'})

# 2. GỬI BÁO CÁO (REPORT)
@login_required
def report_post(request, post_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        if reason:
            post = Post.objects.get(id=post_id)
            Report.objects.create(post=post, user=request.user, reason=reason)
            return JsonResponse({'status': 'ok', 'message': 'Đã gửi báo cáo cho Admin.'})
    return JsonResponse({'status': 'error'})

# 3. QUYỀN ADMIN: XÓA BÀI VIẾT
@staff_member_required # Chỉ Admin/Staff mới được chạy hàm này
@login_required
def delete_post(request, post_id): # <--- CHÚ Ý TÊN HÀM NÀY
    if request.method == 'POST' and request.user.is_superuser:
        print(f"\n====== BẮT ĐẦU XÓA BÀI ID {post_id} ======")
        try:
            post = Post.objects.get(id=post_id)
            
            # Xử lý nội dung an toàn để không bị lỗi
            noidung = post.content if post.content else "Chỉ chứa ảnh"
            target_str = f"Bài viết ID {post.id} của '{post.author.username}' ({noidung[:30]})"
            
            print("1. Đang ghi vào Hộp đen AdminLog...")
            AdminLog.objects.create(
                admin=request.user,
                action_type='DELETE_POST',
                target_info=target_str,
                reason="Xóa từ Bảng tin"
            )
            
            print("2. Đang tiến hành xóa bài...")
            post.delete()
            print("3. Đã xóa và ghi Log THÀNH CÔNG!\n======================================")
            
            return JsonResponse({'status': 'ok'})
            
        except Exception as e:
            print(f"!!! LỖI RỒI: {e} !!!")
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error', 'message': 'Từ chối truy cập'})

# Sửa lại hàm resolve_report
@staff_member_required
def resolve_report(request, report_id):
    try:
        # 1. Tìm cái Report mà Admin vừa bấm
        clicked_report = Report.objects.get(id=report_id)
        
        # 2. Cập nhật ĐỒNG LOẠT tất cả các Report có cùng bài viết đó thành "Đã xử lý"
        Report.objects.filter(post=clicked_report.post).update(is_resolved=True)
        
    except Report.DoesNotExist:
        pass
        
    return redirect('custom_admin') # Nhớ đảm bảo 'custom_admin' đúng với tên name trong urls.py nhé
@login_required
def check_unread_messages(request):
    """API trả về số lượng tin nhắn chưa đọc của user hiện tại"""
    unread_count = Message.objects.filter(receiver=request.user, is_read=False).count()
    return JsonResponse({
        'has_unread': unread_count > 0, 
        'count': unread_count
    })
