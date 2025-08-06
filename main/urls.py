from django.urls import path
from . import views
from main.views import create_test_order
from main.views import order_confirmation
urlpatterns = [
    path('', views.home, name='home'),
    path('essence-combo/', views.essence_combo_view, name='essence_combo'),
    path('relief-combo/', views.relief_combo_view, name='relief_combo'),
    path('shanti-combo/', views.shanti_combo_view, name='shanti_combo'),
    path('create-test-order/', create_test_order, name='create_test_order'),
   path('payment-success/', views.payment_success, name='payment_success'),
   path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
   path('bank-transfer/<int:order_id>/', views.bank_transfer_instructions, name='bank_transfer_instructions'),
    path('upload-receipt/<int:order_id>/', views.upload_receipt, name='upload_receipt'),
    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/track/', views.track_order, name='track_order'),
   
]
