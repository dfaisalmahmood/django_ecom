from django import forms
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

PAYMENT_CHOICES = (
    ('S', 'Stripe'),
    ('P', 'PayPal')
)


class CheckoutForm(forms.Form):
    street_address = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': '1234 Main St',
        'class': 'form-control'
    }))
    apartment_address = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Apartment or suite',
        'class': 'form-control'
    }), required=False)
    country = CountryField(blank_label="Choose...").formfield(widget=CountrySelectWidget(attrs={
        'class': 'custom-select d-block w-100'
    }))
    city = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'City or state',
        'class': 'form-control'
    }))
    post_code = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Post or zip code',
        'class': 'form-control'
    }))

    same_shipping_address = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'custom-control-input'
    }))
    save_info = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'custom-control-input'
    }))
    payment_option = forms.ChoiceField(
        widget=forms.RadioSelect(), choices=PAYMENT_CHOICES)
