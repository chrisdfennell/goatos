from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.db.models import F, Sum, Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import json
import requests
import qrcode
from io import BytesIO
import base64

from .models import Goat, GoatLog, GrazingArea, DailyTask, TaskCompletion, Vet, MedicalRecord, FarmSettings, FeedingLog, BreedingLog, FeedItem, MilkLog, Transaction, WeightLog, FarmEvent, Medicine, GoatPhoto, Customer, WaitingList, Sale

# --- HELPER FUNCTIONS ---
def get_common_context():
    """Helper to get context data needed for the base template (like settings)"""
    farm_settings, _ = FarmSettings.objects.get_or_create(pk=1)
    return {'farm_settings': farm_settings}

def get_weather_data(lat, lon):
    if not lat or not lon or (lat == 0.0 and lon == 0.0):
        return None
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code",
        "wind_speed_unit": "ms"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Weather Error: {e}")
        return None

# --- DASHBOARDS ---
def index(request):
    context = get_common_context()
    farm_settings = context['farm_settings']
    
    # Weather
    weather_info = None
    if farm_settings.latitude and farm_settings.longitude:
        w_data = get_weather_data(farm_settings.latitude, farm_settings.longitude)
        if w_data and 'current' in w_data:
            weather_info = {
                'temp': w_data['current']['temperature_2m'],
                'humidity': w_data['current']['relative_humidity_2m'],
                'code': w_data['current']['weather_code']
            }

    goats = Goat.objects.all()
    grazing_areas = GrazingArea.objects.all()
    vets = Vet.objects.all()
    today = timezone.now().date()
    
    # Alerts Logic
    low_stock_items = FeedItem.objects.filter(quantity__lte=F('low_stock_threshold'))
    two_weeks = today + timedelta(days=14)
    medical_alerts = MedicalRecord.objects.filter(
        next_due_date__isnull=False,
        next_due_date__lte=two_weeks
    ).select_related('goat').order_by('next_due_date')
    three_weeks = today + timedelta(days=21)
    kidding_alerts = BreedingLog.objects.filter(
        due_date__isnull=False,
        due_date__gte=today,
        due_date__lte=three_weeks
    ).select_related('goat').order_by('due_date')
    expired_meds = Medicine.objects.filter(expiration_date__lte=today)
    
    has_alerts = low_stock_items.exists() or medical_alerts.exists() or kidding_alerts.exists() or expired_meds.exists()

    all_tasks = DailyTask.objects.all()
    completed_task_ids = set(
        TaskCompletion.objects.filter(date=today, completed=True)
        .values_list('task_id', flat=True)
    )
    
    areas_list = []
    for area in grazing_areas:
        try:
            areas_list.append({
                'name': area.name,
                'color': area.color,
                'coords': json.loads(area.coordinates)
            })
        except: pass

    context.update({
        'weather': weather_info,
        'goats': goats, 
        'grazing_areas': areas_list,
        'am_tasks': all_tasks.filter(time_of_day='AM'),
        'pm_tasks': all_tasks.filter(time_of_day='PM'),
        'any_tasks': all_tasks.filter(time_of_day='ANY'),
        'completed_task_ids': completed_task_ids,
        'has_tasks': all_tasks.exists(),
        'vets': vets,
        'low_stock_items': low_stock_items,
        'medical_alerts': medical_alerts,
        'kidding_alerts': kidding_alerts,
        'expired_meds': expired_meds,
        'has_alerts': has_alerts
    })
    return render(request, 'farm/index.html', context)

def update_settings(request):
    if request.method == 'POST':
        settings, _ = FarmSettings.objects.get_or_create(pk=1)
        settings.name = request.POST.get('name', settings.name)
        settings.google_maps_api_key = request.POST.get('google_maps_api_key', settings.google_maps_api_key)
        try:
            lat = request.POST.get('latitude')
            lng = request.POST.get('longitude')
            if lat: settings.latitude = float(lat)
            if lng: settings.longitude = float(lng)
        except ValueError: pass
        settings.save()
    return redirect('index')

def milk_dashboard(request):
    if request.method == 'POST':
        goat_id = request.POST.get('goat')
        if goat_id:
            MilkLog.objects.create(
                goat_id=goat_id,
                date=request.POST.get('date'),
                time=request.POST.get('time'),
                amount=request.POST.get('amount')
            )
            return redirect('milk_dashboard')

    logs = MilkLog.objects.all().order_by('-date', '-time')
    total_all_time = logs.aggregate(Sum('amount'))['amount__sum'] or 0
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    monthly_logs = logs.filter(date__gte=thirty_days_ago)
    total_30_days = monthly_logs.aggregate(Sum('amount'))['amount__sum'] or 0
    goats = Goat.objects.all()

    context = get_common_context()
    context.update({
        'logs': logs,
        'total_all_time': total_all_time,
        'total_30_days': total_30_days,
        'goats': goats
    })
    return render(request, 'farm/milk.html', context)

def breeding_dashboard(request):
    today = timezone.now().date()
    all_breeding_logs = BreedingLog.objects.all().order_by('due_date')
    active_pregnancies = [log for log in all_breeding_logs if log.due_date and log.due_date >= today]
    context = get_common_context()
    context.update({
        'active_pregnancies': active_pregnancies,
        'all_breeding_logs': all_breeding_logs
    })
    return render(request, 'farm/breeding.html', context)

def silo_dashboard(request):
    feed_items = FeedItem.objects.all().order_by('name')
    context = get_common_context()
    context.update({'feed_items': feed_items})
    return render(request, 'farm/silo.html', context)

def update_inventory(request, item_id):
    item = get_object_or_404(FeedItem, pk=item_id)
    if request.method == 'POST':
        try:
            item.quantity = F('quantity') + float(request.POST.get('amount', 0))
            item.save()
        except: pass
    return redirect('silo_dashboard')

def finance_dashboard(request):
    if request.method == 'POST':
        Transaction.objects.create(
            date=request.POST.get('date'),
            type=request.POST.get('type'),
            category=request.POST.get('category'),
            amount=request.POST.get('amount'),
            description=request.POST.get('description')
        )
        return redirect('finance_dashboard')

    transactions = Transaction.objects.all()
    total_income = transactions.filter(type='Income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = transactions.filter(type='Expense').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense

    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    month_income = transactions.filter(type='Income', date__gte=current_month_start).aggregate(Sum('amount'))['amount__sum'] or 0
    month_expense = transactions.filter(type='Expense', date__gte=current_month_start).aggregate(Sum('amount'))['amount__sum'] or 0

    context = get_common_context()
    context.update({
        'transactions': transactions[:50],
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'month_income': month_income,
        'month_expense': month_expense
    })
    return render(request, 'farm/finance.html', context)

def weight_dashboard(request):
    recent_weights = WeightLog.objects.select_related('goat').order_by('-date')[:20]
    goats = Goat.objects.all()
    context = get_common_context()
    context.update({'recent_weights': recent_weights, 'goats': goats})
    return render(request, 'farm/weight.html', context)

def calendar_dashboard(request):
    if request.method == 'POST':
        FarmEvent.objects.create(
            title=request.POST.get('title'),
            date=request.POST.get('date'),
            end_date=request.POST.get('end_date') or None,
            category=request.POST.get('category')
        )
        return redirect('calendar_dashboard')

    events = []
    
    # System Events (Read Only)
    for log in BreedingLog.objects.filter(due_date__isnull=False):
        events.append({
            'title': f"👶 Due: {log.goat.name}",
            'start': log.due_date.isoformat(),
            'color': '#9C27B0', 
            'url': f"/goat/{log.goat.id}/",
            'editable': False 
        })
    
    for record in MedicalRecord.objects.filter(next_due_date__isnull=False):
        events.append({
            'title': f"🏥 {record.get_record_type_display()}: {record.goat.name}",
            'start': record.next_due_date.isoformat(),
            'color': '#e91e63', 
            'url': f"/goat/{record.goat.id}/",
            'editable': False
        })
        
    # Custom Events (Editable)
    for event in FarmEvent.objects.all():
        event_data = {
            'id': event.id,
            'title': f"{event.title}",
            'start': event.date.isoformat(),
            'extendedProps': { 'type': 'custom', 'category': event.category }
        }
        
        cat = event.category
        if cat == 'Vet': event_data['color'] = '#f44336'
        elif cat == 'Show': event_data['color'] = '#FF9800'
        elif cat == 'Breeding': event_data['color'] = '#9C27B0'
        elif cat == 'Maintenance': event_data['color'] = '#607D8B'
        elif cat == 'Purchase': event_data['color'] = '#4CAF50'
        else: event_data['color'] = '#2196F3'

        if event.end_date:
            end_d = event.end_date + timedelta(days=1)
            event_data['end'] = end_d.isoformat()
            
        events.append(event_data)

    context = get_common_context()
    context.update({'events_json': json.dumps(events)})
    return render(request, 'farm/calendar.html', context)

def medicine_dashboard(request):
    if request.method == 'POST':
        Medicine.objects.create(
            name=request.POST.get('name'),
            quantity=request.POST.get('quantity'),
            unit=request.POST.get('unit'),
            batch=request.POST.get('batch'),
            expiration_date=request.POST.get('expiration_date') or None,
            dosage_amount=request.POST.get('dosage_amount') or 1.0,
            dosage_weight_interval=request.POST.get('dosage_weight_interval') or 0.0,
            notes=request.POST.get('notes')
        )
        return redirect('medicine_dashboard')
    
    meds = Medicine.objects.all().order_by('expiration_date')
    context = get_common_context()
    context.update({'meds': meds})
    return render(request, 'farm/medicine.html', context)

# --- NEW: CRM DASHBOARD ---
def crm_dashboard(request):
    if request.method == 'POST':
        # Add Customer
        if 'customer_name' in request.POST:
            Customer.objects.create(
                name=request.POST.get('customer_name'),
                email=request.POST.get('customer_email'),
                phone=request.POST.get('customer_phone'),
                notes=request.POST.get('customer_notes')
            )
        # Add Waitlist Entry
        elif 'waitlist_customer' in request.POST:
            WaitingList.objects.create(
                customer_id=request.POST.get('waitlist_customer'),
                preferred_dam_id=request.POST.get('preferred_dam') or None,
                preferred_gender=request.POST.get('preferred_gender'),
                notes=request.POST.get('waitlist_notes')
            )
        # Update Status (Simple Toggle for demo)
        elif 'update_status_id' in request.POST:
            entry = get_object_or_404(WaitingList, pk=request.POST.get('update_status_id'))
            if entry.status == 'Active':
                entry.status = 'Fulfilled'
            else:
                entry.status = 'Active'
            entry.save()
            
        return redirect('crm_dashboard')

    customers = Customer.objects.all().order_by('name')
    waiting_list = WaitingList.objects.filter(status='Active').order_by('-date_added')
    goats = Goat.objects.all()

    context = get_common_context()
    context.update({
        'customers': customers,
        'waiting_list': waiting_list,
        'goats': goats
    })
    return render(request, 'farm/crm.html', context)

def stall_card(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    goat_url = request.build_absolute_uri(reverse('goat_detail', args=[goat.id]))
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(goat_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'farm/stall_card.html', {'goat': goat, 'qr_code': img_str})

# --- TOOLS DASHBOARD ---
def tools_dashboard(request):
    goats = Goat.objects.all() # Needed for head count calculation
    context = get_common_context()
    context.update({'goats': goats})
    return render(request, 'farm/tools.html', context)

# --- API ENDPOINTS ---
@csrf_exempt
def move_event(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event = get_object_or_404(FarmEvent, pk=data.get('id'))
            event.date = data.get('date')
            new_end = data.get('end_date')
            if new_end:
                end_date_obj = datetime.strptime(new_end, "%Y-%m-%d").date() - timedelta(days=1)
                event.end_date = end_date_obj
            event.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
def resize_event(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event = get_object_or_404(FarmEvent, pk=data.get('id'))
            fc_end_str = data.get('end_date')
            if fc_end_str:
                end_date_obj = datetime.strptime(fc_end_str, "%Y-%m-%d").date() - timedelta(days=1)
                event.end_date = end_date_obj
                event.save()
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
def update_event_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event = get_object_or_404(FarmEvent, pk=data.get('id'))
            event.title = data.get('title')
            event.date = data.get('date')
            end = data.get('end_date')
            event.end_date = end if end else None
            event.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

def delete_event_api(request, event_id):
    try:
        event = get_object_or_404(FarmEvent, pk=event_id)
        event.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def get_daily_tasks(request, date_str):
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        all_tasks = DailyTask.objects.all()
        completed_ids = set(
            TaskCompletion.objects.filter(date=query_date, completed=True)
            .values_list('task_id', flat=True)
        )
        task_list = []
        for task in all_tasks:
            task_list.append({
                'id': task.id,
                'name': task.name,
                'time_of_day': task.get_time_of_day_display(),
                'completed': task.id in completed_ids
            })
        return JsonResponse({'tasks': task_list})
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

@csrf_exempt
def toggle_task_date(request, task_id, date_str):
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        task = get_object_or_404(DailyTask, pk=task_id)
        completion, created = TaskCompletion.objects.get_or_create(task=task, date=query_date)
        if created: completion.completed = True
        else: completion.completed = not completion.completed
        completion.save()
        return JsonResponse({'status': 'success', 'completed': completion.completed})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def quick_milk(request, goat_id):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        if amount and float(amount) > 0:
            MilkLog.objects.create(
                goat_id=goat_id,
                amount=amount,
                date=timezone.now().date(),
                time='AM' if timezone.now().hour < 12 else 'PM',
                notes="Quick Log from Dashboard"
            )
    return redirect('index')

def toggle_sick(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if goat.status == 'Sick':
        goat.status = 'Healthy'
    else:
        goat.status = 'Sick'
        GoatLog.objects.create(goat=goat, note="Marked as Sick via Quick Action")
    goat.save()
    return redirect('index')

# --- GOAT DETAIL & ACTIONS ---
def goat_detail(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    
    if request.method == 'POST':
        # 1. Profile Image Upload
        if 'image' in request.FILES:
            goat.image = request.FILES['image']
            goat.save()
            return redirect('goat_detail', goat_id=goat.id)
            
        # 2. Daily Log Note
        if 'note' in request.POST:
            GoatLog.objects.create(goat=goat, note=request.POST.get('note'))
            return redirect('goat_detail', goat_id=goat.id)
            
        # 3. NEW: Gallery Upload
        if 'gallery_image' in request.FILES:
            GoatPhoto.objects.create(
                goat=goat, 
                image=request.FILES['gallery_image'],
                caption=request.POST.get('caption', '')
            )
            return redirect('goat_detail', goat_id=goat.id)

    logs = goat.logs.all().order_by('-date')
    medical_records = goat.medical_records.all().order_by('-date')
    feeding_logs = goat.feeding_logs.all().order_by('-date')
    breeding_logs = goat.breeding_logs.all().order_by('-breeding_date')
    milk_logs = goat.milk_logs.all().order_by('-date')
    
    # Chart Data
    weight_logs = goat.weight_logs.all().order_by('date')
    weight_chart_data = {
        'dates': [log.date.strftime("%Y-%m-%d") for log in weight_logs],
        'weights': [float(log.weight) for log in weight_logs]
    }
    daily_milk = goat.milk_logs.values('date').annotate(total=Sum('amount')).order_by('date')
    milk_chart_data = {
        'dates': [x['date'].strftime("%Y-%m-%d") for x in daily_milk],
        'amounts': [float(x['total']) for x in daily_milk]
    }
    
    # Metadata
    latest_weight = weight_logs.last().weight if weight_logs.exists() else 0
    medicines = Medicine.objects.all().values('id', 'name', 'dosage_amount', 'dosage_weight_interval', 'unit')
    
    # Fetch Gallery Photos
    gallery_photos = goat.photos.all()

    context = get_common_context()
    context.update({
        'goat': goat, 'logs': logs, 'medical_records': medical_records,
        'feeding_logs': feeding_logs, 'breeding_logs': breeding_logs, 
        'milk_logs': milk_logs, 'weight_logs': weight_logs.order_by('-date'),
        'weight_chart_data': json.dumps(weight_chart_data),
        'milk_chart_data': json.dumps(milk_chart_data),
        'latest_weight': latest_weight,
        'medicines_json': json.dumps(list(medicines)),
        'gallery_photos': gallery_photos
    })
    return render(request, 'farm/goat_detail.html', context)

def add_weight_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        WeightLog.objects.create(
            goat=goat,
            date=request.POST.get('date'),
            weight=request.POST.get('weight'),
            notes=request.POST.get('notes')
        )
    return redirect('goat_detail', goat_id=goat.id)

def add_medical_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        MedicalRecord.objects.create(
            goat=goat,
            record_type=request.POST.get('record_type'),
            date=request.POST.get('date'),
            notes=request.POST.get('notes'),
            next_due_date=request.POST.get('next_due_date') or None
        )
    return redirect('goat_detail', goat_id=goat.id)

def add_feeding_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        FeedingLog.objects.create(
            goat=goat,
            date=request.POST.get('date') or timezone.now().date(),
            feed_type=request.POST.get('feed_type'),
            amount=request.POST.get('amount'),
            notes=request.POST.get('notes')
        )
    return redirect('goat_detail', goat_id=goat.id)

def add_breeding_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        BreedingLog.objects.create(
            goat=goat,
            mate_name=request.POST.get('mate_name'),
            breeding_date=request.POST.get('breeding_date'),
            notes=request.POST.get('notes')
        )
    return redirect('goat_detail', goat_id=goat.id)

def update_goat_status(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        goat.status = request.POST.get('status', 'Healthy')
        goat.save()
    return redirect('goat_detail', goat_id=goat.id)

def delete_goat(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        goat.delete()
        return redirect('index')
    return redirect('goat_detail', goat_id=goat.id)

def save_grazing_area(request):
    if request.method == 'POST':
        GrazingArea.objects.create(
            name=request.POST.get('area_name'),
            color=request.POST.get('area_color'),
            coordinates=request.POST.get('area_coords')
        )
    return redirect('index')

def toggle_task(request, task_id):
    task = get_object_or_404(DailyTask, pk=task_id)
    today = timezone.now().date()
    completion, created = TaskCompletion.objects.get_or_create(task=task, date=today)
    if not created: completion.delete()
    else: completion.completed = True; completion.save()
    return redirect('index')

def sales_list(request):
    sales = Sale.objects.all().order_by('-sale_date')
    context = get_common_context()
    context.update({'sales': sales})
    return render(request, 'farm/sales_list.html', context)