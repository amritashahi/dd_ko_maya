from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User


User = get_user_model()

class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.CharField(max_length=255, blank=True)

    category = models.CharField(max_length=50, choices=(
        ('essence', 'Essence'),
        ('relief', 'Relief'), 
        ('shanti', 'Shanti')
    ))
    combo_type = models.CharField(max_length=20, blank=True)  # Add this line
    available = models.BooleanField(default=True)
    def get_image_url(self):
        if self.image:
            return f'/static/products/{self.image}'
        return ''
    
class Service(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    category = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name

class ComboBox(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    class Meta:
        abstract = True

class ReliefCombo(ComboBox):
    products = models.ManyToManyField(Product, related_name='relief_combos')
    massage_option = models.CharField(max_length=50)
    massage_days = models.IntegerField()

class ShantiCombo(ComboBox):
    products = models.ManyToManyField(Product, related_name='shanti_combos')
    massage_option = models.CharField(max_length=50)
    massage_days = models.IntegerField()
    yoga_option = models.CharField(max_length=50)

class EssenceCombo(ComboBox):
    products = models.ManyToManyField(Product, through='EssenceComboProduct')
    services = models.ManyToManyField(Service, through='EssenceComboService')

    def has_massage(self):
        return self.services.filter(category='massage').exists()
        
    def has_yoga(self):
        return self.services.filter(category='yoga').exists()

class EssenceComboProduct(models.Model):
    combo = models.ForeignKey(EssenceCombo, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'main_essencecombo_products'

class EssenceComboService(models.Model):
    combo = models.ForeignKey(EssenceCombo, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    days = models.PositiveIntegerField(default=1)

class ComboOrder(models.Model):
    PAYMENT_METHODS = [
        ('COD', 'Cash on Delivery'),
        ('BANK_NIC', 'NIC Asia Bank Transfer'),
    ]
    
    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ]
    DELIVERY_STATUS = [
        ('PROCESSING', 'Processing'),
        ('PREPARING', 'Preparing Your Items'),
        ('DISPATCHED', 'Dispatched for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled')
    ]
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS,
        default='PROCESSING'
    )
    estimated_delivery = models.DateField(null=True, blank=True)
    actual_delivery = models.DateField(null=True, blank=True)
    def overall_status(self):
        if self.delivery_status == 'DELIVERED':
            return "Delivered"
        elif self.payment_status == 'FAILED':
            return "Payment Failed"
        elif self.delivery_status == 'CANCELLED':
            return "Cancelled"
        else:
            return "In Progress"
    
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    payment_id = models.CharField(max_length=100, blank=True)  # For gateway transaction IDs
    
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='COD'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS,
        default='PENDING'
    )
    bank_receipt = models.ImageField(upload_to='receipts/', blank=True)  # For bank transfers
    is_verified = models.BooleanField(default=False)  # For admin verification
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    combo_type = models.CharField(
        max_length=20,
        default='Essence'
    )

    def __str__(self):
        return f"Order #{self.id} - {self.get_payment_method_display()}"
    
    delivery_contact_name = models.CharField(max_length=100, blank=True)
    delivery_contact_phone = models.CharField(max_length=15 ,blank=True, null=True)
    special_delivery_notes = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        if not self.delivery_contact_name and self.user:
            self.delivery_contact_name = self.user.get_full_name()
        super().save(*args, **kwargs)
class OrderItem(models.Model):
    order = models.ForeignKey(ComboOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL)
    service_type = models.CharField(max_length=20, blank=True, choices=[
        ('massage', 'Massage'),
        ('yoga', 'Yoga')
    ])
    quantity = models.PositiveIntegerField(default=1)
    days = models.PositiveIntegerField(null=True, blank=True)
    duration = models.CharField(max_length=50, default='0.00')  # Added from migration
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Added from migration
    
    def save(self, *args, **kwargs):
        # Auto-calculate price if not set
        if not self.price or self.price == 0:
            if self.product:
                self.price = self.product.price * self.quantity
            elif self.service:
                self.price = self.service.price * (self.days or 1)
        super().save(*args, **kwargs)
        
class BankPayment(models.Model):
    order = models.OneToOneField('ComboOrder', on_delete=models.CASCADE)
    receipt = models.FileField(upload_to='verified_receipts/')
    transaction_id = models.CharField(max_length=100)
    verification_data = models.JSONField(null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id}"
    
class OrderTracking(models.Model):
    order = models.ForeignKey(ComboOrder, on_delete=models.CASCADE)
    update_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=100)
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)   
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    delivery_address = models.TextField(blank=True)
    alternate_phone = models.CharField(max_length=15, blank=True)
    preferred_contact_time = models.CharField(
        max_length=20,
        choices=[
            ('ANYTIME', 'Anytime'),
            ('MORNING', 'Morning (9AM-12PM)'),
            ('AFTERNOON', 'Afternoon (12PM-5PM)'),
            ('EVENING', 'Evening (5PM-9PM)')
        ],
        default='ANYTIME'
    )

    def __str__(self):
        return f"{self.user.username}'s profile"     
    
class TrackingUpdate(models.Model):
    order = models.ForeignKey(ComboOrder, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=100, choices=[
        ('PROCESSING', 'Order Processing'),
        ('SHIPPED', 'Shipped from Warehouse'),
        ('IN_TRANSIT', 'In Transit'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
    ])
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']    
