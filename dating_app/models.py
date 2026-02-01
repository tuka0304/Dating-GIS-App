from django.db import models
from django.contrib.auth.models import User
import datetime

# DANH SÁCH 34 TỈNH THÀNH (THEO QUY HOẠCH SÁP NHẬP)
PROVINCE_CHOICES = [
    # --- KHU VỰC PHÍA BẮC ---
    ('HNI', 'Thành phố Hà Nội'),
    ('HPH', 'Thành phố Hải Phòng'), # Hải Dương + Hải Phòng
    ('TQU', 'Tỉnh Tuyên Quang'),    # Tuyên Quang + Hà Giang
    ('LCA', 'Tỉnh Lào Cai'),        # Lào Cai + Yên Bái
    ('TNG', 'Tỉnh Thái Nguyên'),    # Bắc Kạn + Thái Nguyên
    ('PTH', 'Tỉnh Phú Thọ'),        # Vĩnh Phúc + Phú Thọ + Hoà Bình
    ('BNI', 'Tỉnh Bắc Ninh'),       # Bắc Ninh + Bắc Giang
    ('HYE', 'Tỉnh Hưng Yên'),       # Hưng Yên + Thái Bình
    ('NBI', 'Tỉnh Ninh Bình'),      # Hà Nam + Ninh Bình + Nam Định
    ('QNI', 'Tỉnh Quảng Ninh'),
    ('LSO', 'Tỉnh Lạng Sơn'),
    ('CBA', 'Tỉnh Cao Bằng'),
    ('LCH', 'Tỉnh Lai Châu'),
    ('DBI', 'Tỉnh Điện Biên'),
    ('SLA', 'Tỉnh Sơn La'),

    # --- KHU VỰC MIỀN TRUNG ---
    ('THA', 'Tỉnh Thanh Hoá'),
    ('NAN', 'Tỉnh Nghệ An'),
    ('HTI', 'Tỉnh Hà Tĩnh'),
    ('HUE', 'Thành phố Huế'),
    ('QTR', 'Tỉnh Quảng Trị'),      # Quảng Bình + Quảng Trị
    ('DNG', 'Thành phố Đà Nẵng'),   # Quảng Nam + Đà Nẵng
    ('QNG', 'Tỉnh Quảng Ngãi'),     # Kon Tum + Quảng Ngãi
    ('GLA', 'Tỉnh Gia Lai'),        # Gia Lai + Bình Định
    ('KHO', 'Tỉnh Khánh Hoà'),      # Ninh Thuận + Khánh Hoà
    ('DLA', 'Tỉnh Đắk Lắk'),        # Đắk Lắk + Phú Yên
    ('LDO', 'Tỉnh Lâm Đồng'),       # Lâm Đồng + Đắk Nông + Bình Thuận

    # --- KHU VỰC PHÍA NAM ---
    ('HCM', 'Thành phố Hồ Chí Minh'), # BRVT + Bình Dương + TP.HCM
    ('DNI', 'Tỉnh Đồng Nai'),       # Đồng Nai + Bình Phước
    ('TNI', 'Tỉnh Tây Ninh'),       # Tây Ninh + Long An
    ('CTO', 'Thành phố Cần Thơ'),   # Cần Thơ + Sóc Trăng + Hậu Giang
    ('VLG', 'Tỉnh Vĩnh Long'),      # Bến Tre + Vĩnh Long + Trà Vinh
    ('DTH', 'Tỉnh Đồng Tháp'),      # Tiền Giang + Đồng Tháp
    ('AGI', 'Tỉnh An Giang'),       # An Giang + Kiên Giang
    ('CMU', 'Tỉnh Cà Mau')          # Bạc Liêu + Cà Mau
]

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Thông tin cơ bản
    full_name = models.CharField(max_length=100, verbose_name="Họ tên")
    gender = models.CharField(max_length=10, choices=[('Nam', 'Nam'), ('Nữ', 'Nữ'), ('Khác', 'Khác')], default='Nam')
    birth_date = models.DateField(default=datetime.date(2000, 1, 1))
    
    # --- PHẦN GIS ---
    # Mã tỉnh 3 ký tự
    province = models.CharField(max_length=10, choices=PROVINCE_CHOICES, default='HCM') 
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(default=10.8231, verbose_name="Vĩ độ")
    longitude = models.FloatField(default=106.6297, verbose_name="Kinh độ")
    bio = models.TextField(blank=True, verbose_name="Giới thiệu/Status")    

    # Thông tin phụ
    music_playlist = models.TextField(blank=True, help_text="Mỗi bài hát 1 dòng")
    hobbies = models.TextField(blank=True, help_text="Các sở thích cách nhau dấu phẩy")
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True)
    cover_photo = models.ImageField(upload_to='covers/', default='covers/default.jpg', blank=True)

    def __str__(self):
        return self.full_name
    
    def get_age(self):
        return datetime.date.today().year - self.birth_date.year

# --- CLASS TIN NHẮN ---
class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField(verbose_name="Nội dung")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.content[:20]}"
    
    class Meta:
        ordering = ['timestamp']