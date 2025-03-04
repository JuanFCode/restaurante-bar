from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from inventory.models import Category, InventoryItem
from django.contrib.auth.models import Group

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User        
        fields = ('username', 'email', 'password1', 'password2')


class InventoryItemForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), initial=0)
    assigned_group = forms.ModelChoiceField(
        queryset=Group.objects.filter(name="Empleado"),  # Solo grupos de empleados
        required=False,
        label="Grupo asignado"
    )

    class Meta:
        model = InventoryItem
        fields = ['name', 'quantity', 'price', 'category', 'assigned_group']
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Capturar el usuario actual
        super().__init__(*args, **kwargs)
        
        # Solo administradores y supervisores pueden ver y asignar grupos
        if user and not (user.is_superuser or user.groups.filter(name="Administrador").exists() or user.groups.filter(name="Supervisor").exists()):
            del self.fields['assigned_group']  # Ocultar para empleado
            
