from django.shortcuts import render
from django.http import JsonResponse
from .models import UserProfile
from .gis_tools import DatingGISTool # Import Tool xịn xò của nhóm mình

def map_search_view(request):
    # 1. Giả lập lấy User hiện tại (Vì chưa làm trang Login phức tạp)
    # Lấy user đầu tiên trong DB làm "Tôi". Nếu không có ai thì báo lỗi.
    try:
        my_profile = UserProfile.objects.first()
        if not my_profile:
            return render(request, 'error.html', {'message': 'Database trống! Hãy vào Admin thêm User.'})
    except:
        return render(request, 'error.html', {'message': 'Lỗi chưa chạy Migration.'})

    my_location = (my_profile.latitude, my_profile.longitude)

    # 2. Lấy tham số từ thanh tìm kiếm (Filter)
    # Mặc định tìm bán kính 10km nếu không chọn gì
    try:
        radius = float(request.GET.get('radius', 10))
    except ValueError:
        radius = 10.0
        
    gender_filter = request.GET.get('gender', 'ALL')

    # 3. Lọc dữ liệu thô từ Database (ORM)
    # Exclude: Loại bỏ chính mình ra khỏi danh sách tìm kiếm
    candidates = UserProfile.objects.exclude(id=my_profile.id)
    
    # Nếu có chọn giới tính thì lọc thêm
    if gender_filter != 'ALL':
        candidates = candidates.filter(gender=gender_filter)

    # 4. Sử dụng TOOL GIS để tính toán khoảng cách
    # Hàm này sẽ trả về danh sách những người nằm trong bán kính
    nearby_users = DatingGISTool.find_users_in_radius(my_location, candidates, radius)

    # 5. Đóng gói dữ liệu thành JSON để gửi sang Javascript (Frontend)
    results_json = []
    for u in nearby_users:
        results_json.append({
            'name': u.full_name,
            'gender': u.gender,
            'age': u.get_age(),
            'address': u.address,
            'lat': u.latitude,
            'lon': u.longitude,
            'distance': u.distance_km, # Thuộc tính này do Tool GIS tính ra
            'avatar': u.avatar.url if u.avatar else '',
            'cover': u.cover_photo.url if u.cover_photo else '',
            'bio': u.hobbies,
            'playlist': u.music_playlist.split('\n') if u.music_playlist else [],
            'hobbies': u.hobbies.split(',') if u.hobbies else []
        })

    # Gửi tất cả sang file HTML
    return render(request, 'map_search.html', {
        'my_profile': my_profile,
        'results': results_json,
        'radius': radius,
        'selected_gender': gender_filter
    })