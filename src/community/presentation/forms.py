from django import forms
from django.contrib.auth import get_user_model

from community.infrastructure.container import get_community_service
from community.infrastructure.persistence.models import Community


class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ["name", "description", "image", "is_private"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "ชื่อกลุ่ม"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "รายละเอียดกลุ่ม",
                }
            ),
            "image": forms.FileInput(attrs={"class": "form-control"}),
            "is_private": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class JoinByInviteCodeForm(forms.Form):
    invite_code = forms.CharField(
        max_length=8,
        label="Invite Code",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter 8-character invite code",
            }
        ),
    )


class TransferOwnershipForm(forms.Form):
    """ฟอร์มเลือกสมาชิกที่จะโอนสิทธิ์ความเป็นเจ้าของกลุ่มให้"""

    new_owner = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        label="เลือกเจ้าของกลุ่มคนใหม่",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, community=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if community and current_user:
            self.fields[
                "new_owner"
            ].queryset = get_community_service().transfer_candidates(
                community, current_user
            )
