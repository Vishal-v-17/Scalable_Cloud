from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from .models import User, Booking, RoomType

class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirm', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['room', 'check_in', 'check_out']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}),
            'check_out': forms.DateInput(attrs={'type': 'date'}),
        }

class RoomTypeForm(forms.ModelForm):
    images = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'multiple': True}),
        required=False,
        label="Upload Room Images"
    )
    
    class Meta:
        model = RoomType
        fields = [ 'occupancy', 'bed_size', 'layout', 'wifi', 'price', 'rating', 'description' ]

        widgets = {
            'occupancy': forms.Select(attrs={'class': 'form-select'}),
            'bed_size': forms.Select(attrs={'class': 'form-select'}),
            'layout': forms.Select(attrs={'class': 'form-select'}),
            'wifi': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter price per night'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
            # 'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'occupancy': 'Occupancy',
            'bed_size': 'Bed Size',
            'layout': 'Layout Type',
            'wifi': 'Wi-Fi Available',
            'price': 'Price per Night',
            'rating': 'Rating (1–5)',
            'description': 'Description',
            # 'image' : 'Images'
            }