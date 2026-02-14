from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(
        label="Nombres",
        max_length=60,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tu nombre"})
    )
    last_name = forms.CharField(
        label="Apellidos",
        max_length=60,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tu apellido"})
    )
    email = forms.EmailField(
        label="Correo",
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "tu@correo.com"})
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].label = "Usuario"
        self.fields["username"].widget.attrs.update({"class": "form-control", "placeholder": "Crea tu usuario"})

        self.fields["password1"].label = "Contraseña"
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Crea una contraseña"})

        self.fields["password2"].label = "Confirmar contraseña"
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Repite la contraseña"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user
