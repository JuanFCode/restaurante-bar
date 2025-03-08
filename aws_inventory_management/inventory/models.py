from django.db import models
from django.contrib.auth.models import User, Group

class InventoryItem(models.Model):
    name = models.CharField(max_length=200)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)  
    assigned_group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        permissions = (
            ("manage_inventory", "Puede administrar el inventario"),
        )

    def __str__(self):
        return f"{self.name} - {self.price}"

class Category(models.Model):
    name = models.CharField(max_length=200)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name
    

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey('InventoryItem', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def subtotal(self):
        return self.quantity * self.item.price  

    def __str__(self):
        return f"{self.quantity} x {self.item.name} - {self.user.username}"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, 
        choices=[("Pendiente", "Pendiente"), ("Pagado", "Pagado"), ("Impreso", "Impreso")], 
        default="Pendiente"
    )
    payment_method = models.CharField(
        max_length=50,
        choices=[("Efectivo", "Efectivo"), ("Tarjeta", "Tarjeta"), ("Transferencia", "Transferencia")],
        default="Efectivo"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ Relación ManyToMany con InventoryItem usando OrderItem
    items = models.ManyToManyField(InventoryItem, through="OrderItem")  

    def __str__(self):
        return f"Orden #{self.id} - {self.user.username} - {self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.item.name} (Orden #{self.order.id})"
