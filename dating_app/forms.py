from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile

class RegisterForm(UserCreationForm):
    full_name = forms.CharField(label="Họ và tên", max_length=100)
    gender = forms.ChoiceField(label="Giới tính", choices=[('Nam', 'Nam'), ('Nữ', 'Nữ'), ('Khác', 'Khác')])
    birth_date = forms.DateField(label="Ngày sinh", widget=forms.DateInput(attrs={'type': 'date'}))
    email = forms.EmailField(required=False, label="Email")
    
    class Meta:
        model = User
        fields = ['username', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        
        # CHÚ Ý: fields, widgets, labels phải lùi vào 1 Tab so với chữ 'class Meta:'
        fields = ['full_name', 'gender', 'birth_date', 'marital_status', 'province', 'address', 
                  'bio', 'hobbies', 'music_playlist', 'avatar', 'cover_photo']
        
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nhập tên hiển thị'}),
            'address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Địa chỉ cụ thể'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Viết gì đó về bạn...'}),
            'hobbies': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Ví dụ: Ăn, Ngủ, Code...'}),
            'music_playlist': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Mỗi bài hát một dòng'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'province': forms.Select(attrs={'class': 'form-input'}),
            'marital_status': forms.Select(attrs={'class': 'form-input'}),
        }
        
        labels = {
            'cover_photo': 'Ảnh nổi bật / Ảnh bìa',
            'bio': 'Status / Giới thiệu',
            'music_playlist': 'Playlist nhạc (Tên bài hát)',
            'marital_status': 'Tình trạng quan hệ'
        }
    