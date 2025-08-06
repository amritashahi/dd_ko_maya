from django import forms
from .models import ComboOrder,UserProfile

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'delivery_address', 'alternate_phone', 'preferred_contact_time']
        widgets = {
            'delivery_address': forms.Textarea(attrs={'rows': 3}),
        }
        
class OrderContactForm(forms.ModelForm):
    class Meta:
        model = ComboOrder
        fields = ['delivery_contact_name', 'delivery_contact_phone', 'special_delivery_notes']
        widgets = {
            'special_delivery_notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Building landmarks, gate codes, etc.'
            }),
        }        