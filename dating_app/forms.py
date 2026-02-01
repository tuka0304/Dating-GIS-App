from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class RegisterForm(UserCreationForm):
    # --- THÊM CÁC TRƯỜNG MỚI VÀO ĐÂY ---
    full_name = forms.CharField(label="Họ và tên", max_length=100)
    
    gender = forms.ChoiceField(
        label="Giới tính", 
        choices=[('Nam', 'Nam'), ('Nữ', 'Nữ'), ('Khác', 'Khác')]
    )
    
    # type='date' để hiện cái lịch chọn ngày
    birth_date = forms.DateField(
        label="Ngày sinh", 
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    email = forms.EmailField(required=False, label="Email")
    
    class Meta:
        model = User
        fields = ['username', 'email'] # Các trường thuộc bảng User gốc



# ... (Giữ nguyên các import và class RegisterForm cũ) ...

from .models import UserProfile # Đảm bảo đã import model này

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['full_name', 'gender', 'birth_date', 'province', 'address', 
                  'bio', 'hobbies', 'music_playlist', 'avatar', 'cover_photo']
        
        # Thêm style cho các ô nhập liệu đẹp như giao diện Dark Mode
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nhập tên hiển thị'}),
            'address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Địa chỉ cụ thể'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Viết gì đó về bạn...'}),
            'hobbies': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Ví dụ: Ăn, Ngủ, Code...'}),
            'music_playlist': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Mỗi bài hát một dòng'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'province': forms.Select(attrs={'class': 'form-input'}),
        }
        labels = {
            'cover_photo': 'Ảnh nổi bật / Ảnh bìa',
            'bio': 'Status / Giới thiệu',
            'music_playlist': 'Playlist nhạc (Tên bài hát)'
        }  