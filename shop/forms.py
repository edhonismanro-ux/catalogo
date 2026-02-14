from django import forms
from .models import Order, Address


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["full_name", "whatsapp", "address", "reference", "notes"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tu nombre completo"}),
            "whatsapp": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: 944739301"}),
            "address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dirección (opcional)"}),
            "reference": forms.TextInput(attrs={"class": "form-control", "placeholder": "Referencia (opcional)"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Notas (opcional)"}),
        }


class ReceiptUploadForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["receipt_image"]
        widgets = {
            "receipt_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ["label", "full_name", "whatsapp", "address", "reference", "notes", "is_default"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
