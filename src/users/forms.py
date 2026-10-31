
from django import forms
from .models import User


class ProfileCoverForm(forms.Form):
    profile_cover = forms.ImageField()

    def clean_profile_cover(self):
        image = self.cleaned_data["profile_cover"]
        if image.size > 10 * 1024 * 1024:
            raise forms.ValidationError("รูปภาพปกต้องมีขนาดไม่เกิน 10 MB")
        return image


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "full_name", "bio", "profile_image"]
        widgets = {
            "username": forms.TextInput(attrs={
                "placeholder": "ชื่อผู้ใช้",
                "maxlength": "150",
                "autocomplete": "username",
            }),
            "full_name": forms.TextInput(attrs={
                "placeholder": "ชื่อที่แสดง",
                "maxlength": "100",
            }),
            "bio": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "แนะนำตัวเอง",
            }),
            "profile_image": forms.ClearableFileInput(attrs={
                "accept": "image/*",
            }),
        }

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exclude(
            pk=self.instance.pk
        ).exists():
            raise forms.ValidationError("ชื่อผู้ใช้นี้ถูกใช้แล้ว")
        return username

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if not full_name:
            raise forms.ValidationError("กรุณากรอกชื่อที่แสดง")
        return full_name
