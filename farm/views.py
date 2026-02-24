from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.db.models import F, Sum, Q, Avg
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.contrib import messages
from django.conf import settings as django_settings
import json
import csv
import requests
import qrcode
from io import BytesIO
import base64
from .forms import MeatHarvestForm
from .models import (Goat, GoatLog, GrazingArea, DailyTask, TaskCompletion, Vet, MedicalRecord,
    FarmSettings, FeedingLog, BreedingLog, FeedItem, MilkLog, Transaction, WeightLog, FarmEvent,
    Medicine, GoatPhoto, Customer, WaitingList, Sale, MeatHarvest, PastureAssignment, MapMarker,
    PastureCondition, MedicalSchedule, KiddingRecord, HealthScore, HeatObservation, GoatDocument,
    Supplier, Pen, PenAssignment)
from django.db.models import Count
import os
import zipfile
import sqlite3
import zipfile
import sqlite3 as sqlite3_lib

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
            active = area.active_assignment
            goat_names = []
            goat_count = 0
            if active:
                assigned_goats = active.goats.all()
                goat_count = assigned_goats.count()
                goat_names = [g.name for g in assigned_goats]
            latest_cond = area.latest_condition
            areas_list.append({
                'id': area.id,
                'name': area.name,
                'color': area.color,
                'coords': json.loads(area.coordinates),
                'goat_count': goat_count,
                'goat_names': goat_names,
                'days_resting': area.days_resting,
                'condition_score': latest_cond.score if latest_cond else None,
            })
        except (json.JSONDecodeError, TypeError):
            pass

    # Map markers
    markers_list = list(MapMarker.objects.all().values('id', 'name', 'marker_type', 'latitude', 'longitude', 'notes'))

    # Active pasture assignments
    active_assignments = PastureAssignment.objects.filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).select_related('grazing_area').prefetch_related('goats')

    # Medical schedule alerts
    schedule_alerts = [s for s in MedicalSchedule.objects.select_related('goat').all() if s.is_due_soon]

    # FAMACHA alerts: goats with score >= 4 (needs deworming)
    famacha_alerts = []
    for goat in goats:
        latest_score = goat.health_scores.first()
        if latest_score and latest_score.famacha_score and latest_score.famacha_score >= 4:
            famacha_alerts.append({'goat': goat, 'score': latest_score.famacha_score, 'date': latest_score.date})

    # Heat alerts: does predicted in heat within 3 days
    three_days = today + timedelta(days=3)
    heat_alerts = []
    for goat in goats.filter(gender__in=['Doe', 'Doeling']):
        latest_heat = goat.heat_observations.first()
        if latest_heat and latest_heat.next_heat_date >= today and latest_heat.next_heat_date <= three_days:
            heat_alerts.append({'goat': goat, 'predicted_date': latest_heat.next_heat_date})

    # Pen over-capacity alerts
    overcrowded_pens = [p for p in Pen.objects.all() if p.is_over_capacity]

    has_alerts = has_alerts or len(schedule_alerts) > 0 or len(famacha_alerts) > 0 or len(heat_alerts) > 0 or len(overcrowded_pens) > 0

    # Rotation timeline (last 90 days)
    ninety_days_ago = today - timedelta(days=90)
    rotation_history = PastureAssignment.objects.filter(
        Q(start_date__gte=ninety_days_ago) | Q(end_date__gte=ninety_days_ago) | Q(end_date__isnull=True)
    ).select_related('grazing_area').prefetch_related('goats').order_by('start_date')
    rotation_timeline = []
    for a in rotation_history:
        rotation_timeline.append({
            'area_name': a.grazing_area.name,
            'color': a.grazing_area.color,
            'start_date': a.start_date.isoformat(),
            'end_date': a.end_date.isoformat() if a.end_date else None,
            'goats': [g.name for g in a.goats.all()],
        })

    context.update({
        'goats': goats,
        'grazing_areas': areas_list,
        'map_markers': markers_list,
        'active_assignments': active_assignments,
        'all_grazing_areas': grazing_areas,
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
        'schedule_alerts': schedule_alerts,
        'famacha_alerts': famacha_alerts,
        'heat_alerts': heat_alerts,
        'overcrowded_pens': overcrowded_pens,
        'has_alerts': has_alerts,
        'rotation_timeline_data': rotation_timeline,
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
        messages.success(request, 'Settings updated.')
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
            messages.success(request, 'Milk log recorded.')
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
    kidding_records = KiddingRecord.objects.select_related('dam', 'breeding_log').order_by('-kidding_date')[:30]
    does = Goat.objects.filter(gender__in=['Doe', 'Doeling']).order_by('name')
    breeding_logs_for_form = BreedingLog.objects.filter(due_date__isnull=False).select_related('goat').order_by('-due_date')[:20]
    context = get_common_context()
    context.update({
        'active_pregnancies': active_pregnancies,
        'all_breeding_logs': all_breeding_logs,
        'kidding_records': kidding_records,
        'does': does,
        'breeding_logs_for_form': breeding_logs_for_form,
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
            amount = float(request.POST.get('amount', 0))
            item.refresh_from_db()
            new_qty = float(item.quantity) + amount
            if new_qty < 0:
                new_qty = 0
            item.quantity = new_qty
            item.save()
            messages.success(request, f'{item.name} inventory updated.')
        except (ValueError, TypeError):
            pass  # Invalid quantity input
    return redirect('silo_dashboard')

def finance_dashboard(request):
    if request.method == 'POST':
        goat_id = request.POST.get('goat_id')
        supplier_id = request.POST.get('supplier_id')
        Transaction.objects.create(
            date=request.POST.get('date'),
            type=request.POST.get('type'),
            category=request.POST.get('category'),
            amount=request.POST.get('amount'),
            description=request.POST.get('description'),
            goat_id=goat_id if goat_id else None,
            supplier_id=supplier_id if supplier_id else None,
        )
        messages.success(request, 'Transaction recorded.')
        return redirect('finance_dashboard')

    transactions = Transaction.objects.select_related('goat', 'supplier').all()
    total_income = transactions.filter(type='Income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = transactions.filter(type='Expense').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense

    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    month_income = transactions.filter(type='Income', date__gte=current_month_start).aggregate(Sum('amount'))['amount__sum'] or 0
    month_expense = transactions.filter(type='Expense', date__gte=current_month_start).aggregate(Sum('amount'))['amount__sum'] or 0

    goats = Goat.objects.all().order_by('name')
    suppliers = Supplier.objects.all().order_by('name')

    context = get_common_context()
    context.update({
        'transactions': transactions[:50],
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'month_income': month_income,
        'month_expense': month_expense,
        'goats': goats,
        'suppliers': suppliers,
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
        messages.success(request, 'Event added to calendar.')
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
        
    # Medical Schedule Events (Recurring)
    for schedule in MedicalSchedule.objects.select_related('goat').all():
        target = schedule.goat.name if schedule.goat else "Herd"
        events.append({
            'title': f"🔁 {schedule.get_record_type_display()}: {target}",
            'start': schedule.next_due.isoformat(),
            'color': '#FF5722',
            'editable': False,
            'url': f"/goat/{schedule.goat.id}/" if schedule.goat else '',
        })

    # Heat / Estrus Events (predicted cycles)
    for obs in HeatObservation.objects.select_related('goat').all():
        # Show the observed heat
        events.append({
            'title': f"🔥 Heat: {obs.goat.name}",
            'start': obs.date_observed.isoformat(),
            'color': '#E91E63',
            'url': f"/goat/{obs.goat.id}/",
            'editable': False,
        })
        # Show predicted next heat
        next_heat = obs.next_heat_date
        if next_heat >= date.today() - timedelta(days=7):
            events.append({
                'title': f"🔮 Predicted Heat: {obs.goat.name}",
                'start': next_heat.isoformat(),
                'color': '#FF80AB',
                'url': f"/goat/{obs.goat.id}/",
                'editable': False,
            })

    # Kidding records (past births)
    for kr in KiddingRecord.objects.select_related('dam').all():
        events.append({
            'title': f"🐣 Kidding: {kr.dam.name} ({kr.birth_type})",
            'start': kr.kidding_date.isoformat(),
            'color': '#4CAF50',
            'url': f"/goat/{kr.dam.id}/",
            'editable': False,
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
        messages.success(request, 'Medicine added to cabinet.')
        return redirect('medicine_dashboard')
    
    meds = Medicine.objects.all().order_by('expiration_date')
    schedules = MedicalSchedule.objects.select_related('goat').all()
    goats = Goat.objects.all()
    context = get_common_context()
    context.update({'meds': meds, 'schedules': schedules, 'goats': goats})
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
            messages.success(request, 'Customer added.')
        # Add Waitlist Entry
        elif 'waitlist_customer' in request.POST:
            WaitingList.objects.create(
                customer_id=request.POST.get('waitlist_customer'),
                preferred_dam_id=request.POST.get('preferred_dam') or None,
                preferred_gender=request.POST.get('preferred_gender'),
                notes=request.POST.get('waitlist_notes')
            )
            messages.success(request, 'Added to waiting list.')
        # Update Status (Simple Toggle for demo)
        elif 'update_status_id' in request.POST:
            entry = get_object_or_404(WaitingList, pk=request.POST.get('update_status_id'))
            if entry.status == 'Active':
                entry.status = 'Fulfilled'
            else:
                entry.status = 'Active'
            entry.save()
            messages.success(request, 'Status updated.')

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
@require_POST
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

@require_POST
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

@require_POST
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

@require_POST
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

@require_POST
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

@require_POST
def quick_milk(request, goat_id):
    try:
        amount = request.POST.get('amount')
        if amount and float(amount) > 0:
            MilkLog.objects.create(
                goat_id=goat_id,
                amount=amount,
                date=timezone.now().date(),
                time='AM' if timezone.now().hour < 12 else 'PM',
                notes="Quick Log from Dashboard"
            )
    except (ValueError, TypeError):
        pass  # Invalid amount input
    return redirect('index')

@require_POST
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
            uploaded = request.FILES['image']
            if uploaded.size > 10 * 1024 * 1024:  # 10 MB limit
                messages.error(request, "Image too large. Maximum size is 10MB.")
                return redirect('goat_detail', goat_id=goat.id)
            goat.image = uploaded
            goat.save()
            messages.success(request, 'Profile photo updated.')
            return redirect('goat_detail', goat_id=goat.id)

        # 2. Daily Log Note
        if 'note' in request.POST:
            GoatLog.objects.create(goat=goat, note=request.POST.get('note'))
            messages.success(request, 'Log entry added.')
            return redirect('goat_detail', goat_id=goat.id)

        # 3. Gallery Upload
        if 'gallery_image' in request.FILES:
            uploaded = request.FILES['gallery_image']
            if uploaded.size > 10 * 1024 * 1024:  # 10 MB limit
                messages.error(request, "Image too large. Maximum size is 10MB.")
                return redirect('goat_detail', goat_id=goat.id)
            GoatPhoto.objects.create(
                goat=goat,
                image=uploaded,
                caption=request.POST.get('caption', '')
            )
            messages.success(request, 'Photo added to gallery.')
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
    
    # Fetch Gallery Photos (ordered by date for timeline)
    gallery_photos = goat.photos.all().order_by('date_added')

    # Offspring (Feature 9: Pedigree)
    offspring = Goat.objects.filter(Q(dam=goat) | Q(sire=goat)).distinct()

    # Health Scores (FAMACHA & BCS)
    health_scores = goat.health_scores.all()[:20]
    health_chart_data = json.dumps({
        'dates': [s.date.strftime('%b %d') for s in reversed(list(health_scores))],
        'famacha': [s.famacha_score for s in reversed(list(health_scores))],
        'bcs': [float(s.body_condition_score) if s.body_condition_score else None for s in reversed(list(health_scores))],
    })

    # Heat Observations
    heat_observations = goat.heat_observations.all()[:10]

    # Documents
    documents = goat.documents.all()

    # Current Pen Assignment
    current_pen = PenAssignment.objects.filter(goat=goat, date_out__isnull=True).select_related('pen').first()

    context = get_common_context()
    context.update({
        'goat': goat, 'logs': logs, 'medical_records': medical_records,
        'feeding_logs': feeding_logs, 'breeding_logs': breeding_logs,
        'milk_logs': milk_logs, 'weight_logs': weight_logs.order_by('-date'),
        'weight_chart_data': json.dumps(weight_chart_data),
        'milk_chart_data': json.dumps(milk_chart_data),
        'latest_weight': latest_weight,
        'medicines_json': json.dumps(list(medicines)),
        'gallery_photos': gallery_photos,
        'offspring': offspring,
        'health_scores': health_scores,
        'health_chart_data': health_chart_data,
        'heat_observations': heat_observations,
        'documents': documents,
        'current_pen': current_pen,
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
        messages.success(request, 'Weight recorded.')
    return redirect('goat_detail', goat_id=goat.id)

def add_medical_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        record_type = request.POST.get('record_type')
        record_date = request.POST.get('date')
        MedicalRecord.objects.create(
            goat=goat,
            record_type=record_type,
            date=record_date,
            notes=request.POST.get('notes'),
            next_due_date=request.POST.get('next_due_date') or None
        )
        # Auto-update matching medical schedule
        matching_schedules = MedicalSchedule.objects.filter(
            Q(goat=goat) | Q(goat__isnull=True),
            record_type=record_type,
        )
        for schedule in matching_schedules:
            schedule.last_performed = record_date
            schedule.save()
        messages.success(request, 'Medical record added.')
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
        messages.success(request, 'Feeding record added.')
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
        messages.success(request, 'Breeding record added.')
    return redirect('goat_detail', goat_id=goat.id)

def update_goat_status(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        goat.status = request.POST.get('status', 'Healthy')
        goat.save()
        messages.success(request, f'Status updated to {goat.status}.')
    return redirect('goat_detail', goat_id=goat.id)

def delete_goat(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        goat.delete()
        messages.success(request, 'Goat deleted.')
        return redirect('index')
    return redirect('goat_detail', goat_id=goat.id)

def save_grazing_area(request):
    if request.method == 'POST':
        GrazingArea.objects.create(
            name=request.POST.get('area_name'),
            color=request.POST.get('area_color'),
            coordinates=request.POST.get('area_coords')
        )
        messages.success(request, 'Grazing area saved.')
    return redirect('index')

@require_POST
def toggle_task(request, task_id):
    task = get_object_or_404(DailyTask, pk=task_id)
    today = timezone.now().date()
    completion, created = TaskCompletion.objects.get_or_create(task=task, date=today)
    if created:
        completion.completed = True
    else:
        completion.completed = not completion.completed
    completion.save()
    # Support AJAX calls
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'status': 'success', 'completed': completion.completed})
    return redirect('index')

def sales_list(request):
    sales = Sale.objects.all().order_by('-sale_date')
    total_revenue = sales.aggregate(Sum('sale_price'))['sale_price__sum'] or 0
    pending_agg = sales.filter(is_paid_in_full=False).aggregate(
        total_price=Sum('sale_price'), total_deposits=Sum('deposit_amount')
    )
    pending_revenue = (pending_agg['total_price'] or 0) - (pending_agg['total_deposits'] or 0)
    customers = Customer.objects.all().order_by('name')
    goats = Goat.objects.all()
    context = get_common_context()
    context.update({
        'sales': sales,
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'customers': customers,
        'goats': goats,
    })
    return render(request, 'farm/sales_list.html', context)

def meat_locker(request):
    harvests = MeatHarvest.objects.all().order_by('-harvest_date')
    
    # Handle Form Submission
    if request.method == 'POST':
        form = MeatHarvestForm(request.POST)
        if form.is_valid():
            harvest = form.save()
            # Optional: Auto-mark goat as Deceased/Archived
            goat = harvest.goat
            goat.status = 'Deceased' # Or 'Harvested' if you add that option
            goat.save()
            messages.success(request, 'Harvest recorded.')
            return redirect('meat_locker')
    else:
        form = MeatHarvestForm()

    # Calculate Stats
    total_hanging = harvests.aggregate(Sum('hanging_weight'))['hanging_weight__sum'] or 0

    # Calc Average Yield manually since it's a property, not a DB field
    yields = [h.yield_percentage for h in harvests if h.live_weight > 0]
    avg_yield = sum(yields) / len(yields) if yields else 0

    context = get_common_context()
    context.update({
        'harvests': harvests,
        'form': form,
        'total_hanging': round(total_hanging, 1),
        'avg_yield': round(avg_yield, 1),
        'total_count': harvests.count()
    })
    return render(request, 'farm/meat_locker.html', context)


# --- PIN GATE ---
def pin_login(request):
    from .forms import PinForm
    error = None
    if request.method == 'POST':
        form = PinForm(request.POST)
        if form.is_valid():
            entered_pin = form.cleaned_data['pin']
            if entered_pin == django_settings.FARM_PIN:
                request.session['pin_authenticated'] = True
                return redirect('index')
            else:
                error = 'Incorrect PIN'
    else:
        form = PinForm()
    return render(request, 'farm/pin_login.html', {'form': form, 'error': error})


def pin_logout(request):
    request.session.pop('pin_authenticated', None)
    return redirect('pin_login')


# --- ADD GOAT ---
def add_goat(request):
    from .forms import GoatForm
    if request.method == 'POST':
        form = GoatForm(request.POST, request.FILES)
        if form.is_valid():
            goat = form.save()
            messages.success(request, f'{goat.name} added to herd!')
            return redirect('goat_detail', goat_id=goat.id)
    else:
        form = GoatForm()
    context = get_common_context()
    context['form'] = form
    return render(request, 'farm/add_goat.html', context)


# --- CSV EXPORTS ---
def export_goats_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="goats_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Breed', 'Gender', 'Status', 'Birthdate', 'Age', 'Is Fainting', 'Dam', 'Sire', 'Bio'])
    for goat in Goat.objects.select_related('dam', 'sire').all():
        writer.writerow([
            goat.name, goat.breed, goat.gender,
            goat.status, goat.birthdate, goat.display_age,
            goat.is_fainting,
            goat.dam.name if goat.dam else '',
            goat.sire.name if goat.sire else '',
            goat.bio
        ])
    return response


def export_finances_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="finances_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Description'])
    for t in Transaction.objects.all():
        writer.writerow([t.date, t.type, t.category, t.amount, t.description])
    return response


def export_milk_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="milk_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Goat', 'Amount (lbs)', 'Notes'])
    for log in MilkLog.objects.select_related('goat').all():
        writer.writerow([log.date, log.time, log.goat.name, log.amount, log.notes])
    return response


def export_medical_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="medical_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Goat', 'Type', 'Notes', 'Next Due Date'])
    for r in MedicalRecord.objects.select_related('goat').all():
        writer.writerow([r.date, r.goat.name, r.record_type, r.notes, r.next_due_date])
    return response


# --- VET CRUD ---
def add_vet(request):
    if request.method == 'POST':
        Vet.objects.create(
            name=request.POST.get('name'),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            email=request.POST.get('email', '')
        )
        messages.success(request, 'Vet contact added.')
    return redirect('index')


@require_POST
def delete_vet(request, vet_id):
    vet = get_object_or_404(Vet, pk=vet_id)
    vet.delete()
    messages.success(request, 'Vet contact removed.')
    return redirect('index')


# --- DAILY TASK CRUD ---
def add_task(request):
    if request.method == 'POST':
        DailyTask.objects.create(
            name=request.POST.get('name'),
            time_of_day=request.POST.get('time_of_day', 'ANY')
        )
        messages.success(request, 'Task added.')
    return redirect('index')


@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(DailyTask, pk=task_id)
    task.delete()
    messages.success(request, 'Task removed.')
    return redirect('index')


# --- FEED ITEM CRUD ---
def add_feed_item(request):
    if request.method == 'POST':
        FeedItem.objects.create(
            name=request.POST.get('name'),
            quantity=request.POST.get('quantity', 0),
            unit=request.POST.get('unit', 'lbs'),
            low_stock_threshold=request.POST.get('low_stock_threshold', 5)
        )
        messages.success(request, 'Feed item added to silo.')
    return redirect('silo_dashboard')


@require_POST
def delete_feed_item(request, item_id):
    item = get_object_or_404(FeedItem, pk=item_id)
    item.delete()
    messages.success(request, 'Feed item removed.')
    return redirect('silo_dashboard')


# --- EDIT GOAT ---
def edit_goat(request, goat_id):
    from .forms import GoatForm
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        form = GoatForm(request.POST, request.FILES, instance=goat)
        if form.is_valid():
            form.save()
            messages.success(request, f'{goat.name} updated.')
            return redirect('goat_detail', goat_id=goat.id)
    else:
        form = GoatForm(instance=goat)
    context = get_common_context()
    context.update({'form': form, 'goat': goat})
    return render(request, 'farm/edit_goat.html', context)


# --- DELETE RECORD VIEWS ---
@require_POST
def delete_medical_record(request, record_id):
    record = get_object_or_404(MedicalRecord, pk=record_id)
    goat_id = record.goat_id
    record.delete()
    messages.success(request, 'Medical record deleted.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_milk_log(request, log_id):
    log = get_object_or_404(MilkLog, pk=log_id)
    goat_id = log.goat_id
    log.delete()
    messages.success(request, 'Milk log deleted.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_weight_log(request, log_id):
    log = get_object_or_404(WeightLog, pk=log_id)
    goat_id = log.goat_id
    log.delete()
    messages.success(request, 'Weight record deleted.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_feeding_log(request, log_id):
    log = get_object_or_404(FeedingLog, pk=log_id)
    goat_id = log.goat_id
    log.delete()
    messages.success(request, 'Feeding record deleted.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_breeding_log(request, log_id):
    log = get_object_or_404(BreedingLog, pk=log_id)
    goat_id = log.goat_id
    log.delete()
    messages.success(request, 'Breeding record deleted.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_goat_log(request, log_id):
    log = get_object_or_404(GoatLog, pk=log_id)
    goat_id = log.goat_id
    log.delete()
    messages.success(request, 'Log entry deleted.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_goat_photo(request, photo_id):
    photo = get_object_or_404(GoatPhoto, pk=photo_id)
    goat_id = photo.goat_id
    photo.delete()
    messages.success(request, 'Photo removed.')
    return redirect('goat_detail', goat_id=goat_id)


@require_POST
def delete_transaction(request, txn_id):
    txn = get_object_or_404(Transaction, pk=txn_id)
    txn.delete()
    messages.success(request, 'Transaction deleted.')
    return redirect('finance_dashboard')


# --- SALES CRUD ---
def add_sale(request):
    if request.method == 'POST':
        Sale.objects.create(
            customer_id=request.POST.get('customer'),
            goat_id=request.POST.get('goat'),
            sale_date=request.POST.get('sale_date'),
            sale_price=request.POST.get('sale_price'),
            deposit_amount=request.POST.get('deposit_amount') or 0,
            is_paid_in_full='is_paid_in_full' in request.POST,
            notes=request.POST.get('notes', '')
        )
        messages.success(request, 'Sale recorded.')
    return redirect('sales_list')


@require_POST
def toggle_sale_paid(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    sale.is_paid_in_full = not sale.is_paid_in_full
    sale.save()
    messages.success(request, f'Sale marked as {"Paid" if sale.is_paid_in_full else "Pending"}.')
    return redirect('sales_list')


@require_POST
def delete_sale(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    sale.delete()
    messages.success(request, 'Sale deleted.')
    return redirect('sales_list')


# --- CUSTOMER CRUD ---
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    if request.method == 'POST':
        customer.name = request.POST.get('name', customer.name)
        customer.email = request.POST.get('email', customer.email)
        customer.phone = request.POST.get('phone', customer.phone)
        customer.notes = request.POST.get('notes', customer.notes)
        customer.save()
        messages.success(request, 'Customer updated.')
    return redirect('crm_dashboard')


@require_POST
def delete_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    customer.delete()
    messages.success(request, 'Customer deleted.')
    return redirect('crm_dashboard')


# =====================================================
# PHASE 2: MAP ENHANCEMENTS (Features 1-6)
# =====================================================

# Feature 1: Grazing Rotation
def assign_pasture(request):
    if request.method == 'POST':
        area_id = request.POST.get('grazing_area')
        goat_ids = request.POST.getlist('goats')
        start_date = request.POST.get('start_date') or timezone.now().date()
        notes = request.POST.get('notes', '')

        assignment = PastureAssignment.objects.create(
            grazing_area_id=area_id,
            start_date=start_date,
            notes=notes,
        )
        assignment.goats.set(goat_ids)
        messages.success(request, 'Goats assigned to pasture.')
    return redirect('index')


@require_POST
def end_pasture_assignment(request, assignment_id):
    assignment = get_object_or_404(PastureAssignment, pk=assignment_id)
    assignment.end_date = timezone.now().date()
    assignment.save()
    messages.success(request, 'Rotation ended.')
    return redirect('index')


def api_rotation_history(request, area_id):
    area = get_object_or_404(GrazingArea, pk=area_id)
    assignments = area.assignments.all()[:20]
    history = []
    for a in assignments:
        history.append({
            'id': a.id,
            'start_date': a.start_date.isoformat(),
            'end_date': a.end_date.isoformat() if a.end_date else None,
            'is_active': a.is_active,
            'goats': [g.name for g in a.goats.all()],
            'notes': a.notes,
        })
    return JsonResponse({'history': history, 'days_resting': area.days_resting})


# Feature 3: Map Markers
def add_map_marker(request):
    if request.method == 'POST':
        MapMarker.objects.create(
            name=request.POST.get('name'),
            marker_type=request.POST.get('marker_type', 'Other'),
            latitude=float(request.POST.get('latitude', 0)),
            longitude=float(request.POST.get('longitude', 0)),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Map marker added.')
    return redirect('index')


@require_POST
def delete_map_marker(request, marker_id):
    marker = get_object_or_404(MapMarker, pk=marker_id)
    marker.delete()
    messages.success(request, 'Map marker removed.')
    return redirect('index')


# Feature 4: Pasture Condition
def add_pasture_condition(request, area_id):
    area = get_object_or_404(GrazingArea, pk=area_id)
    if request.method == 'POST':
        PastureCondition.objects.create(
            grazing_area=area,
            date=request.POST.get('date') or timezone.now().date(),
            score=int(request.POST.get('score', 3)),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Condition score recorded.')
    return redirect('index')


def api_pasture_conditions(request, area_id):
    conditions = PastureCondition.objects.filter(grazing_area_id=area_id).order_by('date')[:50]
    data = {
        'dates': [c.date.isoformat() for c in conditions],
        'scores': [c.score for c in conditions],
    }
    return JsonResponse(data)


# Feature 5: Drawing Tool Improvements
@require_POST
def update_grazing_area(request, area_id):
    try:
        data = json.loads(request.body)
        area = get_object_or_404(GrazingArea, pk=area_id)
        if 'coordinates' in data:
            area.coordinates = json.dumps(data['coordinates'])
        if 'name' in data:
            area.name = data['name']
        if 'color' in data:
            area.color = data['color']
        area.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_POST
def delete_grazing_area(request, area_id):
    try:
        area = get_object_or_404(GrazingArea, pk=area_id)
        area.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# =====================================================
# DEDICATED MAP PAGE + KML EXPORT
# =====================================================

def map_dashboard(request):
    """Dedicated full-screen map page with all tools and collapsible panels."""
    context = get_common_context()
    today = timezone.now().date()
    goats = Goat.objects.all()
    grazing_areas = GrazingArea.objects.all()

    areas_list = []
    for area in grazing_areas:
        try:
            active = area.active_assignment
            goat_names, goat_count = [], 0
            if active:
                assigned_goats = active.goats.all()
                goat_count = assigned_goats.count()
                goat_names = [g.name for g in assigned_goats]
            latest_cond = area.latest_condition
            areas_list.append({
                'id': area.id, 'name': area.name, 'color': area.color,
                'coords': json.loads(area.coordinates),
                'goat_count': goat_count, 'goat_names': goat_names,
                'days_resting': area.days_resting,
                'condition_score': latest_cond.score if latest_cond else None,
            })
        except (json.JSONDecodeError, TypeError):
            pass

    markers_list = list(MapMarker.objects.all().values('id', 'name', 'marker_type', 'latitude', 'longitude', 'notes'))
    active_assignments = PastureAssignment.objects.filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).select_related('grazing_area').prefetch_related('goats')

    ninety_days_ago = today - timedelta(days=90)
    rotation_history = PastureAssignment.objects.filter(
        Q(start_date__gte=ninety_days_ago) | Q(end_date__gte=ninety_days_ago) | Q(end_date__isnull=True)
    ).select_related('grazing_area').prefetch_related('goats').order_by('start_date')
    rotation_timeline = []
    for a in rotation_history:
        rotation_timeline.append({
            'area_name': a.grazing_area.name, 'color': a.grazing_area.color,
            'start_date': a.start_date.isoformat(),
            'end_date': a.end_date.isoformat() if a.end_date else None,
            'goats': [g.name for g in a.goats.all()],
        })

    context.update({
        'goats': goats,
        'grazing_areas': areas_list,
        'map_markers': markers_list,
        'active_assignments': active_assignments,
        'all_grazing_areas': grazing_areas,
        'rotation_timeline_data': rotation_timeline,
    })
    return render(request, 'farm/map.html', context)


def export_grazing_areas_kml(request):
    """Export all grazing areas as KML for Google Earth / GIS tools."""
    areas = GrazingArea.objects.all()
    kml_placemarks = []
    for area in areas:
        try:
            coords = json.loads(area.coordinates)
        except (json.JSONDecodeError, TypeError):
            continue
        coord_str = ' '.join(f"{c['lng']},{c['lat']},0" for c in coords)
        if coords:
            coord_str += f" {coords[0]['lng']},{coords[0]['lat']},0"
        latest_cond = area.latest_condition
        cond_text = f"Condition: {latest_cond.score}/5" if latest_cond else "No condition data"
        hex_color = area.color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            kml_color = f'88{b}{g}{r}'
        else:
            kml_color = '880000ff'
        kml_placemarks.append(f"""    <Placemark>
      <name>{area.name}</name>
      <description>{cond_text}</description>
      <Style>
        <PolyStyle><color>{kml_color}</color></PolyStyle>
        <LineStyle><color>ff{hex_color[4:6]}{hex_color[2:4]}{hex_color[0:2]}</color><width>2</width></LineStyle>
      </Style>
      <Polygon>
        <outerBoundaryIs><LinearRing>
            <coordinates>{coord_str}</coordinates>
        </LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>""")

    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>GoatOS Grazing Areas</name>
{''.join(kml_placemarks)}
  </Document>
</kml>"""
    response = HttpResponse(kml_content, content_type='application/vnd.google-earth.kml+xml')
    response['Content-Disposition'] = 'attachment; filename="grazing_areas.kml"'
    return response


# =====================================================
# PHASE 3: HERD ANALYTICS DASHBOARD (Feature 7)
# =====================================================

def analytics_dashboard(request):
    goats = Goat.objects.all()
    today = timezone.now().date()

    # Breed distribution
    breed_data = list(goats.values('breed').annotate(count=Count('id')).order_by('-count'))

    # Gender distribution
    gender_data = list(goats.values('gender').annotate(count=Count('id')).order_by('-count'))

    # Status distribution
    status_data = list(goats.values('status').annotate(count=Count('id')).order_by('-count'))

    # Age distribution (buckets)
    age_buckets = {'0-1': 0, '1-2': 0, '2-3': 0, '3-5': 0, '5+': 0}
    for g in goats:
        days = g.age_in_days
        years = days / 365
        if years < 1:
            age_buckets['0-1'] += 1
        elif years < 2:
            age_buckets['1-2'] += 1
        elif years < 3:
            age_buckets['2-3'] += 1
        elif years < 5:
            age_buckets['3-5'] += 1
        else:
            age_buckets['5+'] += 1

    # Monthly milk production (last 12 months)
    twelve_months_ago = today - timedelta(days=365)
    milk_monthly = (
        MilkLog.objects.filter(date__gte=twelve_months_ago)
        .extra(select={'month': "strftime('%%Y-%%m', date)"})
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    # Breeding stats
    total_breedings = BreedingLog.objects.count()
    # Count goats that have offspring (successful kiddings)
    successful_dams = Goat.objects.filter(kids_dam__isnull=False).distinct().count()
    successful_sires = Goat.objects.filter(kids_sire__isnull=False).distinct().count()

    context = get_common_context()
    context.update({
        'total_goats': goats.count(),
        'breed_data': json.dumps(breed_data),
        'gender_data': json.dumps(gender_data),
        'status_data': json.dumps(status_data),
        'age_buckets': json.dumps(age_buckets),
        'milk_monthly': json.dumps(list(milk_monthly)),
        'total_breedings': total_breedings,
        'successful_dams': successful_dams,
    })
    return render(request, 'farm/analytics.html', context)


# =====================================================
# PHASE 4: RECURRING MEDICAL SCHEDULES (Feature 8)
# =====================================================

def add_medical_schedule(request):
    if request.method == 'POST':
        goat_id = request.POST.get('goat') or None
        MedicalSchedule.objects.create(
            goat_id=goat_id,
            record_type=request.POST.get('record_type'),
            interval_days=int(request.POST.get('interval_days', 56)),
            last_performed=request.POST.get('last_performed') or timezone.now().date(),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Medical schedule created.')
    return redirect('medicine_dashboard')


@require_POST
def delete_medical_schedule(request, schedule_id):
    schedule = get_object_or_404(MedicalSchedule, pk=schedule_id)
    schedule.delete()
    messages.success(request, 'Schedule removed.')
    return redirect('medicine_dashboard')


# =====================================================
# PHASE 6: BACKUP/RESTORE (Feature 12)
# =====================================================

def backup_database(request):
    db_path = django_settings.DATABASES['default']['NAME']
    if not os.path.exists(str(db_path)):
        messages.error(request, 'Database file not found.')
        return redirect('tools_dashboard')

    response = HttpResponse(content_type='application/x-sqlite3')
    response['Content-Disposition'] = 'attachment; filename="goatos_backup.sqlite3"'
    with open(str(db_path), 'rb') as f:
        response.write(f.read())
    return response


def backup_media(request):
    media_root = str(django_settings.MEDIA_ROOT)
    if not os.path.exists(media_root):
        messages.error(request, 'Media directory not found.')
        return redirect('tools_dashboard')

    response = HttpResponse(content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="goatos_media_backup.zip"'

    with zipfile.ZipFile(response, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(media_root):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, media_root)
                zf.write(file_path, arcname)
    return response


def restore_database(request):
    if request.method == 'POST' and request.FILES.get('db_file'):
        uploaded = request.FILES['db_file']

        # Basic validation: check it's a valid SQLite file
        header = uploaded.read(16)
        uploaded.seek(0)
        if header[:16] != b'SQLite format 3\x00':
            messages.error(request, 'Invalid file. Must be a valid SQLite database.')
            return redirect('tools_dashboard')

        db_path = str(django_settings.DATABASES['default']['NAME'])

        # Write the uploaded file
        with open(db_path, 'wb') as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        messages.success(request, 'Database restored. Please restart the server for changes to take full effect.')
        return redirect('tools_dashboard')

    messages.error(request, 'No file uploaded.')
    return redirect('tools_dashboard')


# =====================================================
# PWA SERVICE WORKER (Feature 11)
# =====================================================

def service_worker(request):
    sw_content = """
var CACHE_NAME = 'goatos-v1';
var urlsToCache = ['/static/farm/manifest.json'];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(urlsToCache);
        })
    );
});

self.addEventListener('fetch', function(event) {
    event.respondWith(
        fetch(event.request).catch(function() {
            return caches.match(event.request).then(function(response) {
                return response || new Response('<h1>GoatOS Offline</h1><p>Please check your connection.</p>', {
                    headers: {'Content-Type': 'text/html'}
                });
            });
        })
    );
});
"""
    return HttpResponse(sw_content, content_type='application/javascript')


# =====================================================
# FEATURE 1: KIDDING RECORDS
# =====================================================

def add_kidding_record(request):
    if request.method == 'POST':
        dam_id = request.POST.get('dam_id')
        breeding_log_id = request.POST.get('breeding_log_id')
        dam = get_object_or_404(Goat, pk=dam_id)

        record = KiddingRecord.objects.create(
            dam=dam,
            breeding_log_id=breeding_log_id if breeding_log_id else None,
            kidding_date=request.POST.get('kidding_date') or date.today(),
            num_kids_born=request.POST.get('num_kids_born', 1),
            num_alive=request.POST.get('num_alive', 1),
            num_stillborn=request.POST.get('num_stillborn', 0),
            birth_type=request.POST.get('birth_type', 'Single'),
            presentation=request.POST.get('presentation', 'Normal'),
            assisted='assisted' in request.POST,
            complications=request.POST.get('complications', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Kidding record added for {dam.name}.')
        return redirect(request.POST.get('next', 'breeding_dashboard'))
    return redirect('breeding_dashboard')


@require_POST
def delete_kidding_record(request, record_id):
    record = get_object_or_404(KiddingRecord, pk=record_id)
    record.delete()
    messages.success(request, 'Kidding record deleted.')
    return redirect('breeding_dashboard')


# =====================================================
# FEATURE 4: KIDDING SEASON DASHBOARD
# =====================================================

def kidding_season_dashboard(request):
    today = date.today()
    # Get all breeding logs with future or recent due dates
    pregnant_does = BreedingLog.objects.filter(
        due_date__isnull=False,
        due_date__gte=today - timedelta(days=14)  # Include up to 2 weeks overdue
    ).select_related('goat').order_by('due_date')

    for log in pregnant_does:
        log.days_until = (log.due_date - today).days
        if log.days_until < -7:
            log.urgency = 'overdue'
        elif log.days_until < 0:
            log.urgency = 'overdue'
        elif log.days_until <= 7:
            log.urgency = 'this-week'
        elif log.days_until <= 14:
            log.urgency = 'two-weeks'
        else:
            log.urgency = 'later'

    recent_kiddings = KiddingRecord.objects.select_related('dam', 'breeding_log').order_by('-kidding_date')[:20]
    does = Goat.objects.filter(gender__in=['Doe', 'Doeling'])
    breeding_logs = BreedingLog.objects.filter(due_date__gte=today - timedelta(days=30)).select_related('goat')

    context = get_common_context()
    context.update({
        'pregnant_does': pregnant_does,
        'recent_kiddings': recent_kiddings,
        'does': does,
        'breeding_logs': breeding_logs,
    })
    return render(request, 'farm/kidding_season.html', context)


# =====================================================
# FEATURE 2: FAMACHA & BODY CONDITION SCORING
# =====================================================

def add_health_score(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        HealthScore.objects.create(
            goat=goat,
            date=request.POST.get('date') or date.today(),
            famacha_score=request.POST.get('famacha_score') or None,
            body_condition_score=request.POST.get('body_condition_score') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Health score recorded for {goat.name}.')
        return redirect('goat_detail', goat_id=goat.id)
    return redirect('goat_detail', goat_id=goat.id)


@require_POST
def delete_health_score(request, score_id):
    score = get_object_or_404(HealthScore, pk=score_id)
    goat_id = score.goat.id
    score.delete()
    messages.success(request, 'Health score deleted.')
    return redirect('goat_detail', goat_id=goat_id)


def health_scores_dashboard(request):
    """Herd-wide FAMACHA & BCS overview"""
    goats = Goat.objects.filter(status='Healthy').order_by('name')
    scores_data = []
    for goat in goats:
        latest = goat.health_scores.first()
        scores_data.append({
            'goat': goat,
            'latest_famacha': latest.famacha_score if latest else None,
            'latest_bcs': latest.body_condition_score if latest else None,
            'latest_date': latest.date if latest else None,
        })

    context = get_common_context()
    context.update({'scores_data': scores_data})
    return render(request, 'farm/health_scores.html', context)


# =====================================================
# FEATURE 3: HEAT DETECTION / ESTRUS
# =====================================================

def add_heat_observation(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        HeatObservation.objects.create(
            goat=goat,
            date_observed=request.POST.get('date_observed') or date.today(),
            signs=request.POST.get('signs', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Heat observation recorded for {goat.name}.')
        return redirect('goat_detail', goat_id=goat.id)
    return redirect('goat_detail', goat_id=goat.id)


@require_POST
def delete_heat_observation(request, observation_id):
    obs = get_object_or_404(HeatObservation, pk=observation_id)
    goat_id = obs.goat.id
    obs.delete()
    messages.success(request, 'Heat observation deleted.')
    return redirect('goat_detail', goat_id=goat_id)


# =====================================================
# FEATURE 5: ACTIVITY FEED / FARM TIMELINE
# =====================================================

def activity_feed(request):
    """Unified chronological feed of ALL farm activity"""
    limit = int(request.GET.get('limit', 100))
    filter_type = request.GET.get('type', 'all')

    activities = []

    def add_activities(queryset, activity_type, icon, color, label_fn, detail_fn, goat_fn, date_fn):
        for obj in queryset:
            activities.append({
                'type': activity_type,
                'icon': icon,
                'color': color,
                'label': label_fn(obj),
                'detail': detail_fn(obj),
                'goat': goat_fn(obj),
                'date': date_fn(obj),
                'obj': obj,
            })

    type_filters = filter_type.split(',') if filter_type != 'all' else None

    if not type_filters or 'medical' in type_filters:
        add_activities(
            MedicalRecord.objects.select_related('goat').order_by('-date')[:limit],
            'medical', '🏥', '#e91e63',
            lambda o: o.get_record_type_display(),
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.goat, lambda o: o.date)

    if not type_filters or 'milk' in type_filters:
        add_activities(
            MilkLog.objects.select_related('goat').order_by('-date')[:limit],
            'milk', '🥛', '#2196f3',
            lambda o: f'{o.amount} lbs ({o.time})',
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.goat, lambda o: o.date)

    if not type_filters or 'breeding' in type_filters:
        add_activities(
            BreedingLog.objects.select_related('goat').order_by('-breeding_date')[:limit],
            'breeding', '🧬', '#9c27b0',
            lambda o: f'Bred with {o.mate_name}',
            lambda o: f'Due: {o.due_date}' if o.due_date else '',
            lambda o: o.goat, lambda o: o.breeding_date)

    if not type_filters or 'weight' in type_filters:
        add_activities(
            WeightLog.objects.select_related('goat').order_by('-date')[:limit],
            'weight', '⚖️', '#009688',
            lambda o: f'{o.weight} lbs',
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.goat, lambda o: o.date)

    if not type_filters or 'feeding' in type_filters:
        add_activities(
            FeedingLog.objects.select_related('goat').order_by('-date')[:limit],
            'feeding', '🌾', '#ff9800',
            lambda o: f'{o.feed_type} - {o.amount}',
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.goat, lambda o: o.date)

    if not type_filters or 'kidding' in type_filters:
        add_activities(
            KiddingRecord.objects.select_related('dam').order_by('-kidding_date')[:limit],
            'kidding', '🐣', '#4caf50',
            lambda o: f'{o.birth_type} - {o.num_alive} alive',
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.dam, lambda o: o.kidding_date)

    if not type_filters or 'health' in type_filters:
        add_activities(
            HealthScore.objects.select_related('goat').order_by('-date')[:limit],
            'health', '🩺', '#ff5722',
            lambda o: f'FAMACHA:{o.famacha_score or "-"} BCS:{o.body_condition_score or "-"}',
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.goat, lambda o: o.date)

    if not type_filters or 'heat' in type_filters:
        add_activities(
            HeatObservation.objects.select_related('goat').order_by('-date_observed')[:limit],
            'heat', '🔥', '#e91e63',
            lambda o: f'Heat observed - {o.signs or "no signs noted"}',
            lambda o: o.notes[:100] if o.notes else '',
            lambda o: o.goat, lambda o: o.date_observed)

    if not type_filters or 'finance' in type_filters:
        add_activities(
            Transaction.objects.order_by('-date')[:limit],
            'finance', '💰', '#795548',
            lambda o: f'{o.type}: ${o.amount} ({o.category})',
            lambda o: o.description[:100] if o.description else '',
            lambda o: o.goat, lambda o: o.date)

    # Sort all activities by date descending
    activities.sort(key=lambda a: a['date'] if a['date'] else date.min, reverse=True)
    activities = activities[:limit]

    context = get_common_context()
    context.update({
        'activities': activities,
        'filter_type': filter_type,
        'limit': limit,
    })
    return render(request, 'farm/activity.html', context)


# =====================================================
# FEATURE 6: COST-PER-GOAT ANALYSIS
# =====================================================

def cost_analysis(request):
    goats = Goat.objects.all()
    analysis = []

    for goat in goats:
        expenses = goat.transactions.filter(type='Expense').aggregate(total=Sum('amount'))['total'] or 0
        income = goat.transactions.filter(type='Income').aggregate(total=Sum('amount'))['total'] or 0
        # Also count sale income
        sale_income = goat.sales.aggregate(total=Sum('sale_price'))['total'] or 0
        total_income = float(income) + float(sale_income)
        total_expenses = float(expenses)
        net = total_income - total_expenses

        if total_expenses > 0 or total_income > 0:
            analysis.append({
                'goat': goat,
                'expenses': total_expenses,
                'income': total_income,
                'net': net,
                'feed_cost': float(goat.transactions.filter(type='Expense', category='Feed').aggregate(total=Sum('amount'))['total'] or 0),
                'vet_cost': float(goat.transactions.filter(type='Expense', category='Vet').aggregate(total=Sum('amount'))['total'] or 0),
                'equip_cost': float(goat.transactions.filter(type='Expense', category='Equipment').aggregate(total=Sum('amount'))['total'] or 0),
            })

    # Sort by net (most profitable first)
    analysis.sort(key=lambda a: a['net'], reverse=True)

    # Herd-wide totals
    total_herd_expenses = sum(a['expenses'] for a in analysis)
    total_herd_income = sum(a['income'] for a in analysis)
    total_herd_net = total_herd_income - total_herd_expenses

    # Chart data: top 10 most expensive
    top_expensive = sorted(analysis, key=lambda a: a['expenses'], reverse=True)[:10]
    chart_labels = json.dumps([a['goat'].name for a in top_expensive])
    chart_expenses = json.dumps([a['expenses'] for a in top_expensive])
    chart_income = json.dumps([a['income'] for a in top_expensive])

    context = get_common_context()
    context.update({
        'analysis': analysis,
        'total_herd_expenses': total_herd_expenses,
        'total_herd_income': total_herd_income,
        'total_herd_net': total_herd_net,
        'chart_labels': chart_labels,
        'chart_expenses': chart_expenses,
        'chart_income': chart_income,
        'goats': goats,
    })
    return render(request, 'farm/cost_analysis.html', context)


# =====================================================
# FEATURE 7: DOCUMENT VAULT
# =====================================================

def add_goat_document(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded = request.FILES['file']
        if uploaded.size > 20 * 1024 * 1024:  # 20MB limit
            messages.error(request, 'File too large. Maximum 20MB.')
            return redirect('goat_detail', goat_id=goat.id)
        GoatDocument.objects.create(
            goat=goat,
            file=uploaded,
            title=request.POST.get('title', uploaded.name),
            doc_type=request.POST.get('doc_type', 'Other'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Document uploaded for {goat.name}.')
    return redirect('goat_detail', goat_id=goat.id)


@require_POST
def delete_goat_document(request, doc_id):
    doc = get_object_or_404(GoatDocument, pk=doc_id)
    goat_id = doc.goat.id
    doc.file.delete()
    doc.delete()
    messages.success(request, 'Document deleted.')
    return redirect('goat_detail', goat_id=goat_id)


# =====================================================
# FEATURE 8: SUPPLIER / VENDOR DATABASE
# =====================================================

def suppliers_dashboard(request):
    if request.method == 'POST':
        Supplier.objects.create(
            name=request.POST.get('name'),
            contact_name=request.POST.get('contact_name', ''),
            phone=request.POST.get('phone', ''),
            email=request.POST.get('email', ''),
            address=request.POST.get('address', ''),
            category=request.POST.get('category', 'Other'),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Supplier added.')
        return redirect('suppliers_dashboard')

    suppliers = Supplier.objects.all().order_by('name')
    for s in suppliers:
        s.total_spent = s.transactions.filter(type='Expense').aggregate(total=Sum('amount'))['total'] or 0

    context = get_common_context()
    context.update({'suppliers': suppliers})
    return render(request, 'farm/suppliers.html', context)


@require_POST
def delete_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    supplier.delete()
    messages.success(request, 'Supplier deleted.')
    return redirect('suppliers_dashboard')


# =====================================================
# FEATURE 9: PEN / BARN MANAGEMENT
# =====================================================

def barn_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_pen':
            Pen.objects.create(
                name=request.POST.get('name'),
                pen_type=request.POST.get('pen_type', 'General'),
                capacity=request.POST.get('capacity', 5),
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, 'Pen added.')
        elif action == 'assign':
            pen = get_object_or_404(Pen, pk=request.POST.get('pen_id'))
            goat = get_object_or_404(Goat, pk=request.POST.get('goat_id'))
            # End any existing active assignment for this goat
            PenAssignment.objects.filter(goat=goat, date_out__isnull=True).update(date_out=date.today())
            PenAssignment.objects.create(
                pen=pen, goat=goat,
                date_in=request.POST.get('date_in') or date.today(),
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, f'{goat.name} assigned to {pen.name}.')
        elif action == 'remove':
            assignment = get_object_or_404(PenAssignment, pk=request.POST.get('assignment_id'))
            assignment.date_out = date.today()
            assignment.save()
            messages.success(request, f'{assignment.goat.name} removed from {assignment.pen.name}.')
        return redirect('barn_dashboard')

    pens = Pen.objects.all().order_by('name')
    goats = Goat.objects.filter(status__in=['Healthy', 'Sick']).order_by('name')
    # Get goats currently not assigned to any pen
    assigned_goat_ids = PenAssignment.objects.filter(date_out__isnull=True).values_list('goat_id', flat=True)
    unassigned_goats = goats.exclude(id__in=assigned_goat_ids)

    context = get_common_context()
    context.update({
        'pens': pens,
        'goats': goats,
        'unassigned_goats': unassigned_goats,
    })
    return render(request, 'farm/barn.html', context)


@require_POST
def delete_pen(request, pen_id):
    pen = get_object_or_404(Pen, pk=pen_id)
    pen.delete()
    messages.success(request, 'Pen deleted.')
    return redirect('barn_dashboard')