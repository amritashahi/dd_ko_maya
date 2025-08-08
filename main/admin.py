from django.contrib import admin
from .models import (Product, ReliefCombo, ShantiCombo, EssenceCombo, 
                    EssenceComboProduct, EssenceComboService, Service, BankPayment)
# Add at the top of admin.py
from .models import ComboOrder,TrackingUpdate  # Import your model
from django.utils.html import format_html
from django.utils import timezone

class EssenceComboProductInline(admin.TabularInline):
    model = EssenceComboProduct
    extra = 1
    raw_id_fields = ['product']

class EssenceComboServiceInline(admin.TabularInline):
    model = EssenceComboService
    extra = 1
    raw_id_fields = ['service']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'image_preview']
    search_fields = ['name']
    list_filter = ['category']
    
    def display_image(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.get_image_url()}" width="150" />')
        return "No image"
    display_image.short_description = 'Image Preview'

@admin.register(ReliefCombo)
class ReliefComboAdmin(admin.ModelAdmin):
    list_display = ['name', 'massage_option', 'massage_days', 'total_price']
    filter_horizontal = ['products']

@admin.register(ShantiCombo)
class ShantiComboAdmin(admin.ModelAdmin):
    list_display = ['name', 'massage_option', 'massage_days', 'yoga_option', 'total_price']
    filter_horizontal = ['products']

@admin.register(EssenceCombo)
class EssenceComboAdmin(admin.ModelAdmin):
    list_display = ['name', 'total_price', 'created_at', 'services_list']
    inlines = [EssenceComboProductInline, EssenceComboServiceInline]
    
    def services_list(self, obj):
        return ", ".join([s.name for s in obj.services.all()])
    services_list.short_description = 'Services'

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category']
    list_filter = ['category']
    
# admin.py
@admin.register(ComboOrder)
class ComboOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'combo_type', 'total_price', 'payment_method', 'payment_status', 'bank_receipt_link')
    list_filter = ('payment_method', 'payment_status', 'combo_type')
    search_fields = ('user__username', 'id')
    readonly_fields = ('payment_status',)
    actions = ['mark_as_completed']
    actions = ['mark_delivered', 'cancel_order']
    list_display = ('id', 'user', 'delivery_contact_name', 'delivery_contact_phone', 'delivery_status')
    search_fields = ['delivery_contact_phone', 'user__username']
    list_filter = ['delivery_status']

    def bank_receipt_link(self, obj):
        if obj.bank_receipt:
            return format_html('<a href="{}">View Receipt</a>', obj.bank_receipt.url)
        return "-"
    bank_receipt_link.short_description = 'Receipt'

    def mark_as_completed(self, request, queryset):
        queryset.update(payment_status='COMPLETED')
    mark_as_completed.short_description = "Mark selected as completed"
    
    def mark_delivered(self, request, queryset):
        queryset.update(delivery_status='DELIVERED', actual_delivery=timezone.now())
    mark_delivered.short_description = "Mark selected as delivered"
    
    def cancel_order(self, request, queryset):
        queryset.update(delivery_status='CANCELLED')
    cancel_order.short_description = "Cancel selected orders"

    
# admin.py
@admin.register(BankPayment)
class BankPaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'transaction_id', 'verified', 'verification_date')
    actions = ['verify_payments']
    
    def verify_payments(self, request, queryset):
        for payment in queryset:
            payment.verified = True
            payment.verification_date = timezone.now()
            payment.order.payment_status = 'COMPLETED'
            payment.order.save()
            payment.save()
        self.message_user(request, f"{queryset.count()} payments verified")    
        
@admin.register(TrackingUpdate)
class TrackingUpdateAdmin(admin.ModelAdmin):
    list_display = ('order', 'timestamp', 'status', 'location')
    list_filter = ('status',)
    search_fields = ('order__id',)        
