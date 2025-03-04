from django.contrib import admin
from django.urls import path
from .views import AddItem, Dashboard, DeleteItem, EditItem, Index, SignUpView, custom_logout , add_to_cart, get_inventory_data, update_cart , view_cart , checkout
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', Index.as_view(), name='index'),
    path('dashboard/', Dashboard.as_view(), name='dashboard'),
    path('add-item/', AddItem.as_view(), name='add-item'),
    path('edit-item/<int:pk>/', EditItem.as_view(), name='edit-item'),
    path('delete-item/<int:pk>/', DeleteItem.as_view(), name='delete-item'),
    path('signup/', SignUpView.as_view(), name='signup'),  # Solo administradores pueden acceder
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('cart/add/<int:item_id>/', add_to_cart, name='add-to-cart'),
    path('cart/', view_cart, name='view-cart'),
    path('cart/checkout/', checkout, name='checkout'),
    path('cart/update/<int:item_id>/<str:action>/', update_cart, name='update-cart'),
    path('api/inventory/', get_inventory_data, name='get-inventory-data'),

    
]
