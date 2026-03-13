from django.db import models
from django.contrib.auth.models import User
import datetime

# DANH SÁCH 34 TỈNH THÀNH (Giữ nguyên của bạn)
PROVINCE_CHOICES = [
    ('HNI', 'Thành phố Hà Nội'), ('HPH', 'Thành phố Hải Phòng'), ('TQU', 'Tỉnh Tuyên Quang'),
    ('LCA', 'Tỉnh Lào Cai'), ('TNG', 'Tỉnh Thái Nguyên'), ('PTH', 'Tỉnh Phú Thọ'),
    ('BNI', 'Tỉnh Bắc Ninh'), ('HYE', 'Tỉnh Hưng Yên'), ('NBI', 'Tỉnh Ninh Bình'),
    ('QNI', 'Tỉnh Quảng Ninh'), ('LSO', 'Tỉnh Lạng Sơn'), ('CBA', 'Tỉnh Cao Bằng'),
    ('LCH', 'Tỉnh Lai Châu'), ('DBI', 'Tỉnh Điện Biên'), ('SLA', 'Tỉnh Sơn La'),
    ('THA', 'Tỉnh Thanh Hoá'), ('NAN', 'Tỉnh Nghệ An'), ('HTI', 'Tỉnh Hà Tĩnh'),
    ('HUE', 'Thành phố Huế'), ('QTR', 'Tỉnh Quảng Trị'), ('DNG', 'Thành phố Đà Nẵng'),
    ('QNG', 'Tỉnh Quảng Ngãi'), ('GLA', 'Tỉnh Gia Lai'), ('KHO', 'Tỉnh Khánh Hoà'),
    ('DLA', 'Tỉnh Đắk Lắk'), ('LDO', 'Tỉnh Lâm Đồng'), ('HCM', 'Thành phố Hồ Chí Minh'),
    ('DNI', 'Tỉnh Đồng Nai'), ('TNI', 'Tỉnh Tây Ninh'), ('CTO', 'Thành phố Cần Thơ'),
    ('VLG', 'Tỉnh Vĩnh Long'), ('DTH', 'Tỉnh Đồng Tháp'), ('AGI', 'Tỉnh An Giang'),
    ('CMU', 'Tỉnh Cà Mau')
]

# TÌNH TRẠNG QUAN HỆ (MỚI)
MARITAL_CHOICES = [
    ('Độc thân', 'Độc thân vui tính'),
    ('Đang tìm hiểu', 'Đang tìm hiểu'),
    ('Đang hẹn hò', 'Đang hẹn hò (Hoa đã có chủ)'),
    ('Đã kết hôn', 'Đã kết hôn')
]

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # --- THÔNG TIN CƠ BẢN ---
    full_name = models.CharField(max_length=100, verbose_name="Họ tên")
    gender = models.CharField(max_length=10, choices=[('Nam', 'Nam'), ('Nữ', 'Nữ'), ('Khác', 'Khác')], default='Nam')
    birth_date = models.DateField(default=datetime.date(2000, 1, 1))
    
    # Tình trạng quan hệ (MỚI)
    marital_status = models.CharField(max_length=20, choices=MARITAL_CHOICES, default='Độc thân', verbose_name="Tình trạng")
    
    # --- PHẦN GIS (Tọa độ) ---
    province = models.CharField(max_length=10, choices=PROVINCE_CHOICES, default='HCM') 
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(default=10.8231, verbose_name="Vĩ độ")
    longitude = models.FloatField(default=106.6297, verbose_name="Kinh độ")

    # --- THÔNG TIN PHỤ ---
    bio = models.TextField(blank=True, verbose_name="Giới thiệu/Status")
    music_playlist = models.TextField(blank=True, help_text="Mỗi bài hát 1 dòng")
    hobbies = models.TextField(blank=True, help_text="Các sở thích cách nhau dấu phẩy")
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True)
    cover_photo = models.ImageField(upload_to='covers/', default='covers/default.jpg', blank=True)

    # ==========================================
    # --- TÍNH NĂNG MẠNG XÃ HỘI (MỚI THÊM) ---
    # ==========================================
    
    # 1. Danh sách bạn bè (Nhiều - Nhiều)
    friends = models.ManyToManyField('self', blank=True, symmetrical=True, verbose_name="Danh sách bạn bè")
    
    # 2. Xác nhận hẹn hò (1 - 1, chỉ được chọn 1 người duy nhất)
    dating_with = models.OneToOneField('self', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Đang hẹn hò với")

    def __str__(self):
        return self.full_name
    
    def get_age(self):
        return datetime.date.today().year - self.birth_date.year


# --- CLASS LỜI MỜI KẾT BẠN (MỚI THÊM) ---
class FriendRequest(models.Model):
    sender = models.ForeignKey(User, related_name='sent_requests', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Đang chờ'),
        ('accepted', 'Đã chấp nhận'),
        ('rejected', 'Đã từ chối')
    ], default='pending')
    
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Chống spam: A chỉ được gửi cho B 1 lời mời đang chờ
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} gửi {self.receiver.username} - {self.status}"


# --- CLASS TIN NHẮN (Giữ nguyên) ---
class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField(verbose_name="Nội dung")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.content[:20]}"
    
    class Meta:
        ordering = ['timestamp']

class DatingRequest(models.Model):
    sender = models.ForeignKey(User, related_name='dating_requests_sent', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='dating_requests_received', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='pending') # pending, accepted
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver') # Tránh spam gửi nhiều lần