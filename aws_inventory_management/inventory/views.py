from email.headerregistry import Group
import json
from django.shortcuts import render, redirect , get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View, CreateView, UpdateView, DeleteView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from aws_inventory_management.settings import LOW_QUANTITY
from .models import Category, InventoryItem , CartItem, Order, OrderItem 
from .forms import InventoryItemForm, UserRegisterForm
from django.core.exceptions import ObjectDoesNotExist  # Importar la excepción correcta
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import tempfile
import cups
# Create your views here.


# Vista de inicio
class Index(TemplateView):
    template_name = 'inventory/index.html'


# Mixin para restringir acceso a Administradores y Supervisores
class AdminOrSupervisorRequiredMixin(UserPassesTestMixin):
    """Solo permite acceso a Administradores y Supervisores"""
    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Supervisor']).exists()


# Vista para empleados (solo pueden ver productos)
class EmployeeRestrictedView(LoginRequiredMixin, View):
    """Restringe a empleados solo a ver los artículos"""
    def get(self, request):
        if request.user.groups.filter(name='Empleado').exists():
            items = InventoryItem.objects.all()
        else:
            items = InventoryItem.objects.filter(user=request.user)

        return render(request, 'inventory/dashboard.html', {'items': items})

	
# Vista del Dashboard
class Dashboard(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.groups.filter(name="Empleado").exists():
            items = InventoryItem.objects.filter(assigned_group__name="Empleado")
        else:
            items = InventoryItem.objects.all()

        categories = Category.objects.all()  # 🔹 Agregar consulta de categorías

        low_inventory = items.filter(quantity__lte=LOW_QUANTITY)
        if low_inventory.exists():
            messages.error(request, f"{low_inventory.count()} artículo(s) tienen baja cantidad")

        low_inventory_ids = low_inventory.values_list("id", flat=True)

        # Pasar permisos al contexto
        is_admin = request.user.is_superuser or request.user.groups.filter(name="Administrador").exists()
        is_supervisor = request.user.groups.filter(name="Supervisor").exists()

        return render(
            request, 
            "inventory/dashboard.html", 
            {
                "items": items, 
                "categories": categories,  # 🔹 Pasar categorías al template
                "low_inventory_ids": low_inventory_ids, 
                "is_admin": is_admin, 
                "is_supervisor": is_supervisor
            }
        )



# Vista de registro de usuarios
class SignUpView(View):
	def get(self, request):
		form = UserRegisterForm()
		return render(request, 'inventory/signup.html', {'form': form})

	def post(self, request):
		form = UserRegisterForm(request.POST)

		if form.is_valid():
			form.save()
			user = authenticate(
				username=form.cleaned_data['username'],
				password=form.cleaned_data['password1']
			)

			login(request, user)
			return redirect('index')

		return render(request, 'inventory/signup.html', {'form': form})
	

# Vista de logout personalizado
def custom_logout(request):
    logout(request)
    request.session.flush()
    return render(request, 'inventory/logout.html')  # Renderiza la plantilla de logout



# Vista para agregar artículos (Solo Admins y Supervisores)

class AddItem(LoginRequiredMixin, AdminOrSupervisorRequiredMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('dashboard')

    def get_form_kwargs(self):
        """Pasa el usuario al formulario para controlar los permisos de edición."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        print("Vista AddItem cargada")  # <-- Esto imprimirá cuando la página de agregar producto se carga
        return kwargs

    def form_valid(self, form):
        print("Formulario válido, agregando producto...")  # <-- Esto imprimirá si el formulario es válido
        form.instance.added_by = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        print("Formulario inválido, errores:", form.errors)  # <-- Esto imprimirá si el formulario es inválido
        messages.error(self.request, "Hubo un error al agregar el producto. Revisa los datos ingresados.")
        return self.render_to_response(self.get_context_data(form=form))





# Vista para editar artículos (Solo Admins y Supervisores)
class EditItem(LoginRequiredMixin, AdminOrSupervisorRequiredMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('dashboard')



# Vista para eliminar artículos (Solo Admins y Supervisores)
class DeleteItem(LoginRequiredMixin, AdminOrSupervisorRequiredMixin, DeleteView):
    model = InventoryItem
    template_name = 'inventory/delete_item.html'
    success_url = reverse_lazy('dashboard')
    context_object_name = 'item'




def add_to_cart(request, item_id):
    """ Agrega un producto al carrito y reduce stock """
    if request.user.is_authenticated and request.method == "POST":
        item = get_object_or_404(InventoryItem, id=item_id)

        # Verificar que hay stock disponible
        if item.quantity > 0:
            cart_item, created = CartItem.objects.get_or_create(user=request.user, item=item)

            if not created:
                if cart_item.quantity < item.quantity:  # Evita agregar más de lo que hay en stock
                    cart_item.quantity += 1
                else:
                    return JsonResponse({'error': 'Stock insuficiente'}, status=400)
            else:
                cart_item.quantity = 1  # Si es la primera vez, inicia en 1
            
            cart_item.save()

            # Reducir el stock en el inventario
            item.quantity -= 1
            item.save()

            # Obtener el total de productos en el carrito
            cart_count = CartItem.objects.filter(user=request.user).count()

            return JsonResponse({
                'message': 'Producto agregado al carrito',
                'cart_count': cart_count
            })

        return JsonResponse({'error': 'Stock insuficiente'}, status=400)

    return JsonResponse({'error': 'No autorizado'}, status=403)




def view_cart(request):
    """ Retorna el contenido del carrito en JSON si es AJAX, o renderiza la página normalmente """
    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(user=request.user)
        cart_data = [{
            "id": item.id,
            "name": item.item.name,
            "quantity": item.quantity,
            "subtotal": float(item.subtotal())
        } for item in cart_items]

        total = sum([item.subtotal() for item in cart_items])

        # 📌 Si la petición es AJAX, devolvemos JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'cart_items': cart_data, 'total': total})

        # 📌 Si es una petición normal, renderizamos la página HTML
        return render(request, 'inventory/cart.html', {'cart_items': cart_items, 'total': total})

    return JsonResponse({'error': 'Usuario no autenticado'}, status=403)



def update_cart(request, item_id, action):
    """ Aumenta, disminuye o elimina productos del carrito y ajusta el stock """
    if request.user.is_authenticated and request.method == "POST":
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
        item = cart_item.item  # Producto en inventario

        if action == "add":
            if item.quantity > 0:  # Solo agrega si hay stock
                cart_item.quantity += 1
                cart_item.save()
                item.quantity -= 1  # Reduce el stock
                item.save()
            else:
                return JsonResponse({'error': 'Stock insuficiente'}, status=400)

        elif action == "remove":
            cart_item.quantity -= 1
            if cart_item.quantity == 0:
                cart_item.delete()
            else:
                cart_item.save()
            item.quantity += 1  # Devolver al stock
            item.save()

        elif action == "delete":
            item.quantity += cart_item.quantity  # Restaurar el stock antes de eliminar
            item.save()
            cart_item.delete()

        return JsonResponse({
            'quantity': cart_item.quantity if cart_item.quantity > 0 else 0,
            'cart_count': CartItem.objects.filter(user=request.user).count()
        })

    return JsonResponse({'error': 'No autorizado'}, status=403)






@login_required
def checkout(request):
    """ Finaliza la compra y guarda los productos correctamente en la orden """
    if request.method != "POST":  
        return redirect("view-cart")

    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.error(request, "No hay productos en el carrito.")
        return redirect("view-cart")

    total = sum(item.subtotal() for item in cart_items)
    payment_method = request.POST.get("payment_method")

    if not payment_method:
        messages.error(request, "Debes seleccionar una forma de pago.")
        return redirect("view-cart")

    # 🔹 CREAR LA ORDEN
    order = Order.objects.create(user=request.user, total=total, payment_method=payment_method)

    # 🔹 ASOCIAR LOS PRODUCTOS USANDO OrderItem
    for cart_item in cart_items:
        OrderItem.objects.create(order=order, item=cart_item.item, quantity=cart_item.quantity)  # ✅ Ahora se guardan correctamente

    order.save()

    # 🔹 ELIMINAR EL CARRITO DESPUÉS DE GUARDAR LOS PRODUCTOS EN LA ORDEN
    cart_items.delete()

    messages.success(request, "¡Compra finalizada con éxito! 🛒")
    return redirect("dashboard")  # 📌 Redirige al menú de comidas






def get_inventory_data(request):
    """ Devuelve el inventario en formato JSON para actualizar la tabla dinámicamente """
    if request.user.is_authenticated:
        items = InventoryItem.objects.all()
        inventory_data = [{
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "price": float(item.price)
        } for item in items]

        return JsonResponse({"inventory": inventory_data})

    return JsonResponse({"error": "Usuario no autenticado"}, status=403)


class PendingOrdersView(LoginRequiredMixin, View):
    def get(self, request):
        orders = Order.objects.filter(status__in=["Pendiente", "Pagado"]).order_by("-created_at")
        return render(request, "inventory/pending_orders.html", {"orders": orders})

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        action = request.POST.get("action")

        if action == "mark_paid":
            order.status = "Pagado"
        elif action == "mark_printed":
            order.status = "Impreso"

        order.save()
        return redirect("pending-orders")



class OrderHistoryView(LoginRequiredMixin, View):
    """ Muestra todas las órdenes registradas (histórico) """
    def get(self, request):
        orders = Order.objects.all().order_by("-created_at")  # 📌 Ordenados por fecha más reciente
        return render(request, "inventory/order_history.html", {"orders": orders})


def print_order(request, order_id):
    """Genera e imprime un ticket para un pedido específico"""
    order = get_object_or_404(Order, id=order_id)

    # 🔹 Acceder correctamente a los productos de la orden usando OrderItem
    order_items = OrderItem.objects.filter(order=order)

    if not order_items.exists():
        return JsonResponse({"error": "⚠️ No hay productos en este pedido"}, status=400)

    # Configurar la conexión con la impresora CUPS
    conn = cups.Connection()
    printer_name = "JAL-808R"

    # Comandos ESC/POS
    ESC = "\x1B"
    GS = "\x1D"

    # Encabezado del ticket
    ticket_text = f"""
{ESC}@  # Reset printer
{ESC}\x21\x10     NAPOLES BAR {ESC}\x21\x00
{ESC}\x45\x01NIT: 123456789{ESC}\x45\x00
{ESC}\x21\x01Calle 123, Ciudad
Tel: 555-5555
-----------------------------
CANT  DESCRIPCIÓN       PRECIO
-----------------------------
"""

    # 🔹 Imprimir correctamente los productos
    for order_item in order_items:
        cantidad = str(order_item.quantity).rjust(3)  # Alinear cantidad a la derecha
        nombre_producto = order_item.item.name[:15].ljust(30)  # Nombre ajustado a 15 caracteres
        precio = f"${order_item.item.price:.2f}".rjust(7)  # Precio alineado

        ticket_text += f"{cantidad}  {nombre_producto} {precio}\n"

    # Totales y mensaje de cierre
    ticket_text += f"""
-----------------------------
TOTAL:                 ${order.total:.2f}
-----------------------------
{ESC}\x21\x01GRACIAS POR SU VISITA!
{GS}\x56\x41  # Corte de papel
"""

    # Guardar el ticket en un archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as temp_file:
        temp_file.write(ticket_text)
        temp_file_path = temp_file.name

    # Enviar el archivo a la impresora
    try:
        conn.printFile(printer_name, temp_file_path, "Factura Restaurante", {})
        order.status = "Impreso"  # Marcar como impreso
        order.save()
        return JsonResponse({"message": "Factura enviada a la impresora"})
    except Exception as e:
        return JsonResponse({"error": f"Error al imprimir: {str(e)}"}, status=500)


def update_payment_method(request, order_id):
    """Actualiza la forma de pago de un pedido"""
    if request.method == "POST" and request.user.is_authenticated:
        order = get_object_or_404(Order, id=order_id)
        data = json.loads(request.body)
        new_payment_method = data.get("payment_method")

        if new_payment_method in ["Efectivo", "Tarjeta", "Transferencia"]:
            order.payment_method = new_payment_method
            order.save()
            return JsonResponse({"success": True})
        return JsonResponse({"error": "Forma de pago no válida"}, status=400)

    return JsonResponse({"error": "No autorizado"}, status=403)