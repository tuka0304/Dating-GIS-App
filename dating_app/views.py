import random
from geopy.geocoders import Nominatim # <--- Thêm dòng này để tìm tọa độ
from .models import UserProfile, Message, PROVINCE_CHOICES
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Q
import json

# Import Models và Forms
from .models import UserProfile, Message
from .gis_tools import DatingGISTool
from .forms import RegisterForm
from .forms import RegisterForm, ProfileUpdateForm
# --- VIEW 1: BẢN ĐỒ & TÌM KIẾM ---
@login_required(login_url='login')
def map_search_view(request):
    try:
        my_profile = request.user.profile
    except UserProfile.DoesNotExist:
        my_profile = UserProfile.objects.create(user=request.user, full_name=request.user.username, latitude=10.7769, longitude=106.7009)

    my_location = (my_profile.latitude, my_profile.longitude)

    # --- 1. LẤY THAM SỐ ĐẦU VÀO ---
    try:
        radius = float(request.GET.get('radius', 10))
    except ValueError:
        radius = 10.0
    gender_filter = request.GET.get('gender', 'ALL')
    province_filter = request.GET.get('province', 'ALL')

    # --- 2. LỌC DATABASE CƠ BẢN ---
    candidates = UserProfile.objects.exclude(id=my_profile.id)
    if gender_filter != 'ALL':
        candidates = candidates.filter(gender=gender_filter)

    # --- 3. XỬ LÝ LOGIC ƯU TIÊN (MỚI) ---
    if province_filter != 'ALL':
        # TRƯỜNG HỢP 1: Đang chọn Tỉnh
        # -> Lọc theo Tỉnh
        candidates = candidates.filter(province=province_filter)
        # -> Bán kính coi như "Vô cực" (để lấy hết mọi người trong tỉnh đó dù ở xa)
        calc_radius = 50000 
    else:
        # TRƯỜNG HỢP 2: Không chọn Tỉnh (ALL)
        # -> Dùng Bán kính người dùng nhập để quét quanh mình
        calc_radius = radius

    # --- 4. TÍNH KHOẢNG CÁCH & LỌC ---
    # (Dùng Tool để tính khoảng cách cho từng người luôn)
    nearby_users = DatingGISTool.find_users_in_radius(my_location, candidates, calc_radius)
    
    # --- 5. RANDOM KẾT QUẢ (MỚI) ---
    # Trộn ngẫu nhiên danh sách thay vì xếp theo khoảng cách gần nhất
    random.shuffle(nearby_users)

    # --- 6. ĐÓNG GÓI JSON (Giữ nguyên) ---
    results_json = []
    for u in nearby_users:
        results_json.append({
            'id': u.user.id,
            'name': u.full_name,
            'gender': u.gender,
            'age': u.get_age(),
            'address': u.address,
            'lat': u.latitude,
            'lon': u.longitude,
            'distance': u.distance_km,
            'avatar': u.avatar.url if u.avatar else '',
            'cover': u.cover_photo.url if u.cover_photo else '',
            'bio': u.hobbies,
            'playlist': u.music_playlist.split('\n') if u.music_playlist else [],
            'hobbies': u.hobbies.split(',') if u.hobbies else []
        })

    return render(request, 'map_search.html', {
        'my_profile': my_profile,
        'results': results_json,
        'radius': radius,
        'selected_gender': gender_filter,
        'selected_province': province_filter,
        'provinces': PROVINCE_CHOICES
    })

# --- VIEW 2: API CHAT ---
@login_required
def get_messages(request, user_id):
    try:
        target_user = User.objects.get(id=user_id)
        current_user = request.user
        msgs = Message.objects.filter(
            Q(sender=current_user, receiver=target_user) | 
            Q(sender=target_user, receiver=current_user)
        ).order_by('timestamp')
        
        data = [{'sender': 'me' if m.sender == current_user else 'them', 
                 'content': m.content, 
                 'time': m.timestamp.strftime("%H:%M")} for m in msgs]
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
        except:
            return JsonResponse({'status': 'error'})
    return JsonResponse({'status': 'error'})

# --- VIEW 3: ĐĂNG KÝ / ĐĂNG NHẬP ---
def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # --- ĐOẠN NÀY LÀ MỚI ---
            # Lấy dữ liệu người dùng nhập từ form
            full_name = form.cleaned_data.get('full_name')
            gender = form.cleaned_data.get('gender')
            birth_date = form.cleaned_data.get('birth_date')

            # Tạo Profile với đầy đủ thông tin
            UserProfile.objects.create(
                user=user, 
                full_name=full_name, # Lưu tên thật
                gender=gender,       # Lưu giới tính
                birth_date=birth_date, # Lưu ngày sinh
                latitude=10.7769,    # Tọa độ mặc định (HCM)
                longitude=106.7009
            )
            # -----------------------

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
def settings_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            # 1. Lưu tạm các thông tin chữ trước (chưa lưu vào DB ngay)
            user_profile = form.save(commit=False)
            
            # 2. LOGIC TỰ ĐỘNG TÌM TỌA ĐỘ (GEOCODING)
            address_string = f"{user_profile.address}, {user_profile.get_province_display()}"
            print(f"Đang tìm tọa độ cho: {address_string}...") # In ra terminal để kiểm tra
            
            try:
                # Dùng Nominatim (OpenStreetMap) để tìm
                geolocator = Nominatim(user_agent="dating_gis_app_v1")
                location = geolocator.geocode(address_string)
                
                if location:
                    # Nếu tìm thấy -> Cập nhật tọa độ mới
                    user_profile.latitude = location.latitude
                    user_profile.longitude = location.longitude
                    print(f"Đã tìm thấy: {location.latitude}, {location.longitude}")
                else:
                    # Nếu không tìm thấy địa chỉ cụ thể -> Tìm theo Tên Tỉnh thôi
                    print("Không tìm thấy địa chỉ cụ thể, đang tìm theo Tỉnh...")
                    location_province = geolocator.geocode(user_profile.get_province_display())
                    if location_province:
                        user_profile.latitude = location_province.latitude
                        user_profile.longitude = location_province.longitude
            except Exception as e:
                print(f"Lỗi Geocoding: {e}")
                # Nếu lỗi mạng hoặc lỗi gì đó thì giữ nguyên tọa độ cũ

            # 3. Lưu chính thức vào Database
            user_profile.save()
            return redirect('home')
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, 'settings.html', {'form': form})
def logout_view(request):
    logout(request)
    return redirect('login')