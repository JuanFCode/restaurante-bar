from email.headerregistry import Group
from django.shortcuts import render, redirect , get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View, CreateView, UpdateView, DeleteView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from aws_inventory_management.settings import LOW_QUANTITY
from .models import Category, InventoryItem , CartItem
from .forms import InventoryItemForm, UserRegisterForm
from django.core.exceptions import ObjectDoesNotExist  # Importar la excepción correcta
from django.http import JsonResponse


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
            {"items": items, "low_inventory_ids": low_inventory_ids, "is_admin": is_admin, "is_supervisor": is_supervisor}
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



def checkout(request):
    """ Finaliza la compra y vacía el carrito """
    if request.user.is_authenticated:
        CartItem.objects.filter(user=request.user).delete()
        return JsonResponse({'message': 'Compra finalizada'})
    
    return JsonResponse({'error': 'Debes iniciar sesión para finalizar la compra'}, status=403)





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