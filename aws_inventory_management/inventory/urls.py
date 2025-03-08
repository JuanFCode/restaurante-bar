import os
from django.contrib import admin
from django.urls import path
from .views import (
    AddItem, Dashboard, DeleteItem, EditItem, Index, OrderHistoryView, PendingOrdersView, 
    SignUpView, custom_logout, add_to_cart, get_inventory_data, print_order, update_cart, update_payment_method, 
    view_cart, checkout
)
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('', Index.as_view(), name='index'),
    path('dashboard/', Dashboard.as_view(), name='dashboard'),
    path('add-item/', AddItem.as_view(), name='add-item'),
    path('edit-item/<int:pk>/', EditItem.as_view(), name='edit-item'),
    path('delete-item/<int:pk>/', DeleteItem.as_view(), name='delete-item'),
    path('signup/', SignUpView.as_view(), name='signup'),  
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', custom_logout, name='logout'),
    
    # Rutas del carrito
    path('cart/add/<int:item_id>/', add_to_cart, name='add-to-cart'),
    path('cart/', view_cart, name='view-cart'),
    path('cart/checkout/', checkout, name='checkout'),  # ✅ Solo una vez
    path('cart/update/<int:item_id>/<str:action>/', update_cart, name='update-cart'),

    # API de inventario
    path('api/inventory/', get_inventory_data, name='get-inventory-data'),

    # Pedidos pendientes
    path('orders/pending/', PendingOrdersView.as_view(), name='pending-orders'),
    path('orders/pending/<int:order_id>/', PendingOrdersView.as_view(), name='pending-orders'),



    # Historial de pedidos
    path('orders/history/', OrderHistoryView.as_view(), name='order-history'),

    #Impresión de pedidos
    path('print-order/<int:order_id>/', print_order, name='print-order'),


    path('orders/update-payment/<int:order_id>/', update_payment_method, name='update-payment-method'),


]

# 🔹 Servir archivos estáticos en modo desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=os.path.join(os.path.dirname(settings.BASE_DIR), 'static'))

