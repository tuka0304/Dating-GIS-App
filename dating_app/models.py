from django.db import models
from django.contrib.auth.models import User
import datetime

# Danh sách chọn Tỉnh
PROVINCE_CHOICES = [('HNI', 'Hà Nội'), ('HCM', 'TP. Hồ Chí Minh'), ('DNG', 'Đà Nẵng')]

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Thông tin cơ bản
    full_name = models.CharField(max_length=100, verbose_name="Họ tên")
    gender = models.CharField(max_length=10, choices=[('Nam', 'Nam'), ('Nữ', 'Nữ'), ('Khác', 'Khác')], default='Nam')
    birth_date = models.DateField(default=datetime.date(2000, 1, 1))
    
    # --- PHẦN GIS (Lưu Vector Point dạng số thực) ---
    province = models.CharField(max_length=3, choices=PROVINCE_CHOICES, default='HCM')
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(default=10.8231, verbose_name="Vĩ độ")
    longitude = models.FloatField(default=106.6297, verbose_name="Kinh độ")

    # Thông tin phụ (Discord Style)
    music_playlist = models.TextField(blank=True, help_text="Mỗi bài hát 1 dòng")
    hobbies = models.TextField(blank=True, help_text="Các sở thích cách nhau dấu phẩy")
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True)
    cover_photo = models.ImageField(upload_to='covers/', default='covers/default.jpg', blank=True)

    def __str__(self):
        return self.full_name
    
    def get_age(self):
        return datetime.date.today().year - self.birth_date.year