from django import forms
from .models import Booking, RoomType

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