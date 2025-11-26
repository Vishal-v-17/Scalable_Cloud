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

class RoomForm(forms.Form):

    OCCUPANCY_CHOICES = [
        ('Single', 'Single'),
        ('Double', 'Double'),
        ('Triple', 'Triple'),
        ('Quad', 'Quad'),
    ]

    BED_SIZE_CHOICES = [
        ('King', 'King'),
        ('Queen', 'Queen'),
        ('Twin', 'Twin'),
    ]

    LAYOUT_CHOICES = [
        ('Standard', 'Standard'),
        ('Deluxe', 'Deluxe'),
        ('Suite', 'Suite'),
    ]

    occupancy = forms.ChoiceField(
        choices=OCCUPANCY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    bed_size = forms.ChoiceField(
        choices=BED_SIZE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    layout = forms.ChoiceField(
        choices=LAYOUT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    wifi = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    rating = forms.DecimalField(
        max_digits=3,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 5})
    )

    description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4})
    )
    
    image = forms.ImageField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )