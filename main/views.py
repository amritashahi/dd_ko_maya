from django.shortcuts import render, redirect
from .models import Product, ComboOrder
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from django.db.models import Q
from .models import  OrderItem, BankPayment
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render, get_object_or_404
from django.db import transaction  
from django.urls import reverse
from django.core.mail import send_mail  # For sending emails
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse, Http404
from django.conf import settings
from .payment_utils import send_order_email
import os
import re
from .models import Service # Import all required models
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
import pytesseract  # For OCR (optional)
import logging
from .models import ComboOrder, TrackingUpdate
from .forms import OrderContactForm, UserProfileForm 




User = get_user_model()

def home(request):
    return render(request, 'main/home.html')  

#

def order_confirmation(request, order_id):
    order = get_object_or_404(ComboOrder, id=order_id)
    
    context = {
        'order': order,
        'items': order.items.all(),
        'is_bank_pending': order.payment_method == 'BANK_NIC' and order.payment_status != 'COMPLETED'
    }
    
    return render(request, 'main/order_confirmation.html', context)

def create_test_order(request):
    # Get or create a test user
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'password': 'testpass123'}
    )
    
    # Create the order
    order = ComboOrder.objects.create(
        user=user,
        total_price=Decimal('0.00'),
        combo_type='Essence'
    )
    
    return render(request, 'main/home.html')
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            next_page = request.GET.get('next', 'home')  # Get next parameter or default to 'home'
            return redirect(next_page)
        else:
            # Print form errors to console for debugging
            print("Form errors:", form.errors)
            messages.error(request, "Please correct the errors below")
    else:
        form = UserCreationForm()
    
    return render(request, 'auth/signup.html', {
        'form': form,
        'next': request.GET.get('next', '')  # Pass next parameter to template
    })

def custom_login(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password")
    else:
        form = AuthenticationForm()
    
    return render(request, 'main/templates/auth/login.html', {'form': form})

def handle_combo_order(request, combo_type):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Create order
                order = ComboOrder.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    total=float(request.POST.get('total', 0)),
                    combo_type=combo_type
                )
                
                # Process products
                for key, value in request.POST.items():
                    if key.startswith('product_') and int(value) > 0:
                        OrderItem.objects.create(
                            combo_order=order,  # Match model field name
                            product_id=key.split('_')[1],
                            quantity=int(value)
                        )
                
                # Process services
                service_data = {
                    'massage': (request.POST.get('massage_type'), 
                               request.POST.get('massage_days')),
                    'yoga': (request.POST.get('yoga_type'), 
                            request.POST.get('yoga_days'))
                }
                
                for service_type, (option_name, days) in service_data.items():
                    if option_name and option_name != 'none':
                        OrderItem.objects.create(
                            combo_order=order,  # Match model field name
                            service_type=service_type,
                            option_name=option_name,
                            days=int(days) if days else 1,
                            price=float(request.POST.get(f'{service_type}_price', 0)))
                
                return redirect('order_confirmation', order_id=order.id)
                
        except Exception as e:
            messages.error(request, f"Order failed: {str(e)}")
            return redirect(f'{combo_type}-combo')
    
    return redirect(f'{combo_type}-combo')

def process_payment(request, order):
    payment_method = order.payment_method
    
    if payment_method == 'BANK_NIC':
        request.session['last_order_id'] = order.id
        return render(request, 'main/bank_transfer.html', {'order': order})
    
    elif payment_method == 'COD':
        send_order_email(order, 'COD')
        messages.success(request, "Order placed! Pay on delivery.")
        return redirect('order_confirmation', order_id=order.id)
    
    # For future Khalti integration
    return redirect('order_confirmation', order_id=order.id)

def payment_success(request):
    return render(request, 'main/payment_success.html')        
        

def checkout(request):
    if request.method == 'POST':
        order = ComboOrder.objects.create(
            # ... other fields
            payment_method='COD',
            payment_verified=False  # Will verify on delivery
        )
        
        # Send COD confirmation
        send_mail(
            "COD Order Received",
            f"Order #{order.id} - Pay Rs. {order.total_price} on delivery",
            'noreply@yourstore.com',
            [request.user.email]
        )
        return redirect('order_confirmation', order_id=order.id)    
    
def handle_bank_transfer(request, order_id):
    order = get_object_or_404(ComboOrder, id=order_id)
    
    if request.method == 'POST' and request.FILES.get('receipt'):
        order.bank_receipt = request.FILES['receipt']
        order.save()
        send_order_email(order, 'Bank Transfer')
        messages.success(request, "Receipt uploaded for verification")
        return redirect('order_confirmation', order_id=order.id)
    
    return redirect('bank_transfer', order_id=order_id)         

@login_required
def essence_combo_view(request):
    # Fetch products
    products = Product.objects.filter(
        Q(category='essence') | Q(combo_type='essence')
    ).exclude(available=False)

    if request.method == 'POST':
        # Process order form submission
        payment_method = request.POST.get('payment_method')
        if not payment_method:
            return render(request, 'main/essence_combo.html', {
                'products': products,
                'error': 'Please select a payment method'
            })
        total_price = Decimal('0.00')
        order_items = []
        
        # Calculate totals and prepare order items
        for product in products:
            quantity = int(request.POST.get(f'quantity_{product.id}', 0))
            if quantity > 0:
                item_total = Decimal(product.price) * quantity
                total_price += item_total
                order_items.append({
                    'product': product,
                    'quantity': quantity,
                    'price': product.price
                })

        # Validate at least one item selected
        if not order_items:
            return render(request, 'main/essence_combo.html', {
                'products': products,
                'error': 'Please select at least one item'
            })

        try:
            # Create the order
            order = ComboOrder.objects.create(
                user=request.user,
                total_price=total_price,
                combo_type='Essence',
                payment_method=payment_method,
                payment_status=(payment_method == 'ONLINE')
            )

            # Create order items
            for item in order_items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity'],
                    price=item['price']
                )

            # Handle payment method redirection
            
            if payment_method == 'BANK_NIC':
                request.session['last_order_id'] = order.id 
                return redirect('bank_transfer_instructions', order_id=order.id)
            else:  # COD
                order.payment_status = 'COMPLETED'
                order.save()
                send_order_email(order, 'COD')
                request.session['last_order_id'] = order.id
                return redirect('order_confirmation',order_id=order.id)

        except Exception as e:
            # Handle any errors during order creation
            return render(request, 'main/essence_combo.html', {
                'products': products,
                'error': f'Error creating order: {str(e)}'
            })

    # GET request - show the form
    return render(request, 'main/essence_combo.html', {
        'products': products
    })
@login_required
def relief_combo_view(request):
    # Filter products - use the same filter as in your template
    products = Product.objects.filter(
        Q(name__iexact='Hot Bag') |
        Q(name__iexact='Thermus') |
        Q(name__iexact='Dark Chocolate') |
        Q(name__iexact='Sanitary Pad') |
        Q(name__iexact='Tampon') |
        Q(name__iexact='Menstrual Cup')
    ).exclude(
        Q(name__icontains='massage') | 
        Q(name__icontains='massag') |
        Q(name__icontains='yoga') |
        Q(name__icontains='meditation')
    )

    MASSAGE_SERVICES = {
        '30 minutes': {'price': Decimal('800'), 'image': '/media/products/msg.jpg'},
        '1 hour': {'price': Decimal('1500'), 'image': '/media/products/MSGG.jpg'}
    }

    if request.method == "POST":
        payment_method = request.POST.get('payment_method')
        if not payment_method:
            return render(request, 'main/relief_combo.html', {
                'products': products,
                'error': 'Please select a payment method'
            })
        try:
            with transaction.atomic():
                # Initialize total
                total = Decimal('0.00')
                selected_products = []
                
                # Process products
                for product in products:
                    qty = int(request.POST.get(f'qty_{product.id}', 0))
                    if qty > 0:
                        selected_products.append((product, qty))
                        total += product.price * qty

                # Process massage
                massage_type = request.POST.get('massage_type')
                days = int(request.POST.get('massage_days', 0))
                massage_price = Decimal('0.00')
                
                if massage_type and days > 0:
                    massage_price = MASSAGE_SERVICES[massage_type]['price'] * days
                    total += massage_price

                # Create order
                order = ComboOrder.objects.create(
                    user=request.user,
                    combo_type='Relief',
                    total_price=total
                )

                # Add products to order
                for product, qty in selected_products:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=qty,
                        price=product.price * qty
                    )

                # Add massage if selected
                if massage_price > 0:
                    OrderItem.objects.create(
                        order=order,
                        service_type='Massage',
                        duration=massage_type,
                        days=days,
                        price=massage_price
                    )
                if payment_method == 'BANK_NIC':
                    request.session['last_order_id'] = order.id 
                    return redirect('bank_transfer_instructions', order_id=order.id)
                else:  # COD
                    order.payment_status = 'COMPLETED'
                    order.save()
                    send_order_email(order, 'COD')
                    request.session['last_order_id'] = order.id
                    return redirect('order_confirmation',order_id=order.id)
    

    

        except Exception as e:
            messages.error(request, f"Error creating order: {str(e)}")
            return redirect('relief_combo')

    return render(request, 'main/relief_combo.html', {
        'products': products,
        'massage_services': MASSAGE_SERVICES
    })
@login_required
def shanti_combo_view(request):
    # Get products (excluding services)
    products = Product.objects.filter(
        Q(name__iexact='Hot Bag') |
        Q(name__iexact='Thermus') |
        Q(name__iexact='Dark Chocolate') |
        Q(name__iexact='Sanitary Pad') |
        Q(name__iexact='Tampon') |
        Q(name__iexact='Menstrual Cup')
    ).exclude(
        Q(name__icontains='massage') | 
        Q(name__icontains='yoga') |
        Q(name__icontains='meditation')
    )

    # Service options with images
    MASSAGE_OPTIONS = {
        'none': {'price': 0},
        '30 minutes': {'price': 800, 'image': '/media/products/msg.jpg'},
        '1 hour': {'price': 1500, 'image': '/media/products/MSGG.jpg'}
    }
    
    YOGA_OPTIONS = {
        'none': {'price': 0},
        'online': {'price': 300, 'image': '/media/products/yoga.jpg'},
        'physical': {'price': 600, 'image': '/media/products/med.png'}
    }

    if request.method == "POST":
       payment_method = request.POST.get('payment_method')
       if not payment_method:
            return render(request, 'main/shanti_combo.html', {
                'products': products,
                'error': 'Please select a payment method'
            })
        # Process order
       with transaction.atomic(): 
        selected_products = []
        total = Decimal('0.00')
        
        # Process products
        for product in products:
            qty = int(request.POST.get(f'product_{product.id}', 0))
            if qty > 0:
                selected_products.append((product, qty))
                total += product.price * qty

        # Process services
        # In the POST handling section:
        massage_type = request.POST.get('massage_type', 'none')
        yoga_type = request.POST.get('yoga_type', 'none')

        massage_days = int(request.POST.get('massage_days', 0)) if massage_type != 'none' else 0
        yoga_days = int(request.POST.get('yoga_days', 0)) if yoga_type != 'none' else 0

# Calculate totals
        massage_price = MASSAGE_OPTIONS[massage_type]['price'] * massage_days
        yoga_price = YOGA_OPTIONS[yoga_type]['price'] * yoga_days
        total += massage_price + yoga_price
        ## Create order
        order = ComboOrder.objects.create(
                    user=request.user,
                    combo_type='Shanti',
                    total_price=total
                )

                # Add products to order
        for product, qty in selected_products:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=qty,
                        price=product.price * qty
                    )


        # Save services
        if massage_type != 'none' and massage_days > 0:
            OrderItem.objects.create(
                order=order,
                service_type='Massage',
                duration=massage_type,
                days=massage_days,
                price=massage_price
            )
            
        if yoga_type != 'none' and yoga_days > 0:
            OrderItem.objects.create(
                order=order,
                service_type='Yoga',
                duration=yoga_type,
                days=yoga_days,
                price=yoga_price
            )
            
        if payment_method == 'BANK_NIC':
            request.session['last_order_id'] = order.id 
            return redirect('bank_transfer_instructions', order_id=order.id)
        else:  # COD
                    order.payment_status = 'COMPLETED'
                    order.save()
                    send_order_email(order, 'COD')
                    request.session['last_order_id'] = order.id
                    return redirect('order_confirmation',order_id=order.id)
    

        

        
    return render(request, 'main/shanti_combo.html', {
        'products': products,
        'massage_options': MASSAGE_OPTIONS,
        'yoga_options': YOGA_OPTIONS
    })
    
def create_order(request):
    if request.method == 'POST':
        try:
            # Create order
            order = ComboOrder.objects.create(
                user=request.user if request.user.is_authenticated else None,
                total=float(request.POST.get('total', 0))
            )
            
            # Add products
            for key, value in request.POST.items():
                if key.startswith('product_') and int(value) > 0:
                    product_id = key.split('_')[1]
                    OrderItem.objects.create(
                        order=order,
                        product_id=product_id,
                        quantity=value
                    )
            
            # Add services
            if request.POST.get('massage_type') != 'none':
                OrderItem.objects.create(
                    order=order,
                    service_type='massage',
                    service_name=request.POST['massage_type'],
                    days=request.POST.get('massage_days', 1)
                )
                
            if request.POST.get('yoga_type') != 'none':
                OrderItem.objects.create(
                    order=order,
                    service_type='yoga',
                    service_name=request.POST['yoga_type'],
                    days=request.POST.get('yoga_days', 1)
                )
            
            return redirect('order_confirmation', order_id=order.id)
            
        except Exception as e:
            messages.error(request, f"Error creating order: {str(e)}")
            return redirect('combo_page')
    
    return redirect('combo_page')    

def bank_transfer_instructions(request, order_id):
    order = get_object_or_404(ComboOrder, id=order_id)
    
    # Get bank details from settings
    bank_details = settings.BANK_DETAILS.get('BANK_NIC', {})
    
    # Add order-specific info
    bank_details.update({
        'amount': order.total_price,
        'reference': f"Order #{order.id}"
    })
    
    return render(request, 'main/bank_transfer.html', {
        'order': order,
        'bank_details': bank_details
    })
logger = logging.getLogger(__name__)

def upload_receipt(request, order_id):
    order = get_object_or_404(ComboOrder, id=order_id, user=request.user)
    
    if request.method == 'POST' and request.FILES.get('receipt'):
        receipt = request.FILES['receipt']
        transaction_id = request.POST.get('transaction_id', '').strip()
        
        # 1. Validate receipt file
        try:
            # File type validation
            valid_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
            ext = os.path.splitext(receipt.name)[1].lower()
            if ext not in valid_extensions:
                messages.error(request, "Invalid file type. Only JPG, PNG, or PDF allowed.")
                return redirect('bank_transfer_instructions', order_id=order.id)
            
            # File size validation (5MB max)
            if receipt.size > 5 * 1024 * 1024:
                messages.error(request, "File too large (maximum 5MB allowed).")
                return redirect('bank_transfer_instructions', order_id=order.id)
            
            # 2. Process the receipt
            receipt_path = default_storage.save(
                f'receipts/order_{order.id}/{receipt.name}',
                ContentFile(receipt.read())
            )
            
            # 3. Basic OCR verification (optional)
            verification_data = None
            if ext in ['.jpg', '.jpeg', '.png']:
                try:
                    img = Image.open(default_storage.open(receipt_path))
                    text = pytesseract.image_to_string(img)
                    verification_data = {
                        'amount': extract_amount(text),  # Custom function
                        'date': extract_date(text),      # Custom function
                        'account': extract_account(text) # Custom function
                    }
                except Exception as e:
                    logger.warning(f"OCR processing failed: {str(e)}")
            
            # 4. Create payment record
            BankPayment.objects.create(
                order=order,
                receipt=receipt_path,
                transaction_id=transaction_id,
                verification_data=verification_data,
                uploaded_by=request.user
            )
            
            # 5. Update order status
            order.payment_status = 'PENDING_VERIFICATION'
            order.save()
            
            # 6. Send notifications
            try:
                # Admin email
                send_mail(
                    f'Receipt Uploaded for Order #{order.id}',
                    f"""
                    New receipt uploaded:
                    
                    Order ID: {order.id}
                    Amount: Rs. {order.total_price}
                    Transaction ID: {transaction_id}
                    
                    View receipt: {request.build_absolute_uri(default_storage.url(receipt_path))}
                    """,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL],
                    fail_silently=False
                )
                
                # Customer email
                send_mail(
                    'Receipt Received',
                    f"""
                    Thank you for submitting your payment receipt for Order #{order.id}.
                    
                    We'll verify your payment within 24 hours.
                    
                    Transaction ID: {transaction_id}
                    Amount: Rs. {order.total_price}
                    """,
                    settings.DEFAULT_FROM_EMAIL,
                    [order.user.email],
                    fail_silently=True
                )
                
                messages.success(request, "Receipt uploaded successfully! We'll verify your payment shortly.")
            except Exception as e:
                logger.error(f"Email sending failed: {str(e)}")
                messages.warning(request, "Receipt uploaded! We'll verify your payment shortly (notification failed).")
            
            return redirect('order_confirmation', order_id=order.id)
            
        except Exception as e:
            logger.error(f"Receipt upload failed: {str(e)}")
            messages.error(request, "Error processing your receipt. Please try again.")
            return redirect('bank_transfer_instructions', order_id=order.id)
    
    return redirect('bank_transfer_instructions', order_id=order.id)


# Helper functions for OCR (optional)
def extract_amount(text):
    """Extract payment amount from receipt text"""
    # Implement regex patterns for your bank's receipts
    import re
    matches = re.findall(r'Rs?\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
    return matches[0] if matches else None

def extract_date(text):
    """Extract transaction date from receipt text"""
    from datetime import datetime
    try:
        # Adjust patterns based on your bank's format
        date_str = re.search(r'\d{2}/\d{2}/\d{4}', text).group()
        return datetime.strptime(date_str, '%d/%m/%Y').date()
    except:
        return None

def extract_account(text):
    """Extract account number from receipt text"""
    # Implement based on your bank's format
    return re.search(r'Account:\s*(\d+)', text).group(1) if re.search(r'Account:\s*(\d+)', text) else None
@login_required
def order_history(request):
    orders = ComboOrder.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'main/order_history.html', {'orders': orders})

def order_detail(request, order_id):
    order = get_object_or_404(ComboOrder, id=order_id)
    items = order.items.all()
    return render(request, 'main/order_detail.html', {'order': order, 'items': items})
def track_order(request, order_id):
    order = get_object_or_404(ComboOrder, id=order_id, user=request.user)
    updates = TrackingUpdate.objects.filter(order=order).order_by('-timestamp')
    
    # Auto-generate initial tracking event if none exists
    if not updates.exists():
        TrackingUpdate.objects.create(
            order=order,
            status='PROCESSING',
            notes='We are preparing your DD को माया package'
        )
        updates = TrackingUpdate.objects.filter(order=order)
    
    return render(request, 'main/tracking.html', {
        'order': order,
        'updates': updates
    })
def checkout(request):
    if request.method == 'POST':
        form = OrderContactForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.save()
            return redirect('payment')
    else:
        profile = request.user.userprofile
        initial = {
            'delivery_contact_phone': profile.phone,
            'delivery_contact_name': request.user.get_full_name()
        }
        form = OrderContactForm(initial=initial)
    
    return render(request, 'main/checkout.html', {'form': form})

@login_required
def edit_profile(request):
    profile = request.user.userprofile
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'edit_profile.html', {'form': form})