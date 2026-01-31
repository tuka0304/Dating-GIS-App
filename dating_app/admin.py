from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'province', 'gender', 'get_age')
    search_fields = ('full_name', 'province')
    list_filter = ('province', 'gender')