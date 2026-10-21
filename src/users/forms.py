
from django import forms
from .models import User


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "bio", "profile_image"]
        widgets = {
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

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if not full_name:
            raise forms.ValidationError("กรุณากรอกชื่อที่แสดง")
        return full_name
