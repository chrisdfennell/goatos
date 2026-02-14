import csv
import json
import logging
import base64
import shutil
from io import BytesIO
from pathlib import Path

import requests
import qrcode
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, F, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from datetime import timedelta, datetime

from .constants import (
    MEDICAL_ALERT_DAYS, KIDDING_ALERT_DAYS, MONTHLY_REPORT_DAYS,
    MAX_IMAGE_UPLOAD_BYTES, WEATHER_CACHE_TTL_SECONDS, DEFAULT_PAGE_SIZE,
    CHART_DAYS_LOOKBACK, CHART_MONTHS_LOOKBACK,
    HEAT_CYCLE_DAYS, BREEDING_WINDOW_DAYS,
)
from .forms import (
    MeatHarvestForm, MilkLogForm, TransactionForm, MedicineForm,
    FarmEventForm, CustomerForm, WaitingListForm, WeightLogForm,
    FeedingLogForm, BreedingLogForm, MedicalRecordForm, GoatLogForm,
    GrazingAreaForm,
)
from .models import (
    Goat, GoatLog, GrazingArea, DailyTask, TaskCompletion, Vet,
    MedicalRecord, FarmSettings, FeedingLog, BreedingLog, FeedItem,
    MilkLog, Transaction, WeightLog, FarmEvent, Medicine, GoatPhoto,
    Customer, WaitingList, Sale, MeatHarvest,
)

logger = logging.getLogger(__name__)


# --- HELPER FUNCTIONS ---

def get_common_context():
    """Helper to get context data needed for the base template (like settings)"""
    farm_settings, _ = FarmSettings.objects.get_or_create(pk=1)
    return {'farm_settings': farm_settings}


def get_weather_data(lat, lon):
    if not lat or not lon or (lat == 0.0 and lon == 0.0):
        return None

    cache_key = f'weather_{lat}_{lon}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

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
        data = r.json()
        cache.set(cache_key, data, WEATHER_CACHE_TTL_SECONDS)
        return data
    except requests.RequestException as e:
        logger.warning("Weather API error: %s", e)
        return None


def validate_image_upload(uploaded_file):
    """Returns error message string if invalid, None if ok."""
    if not uploaded_file.content_type.startswith('image/'):
        return "File must be an image (JPEG, PNG, etc.)."
    if uploaded_file.size > MAX_IMAGE_UPLOAD_BYTES:
        return f"Image must be under {MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)}MB."
    return None


# --- DASHBOARDS ---

@login_required
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
    medical_alerts = MedicalRecord.objects.filter(
        next_due_date__isnull=False,
        next_due_date__lte=today + timedelta(days=MEDICAL_ALERT_DAYS)
    ).select_related('goat').order_by('next_due_date')
    kidding_alerts = BreedingLog.objects.filter(
        due_date__isnull=False,
        due_date__gte=today,
        due_date__lte=today + timedelta(days=KIDDING_ALERT_DAYS)
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
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Bad coordinates for grazing area '%s': %s", area.name, e)

    # 30-day summary stats
    thirty_ago = today - timedelta(days=CHART_DAYS_LOOKBACK)
    summary_milk_30 = MilkLog.objects.filter(date__gte=thirty_ago).aggregate(Sum('amount'))['amount__sum'] or 0
    summary_income_30 = Transaction.objects.filter(type='Income', date__gte=thirty_ago).aggregate(Sum('amount'))['amount__sum'] or 0
    summary_expense_30 = Transaction.objects.filter(type='Expense', date__gte=thirty_ago).aggregate(Sum('amount'))['amount__sum'] or 0

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
        'has_alerts': has_alerts,
        'summary_milk_30': summary_milk_30,
        'summary_income_30': summary_income_30,
        'summary_expense_30': summary_expense_30,
    })
    return render(request, 'farm/index.html', context)


@login_required
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
        except ValueError as e:
            logger.warning("Invalid lat/lng in settings update: %s", e)
        settings.save()
    return redirect('index')


@login_required
def milk_dashboard(request):
    if request.method == 'POST':
        form = MilkLogForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('milk_dashboard')

    logs = MilkLog.objects.all().order_by('-date', '-time')
    total_all_time = logs.aggregate(Sum('amount'))['amount__sum'] or 0
    thirty_days_ago = timezone.now().date() - timedelta(days=MONTHLY_REPORT_DAYS)
    monthly_logs = logs.filter(date__gte=thirty_days_ago)
    total_30_days = monthly_logs.aggregate(Sum('amount'))['amount__sum'] or 0
    goats = Goat.objects.all()

    paginator = Paginator(logs, DEFAULT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Chart: daily totals for last 30 days
    chart_start = timezone.now().date() - timedelta(days=CHART_DAYS_LOOKBACK)
    daily_totals = (
        MilkLog.objects.filter(date__gte=chart_start)
        .values('date').annotate(total=Sum('amount'))
        .order_by('date')
    )
    milk_chart = {
        'labels': [d['date'].strftime('%b %d') for d in daily_totals],
        'data': [float(d['total']) for d in daily_totals],
    }

    context = get_common_context()
    context.update({
        'page_obj': page_obj,
        'total_all_time': total_all_time,
        'total_30_days': total_30_days,
        'goats': goats,
        'milk_chart_json': json.dumps(milk_chart),
    })
    return render(request, 'farm/milk.html', context)


@login_required
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


@login_required
def silo_dashboard(request):
    feed_items = FeedItem.objects.all().order_by('name')
    context = get_common_context()
    context.update({'feed_items': feed_items})
    return render(request, 'farm/silo.html', context)


@login_required
def update_inventory(request, item_id):
    item = get_object_or_404(FeedItem, pk=item_id)
    if request.method == 'POST':
        try:
            item.quantity = F('quantity') + float(request.POST.get('amount', 0))
            item.save()
        except (ValueError, TypeError) as e:
            logger.warning("Invalid inventory amount: %s", e)
    return redirect('silo_dashboard')


@login_required
def finance_dashboard(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance_dashboard')

    transactions = Transaction.objects.all()
    total_income = transactions.filter(type='Income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = transactions.filter(type='Expense').aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = total_income - total_expense

    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    month_income = transactions.filter(type='Income', date__gte=current_month_start).aggregate(Sum('amount'))['amount__sum'] or 0
    month_expense = transactions.filter(type='Expense', date__gte=current_month_start).aggregate(Sum('amount'))['amount__sum'] or 0

    paginator = Paginator(transactions, DEFAULT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Chart: monthly income vs expense for last 12 months
    chart_start = (today.replace(day=1) - timedelta(days=CHART_MONTHS_LOOKBACK * 30)).replace(day=1)
    monthly_data = (
        Transaction.objects.filter(date__gte=chart_start)
        .annotate(month=TruncMonth('date'))
        .values('month', 'type')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    months_set = sorted({d['month'] for d in monthly_data})
    income_by_month = {d['month']: float(d['total']) for d in monthly_data if d['type'] == 'Income'}
    expense_by_month = {d['month']: float(d['total']) for d in monthly_data if d['type'] == 'Expense'}
    finance_chart = {
        'labels': [m.strftime('%b %Y') for m in months_set],
        'income': [income_by_month.get(m, 0) for m in months_set],
        'expense': [expense_by_month.get(m, 0) for m in months_set],
    }

    context = get_common_context()
    context.update({
        'page_obj': page_obj,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'month_income': month_income,
        'month_expense': month_expense,
        'finance_chart_json': json.dumps(finance_chart),
    })
    return render(request, 'farm/finance.html', context)


@login_required
def weight_dashboard(request):
    recent_weights = WeightLog.objects.select_related('goat').order_by('-date')
    goats = Goat.objects.all()

    paginator = Paginator(recent_weights, DEFAULT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Chart: monthly herd average weight
    chart_start = (timezone.now().date().replace(day=1) - timedelta(days=6 * 30)).replace(day=1)
    monthly_avg = (
        WeightLog.objects.filter(date__gte=chart_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(avg_weight=Avg('weight'))
        .order_by('month')
    )
    weight_chart = {
        'labels': [d['month'].strftime('%b %Y') for d in monthly_avg],
        'data': [round(float(d['avg_weight']), 1) for d in monthly_avg],
    }

    context = get_common_context()
    context.update({
        'page_obj': page_obj,
        'goats': goats,
        'weight_chart_json': json.dumps(weight_chart),
    })
    return render(request, 'farm/weight.html', context)


@login_required
def calendar_dashboard(request):
    if request.method == 'POST':
        form = FarmEventForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('calendar_dashboard')

    events = []

    # System Events (Read Only)
    for log in BreedingLog.objects.filter(due_date__isnull=False):
        events.append({
            'title': f"Due: {log.goat.name}",
            'start': log.due_date.isoformat(),
            'color': '#9C27B0',
            'url': f"/goat/{log.goat.id}/",
            'editable': False
        })

    for record in MedicalRecord.objects.filter(next_due_date__isnull=False):
        events.append({
            'title': f"{record.get_record_type_display()}: {record.goat.name}",
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
            'extendedProps': {'type': 'custom', 'category': event.category}
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


@login_required
def medicine_dashboard(request):
    if request.method == 'POST':
        form = MedicineForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('medicine_dashboard')

    meds = Medicine.objects.all().order_by('expiration_date')
    context = get_common_context()
    context.update({'meds': meds})
    return render(request, 'farm/medicine.html', context)


# --- CRM DASHBOARD ---

@login_required
def crm_dashboard(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'customer':
            form = CustomerForm(request.POST)
            if form.is_valid():
                form.save()
        elif form_type == 'waitlist':
            form = WaitingListForm(request.POST)
            if form.is_valid():
                form.save()
        elif 'update_status_id' in request.POST:
            entry = get_object_or_404(WaitingList, pk=request.POST.get('update_status_id'))
            entry.status = 'Fulfilled' if entry.status == 'Active' else 'Active'
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


@login_required
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

@login_required
def tools_dashboard(request):
    goats = Goat.objects.all()
    context = get_common_context()
    context.update({'goats': goats})
    return render(request, 'farm/tools.html', context)


# --- CALENDAR API ENDPOINTS ---

@login_required
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


@login_required
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


@login_required
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


@login_required
def delete_event_api(request, event_id):
    try:
        event = get_object_or_404(FarmEvent, pk=event_id)
        event.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
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


@login_required
def toggle_task_date(request, task_id, date_str):
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        task = get_object_or_404(DailyTask, pk=task_id)
        completion, created = TaskCompletion.objects.get_or_create(task=task, date=query_date)
        if created:
            completion.completed = True
        else:
            completion.completed = not completion.completed
        completion.save()
        return JsonResponse({'status': 'success', 'completed': completion.completed})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# --- QUICK ACTIONS ---

@login_required
def quick_milk(request, goat_id):
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            if amount > 0:
                MilkLog.objects.create(
                    goat_id=goat_id,
                    amount=amount,
                    date=timezone.now().date(),
                    time='AM' if timezone.now().hour < 12 else 'PM',
                    notes="Quick Log from Dashboard"
                )
        except (ValueError, TypeError):
            pass
    return redirect('index')


@login_required
def toggle_sick(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    with transaction.atomic():
        if goat.status == 'Sick':
            goat.status = 'Healthy'
        else:
            goat.status = 'Sick'
            GoatLog.objects.create(goat=goat, note="Marked as Sick via Quick Action")
        goat.save()
    return redirect('index')


# --- GOAT DETAIL & ACTIONS ---

@login_required
def goat_detail(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)

    if request.method == 'POST':
        # 1. Profile Image Upload
        if 'image' in request.FILES:
            error = validate_image_upload(request.FILES['image'])
            if error:
                messages.error(request, error)
            else:
                goat.image = request.FILES['image']
                goat.save()
            return redirect('goat_detail', goat_id=goat.id)

        # 2. Daily Log Note
        if 'note' in request.POST:
            form = GoatLogForm(request.POST)
            if form.is_valid():
                log = form.save(commit=False)
                log.goat = goat
                log.save()
            return redirect('goat_detail', goat_id=goat.id)

        # 3. Gallery Upload
        if 'gallery_image' in request.FILES:
            error = validate_image_upload(request.FILES['gallery_image'])
            if error:
                messages.error(request, error)
            else:
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

    # Gallery Photos — grouped by month for timeline view
    gallery_photos = goat.photos.order_by('-date_added')
    from collections import OrderedDict
    photos_by_month = OrderedDict()
    for photo in gallery_photos:
        key = photo.date_added.strftime('%B %Y')
        photos_by_month.setdefault(key, []).append(photo)

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
        'photos_by_month': photos_by_month,
    })
    return render(request, 'farm/goat_detail.html', context)


@login_required
def add_weight_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        form = WeightLogForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.goat = goat
            record.save()
    return redirect('goat_detail', goat_id=goat.id)


@login_required
def add_medical_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        form = MedicalRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.goat = goat
            record.save()
    return redirect('goat_detail', goat_id=goat.id)


@login_required
def add_feeding_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        form = FeedingLogForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.goat = goat
            record.save()
    return redirect('goat_detail', goat_id=goat.id)


@login_required
def add_breeding_record(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        form = BreedingLogForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.goat = goat
            record.save()
    return redirect('goat_detail', goat_id=goat.id)


@login_required
def update_goat_status(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        goat.status = request.POST.get('status', 'Healthy')
        goat.save()
    return redirect('goat_detail', goat_id=goat.id)


@login_required
def delete_goat(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    if request.method == 'POST':
        goat.delete()
        return redirect('index')
    return redirect('goat_detail', goat_id=goat.id)


@login_required
def save_grazing_area(request):
    if request.method == 'POST':
        form = GrazingAreaForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect('index')


@login_required
def toggle_task(request, task_id):
    task = get_object_or_404(DailyTask, pk=task_id)
    today = timezone.now().date()
    completion, created = TaskCompletion.objects.get_or_create(task=task, date=today)
    if not created:
        completion.delete()
    else:
        completion.completed = True
        completion.save()
    return redirect('index')


@login_required
def sales_list(request):
    sales_qs = Sale.objects.all().order_by('-sale_date')
    paginator = Paginator(sales_qs, DEFAULT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = get_common_context()
    context.update({'page_obj': page_obj})
    return render(request, 'farm/sales_list.html', context)


@login_required
def meat_locker(request):
    harvests = MeatHarvest.objects.all().order_by('-harvest_date')

    if request.method == 'POST':
        form = MeatHarvestForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                harvest = form.save()
                goat = harvest.goat
                goat.status = 'Deceased'
                goat.save()
            return redirect('meat_locker')
    else:
        form = MeatHarvestForm()

    # Calculate Stats
    total_hanging = harvests.aggregate(Sum('hanging_weight'))['hanging_weight__sum'] or 0
    yields = [h.yield_percentage for h in harvests if h.live_weight > 0]
    avg_yield = sum(yields) / len(yields) if yields else 0

    context = {
        'harvests': harvests,
        'form': form,
        'total_hanging': round(total_hanging, 1),
        'avg_yield': round(avg_yield, 1),
        'total_count': harvests.count()
    }
    return render(request, 'farm/meat_locker.html', context)


# --- CSV EXPORT ---

@login_required
def export_milk_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="milk_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Goat', 'Amount (lbs)', 'Butterfat %', 'Protein %', 'SCC'])
    for log in MilkLog.objects.select_related('goat').order_by('-date'):
        writer.writerow([log.date, log.time, log.goat.name, log.amount,
                         log.butterfat or '', log.protein or '', log.somatic_cell_count or ''])
    return response


@login_required
def export_transactions_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Description'])
    for t in Transaction.objects.order_by('-date'):
        writer.writerow([t.date, t.type, t.category, t.amount, t.description])
    return response


@login_required
def export_medical_csv(request, goat_id=None):
    qs = MedicalRecord.objects.select_related('goat').order_by('-date')
    filename = 'medical_records.csv'
    if goat_id:
        goat = get_object_or_404(Goat, pk=goat_id)
        qs = qs.filter(goat=goat)
        filename = f'medical_{goat.name}.csv'

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Goat', 'Type', 'Notes', 'Next Due'])
    for r in qs:
        writer.writerow([r.date, r.goat.name, r.get_record_type_display(), r.notes, r.next_due_date or ''])
    return response


# --- REST API ---

@login_required
@require_GET
def api_goats_list(request):
    goats = Goat.objects.all().values(
        'id', 'name', 'breed', 'status', 'birthdate', 'age', 'is_fainting',
        'scrapie_tag', 'microchip_id',
    )
    return JsonResponse({'goats': list(goats)})


@login_required
@require_GET
def api_goat_detail(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    recent_medical = list(goat.medical_records.order_by('-date')[:5].values(
        'id', 'record_type', 'date', 'notes', 'next_due_date'
    ))
    recent_weight = list(goat.weight_logs.order_by('-date')[:5].values(
        'id', 'date', 'weight', 'notes'
    ))
    recent_milk = list(goat.milk_logs.order_by('-date')[:5].values(
        'id', 'date', 'time', 'amount'
    ))
    data = {
        'id': goat.id,
        'name': goat.name,
        'breed': goat.breed,
        'status': goat.status,
        'birthdate': goat.birthdate,
        'age': goat.display_age,
        'bio': goat.bio,
        'scrapie_tag': goat.scrapie_tag or '',
        'microchip_id': goat.microchip_id,
        'recent_medical': recent_medical,
        'recent_weight': recent_weight,
        'recent_milk': recent_milk,
    }
    return JsonResponse(data)


@login_required
@require_GET
def api_milk_list(request):
    qs = MilkLog.objects.select_related('goat').order_by('-date')
    goat_id = request.GET.get('goat')
    if goat_id:
        qs = qs.filter(goat_id=goat_id)
    date_from = request.GET.get('from')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    date_to = request.GET.get('to')
    if date_to:
        qs = qs.filter(date__lte=date_to)

    logs = []
    for log in qs[:100]:
        logs.append({
            'id': log.id,
            'goat_id': log.goat_id,
            'goat_name': log.goat.name,
            'date': log.date.isoformat(),
            'time': log.time,
            'amount': float(log.amount),
            'butterfat': float(log.butterfat) if log.butterfat else None,
            'protein': float(log.protein) if log.protein else None,
            'somatic_cell_count': log.somatic_cell_count,
        })
    return JsonResponse({'milk_logs': logs})


@login_required
@require_GET
def api_finance_list(request):
    qs = Transaction.objects.order_by('-date')
    tx_type = request.GET.get('type')
    if tx_type:
        qs = qs.filter(type=tx_type)
    category = request.GET.get('category')
    if category:
        qs = qs.filter(category=category)
    date_from = request.GET.get('from')
    if date_from:
        qs = qs.filter(date__gte=date_from)

    transactions = []
    for t in qs[:100]:
        transactions.append({
            'id': t.id,
            'date': t.date.isoformat(),
            'type': t.type,
            'category': t.category,
            'amount': float(t.amount),
            'description': t.description,
        })
    return JsonResponse({'transactions': transactions})


# --- PRINT-FRIENDLY REPORTS ---

@login_required
def print_herd_summary(request):
    goats = Goat.objects.select_related('dam', 'sire').all().order_by('name')
    context = get_common_context()
    context.update({
        'report_title': 'Herd Summary',
        'goats': goats,
        'total_count': goats.count(),
        'healthy_count': goats.filter(status='Healthy').count(),
        'sick_count': goats.filter(status='Sick').count(),
        'vet_count': goats.filter(status='Vet').count(),
    })
    return render(request, 'farm/reports/herd_summary.html', context)


@login_required
def print_goat_health(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    weight_logs = goat.weight_logs.order_by('-date')
    latest_weight = weight_logs.first().weight if weight_logs.exists() else None
    context = get_common_context()
    context.update({
        'report_title': f'{goat.name} — Health Record',
        'goat': goat,
        'medical_records': goat.medical_records.order_by('-date'),
        'weight_logs': weight_logs,
        'breeding_logs': goat.breeding_logs.order_by('-breeding_date'),
        'latest_weight': latest_weight,
    })
    return render(request, 'farm/reports/goat_health.html', context)


@login_required
def print_breeding_report(request):
    today = timezone.now().date()
    all_logs = BreedingLog.objects.select_related('goat').order_by('due_date')
    active = []
    past = []
    for log in all_logs:
        if log.due_date and log.due_date >= today:
            log.days_until_due = (log.due_date - today).days
            active.append(log)
        else:
            past.append(log)
    context = get_common_context()
    context.update({
        'report_title': 'Breeding Report',
        'active_pregnancies': active,
        'past_breedings': past,
        'active_count': len(active),
        'total_count': all_logs.count(),
    })
    return render(request, 'farm/reports/breeding_report.html', context)


@login_required
def print_financial_summary(request):
    today = timezone.now().date()
    year = today.year
    year_start = today.replace(month=1, day=1)
    qs = Transaction.objects.filter(date__gte=year_start)

    total_income = qs.filter(type='Income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = qs.filter(type='Expense').aggregate(Sum('amount'))['amount__sum'] or 0

    # Monthly breakdown
    monthly_raw = (
        qs.annotate(month=TruncMonth('date'))
        .values('month', 'type')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    months_set = sorted({d['month'] for d in monthly_raw})
    income_map = {d['month']: float(d['total']) for d in monthly_raw if d['type'] == 'Income'}
    expense_map = {d['month']: float(d['total']) for d in monthly_raw if d['type'] == 'Expense'}
    monthly_data = []
    for m in months_set:
        inc = income_map.get(m, 0)
        exp = expense_map.get(m, 0)
        monthly_data.append({'month': m.strftime('%B %Y'), 'income': inc, 'expense': exp, 'net': inc - exp})

    # Category breakdown
    category_breakdown = list(
        qs.filter(type='Expense')
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    context = get_common_context()
    context.update({
        'report_title': f'Financial Summary — {year}',
        'year': year,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': total_income - total_expense,
        'monthly_data': monthly_data,
        'category_breakdown': category_breakdown,
    })
    return render(request, 'farm/reports/financial_summary.html', context)


# --- PEDIGREE VIEW ---

@login_required
def goat_pedigree(request, goat_id):
    goat = get_object_or_404(
        Goat.objects.select_related(
            'dam', 'sire',
            'dam__dam', 'dam__sire', 'sire__dam', 'sire__sire',
            'dam__dam__dam', 'dam__dam__sire', 'dam__sire__dam', 'dam__sire__sire',
            'sire__dam__dam', 'sire__dam__sire', 'sire__sire__dam', 'sire__sire__sire',
        ),
        pk=goat_id,
    )

    # Collect descendants (kids where this goat is dam or sire)
    kids_as_dam = Goat.objects.filter(dam=goat).order_by('name')
    kids_as_sire = Goat.objects.filter(sire=goat).order_by('name')

    context = get_common_context()
    context.update({
        'goat': goat,
        'kids_as_dam': kids_as_dam,
        'kids_as_sire': kids_as_sire,
    })
    return render(request, 'farm/pedigree.html', context)


# --- DATABASE BACKUP / RESTORE ---

def is_superuser(user):
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def backup_database(request):
    db_path = Path(django_settings.DATABASES['default']['NAME'])
    if not db_path.exists():
        messages.error(request, "Database file not found.")
        return redirect('tools_dashboard')

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'goatos_backup_{timestamp}.sqlite3'

    response = HttpResponse(content_type='application/x-sqlite3')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    with open(db_path, 'rb') as f:
        response.write(f.read())
    return response


@login_required
@user_passes_test(is_superuser)
def restore_database(request):
    if request.method == 'POST' and request.FILES.get('db_file'):
        uploaded = request.FILES['db_file']
        if not uploaded.name.endswith('.sqlite3'):
            messages.error(request, "Only .sqlite3 files are accepted.")
            return redirect('tools_dashboard')

        db_path = Path(django_settings.DATABASES['default']['NAME'])

        # Create safety backup
        backup_path = db_path.with_suffix('.backup')
        if db_path.exists():
            shutil.copy2(db_path, backup_path)

        # Write uploaded file
        with open(db_path, 'wb') as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        messages.success(request, "Database restored successfully. A safety backup was saved.")
        return redirect('tools_dashboard')

    return redirect('tools_dashboard')


# --- BARCODE LOOKUP API ---

@login_required
@require_GET
def api_lookup_barcode(request):
    barcode = request.GET.get('barcode', '').strip()
    if not barcode:
        return JsonResponse({'error': 'No barcode provided'}, status=400)

    # Search FeedItem first, then Medicine
    feed = FeedItem.objects.filter(barcode=barcode).first()
    if feed:
        return JsonResponse({
            'type': 'feed',
            'id': feed.id,
            'name': feed.name,
            'quantity': float(feed.quantity),
            'unit': feed.unit,
        })

    med = Medicine.objects.filter(barcode=barcode).first()
    if med:
        return JsonResponse({
            'type': 'medicine',
            'id': med.id,
            'name': med.name,
            'quantity': float(med.quantity),
            'unit': med.unit,
        })

    return JsonResponse({'error': 'Item not found'}, status=404)


# --- BREEDING PLANNER ---

@login_required
def breeding_planner(request):
    if request.method == 'POST':
        goat_id = request.POST.get('goat_id')
        mate_name = request.POST.get('mate_name', '')
        plan_date = request.POST.get('plan_date')
        if goat_id and plan_date:
            goat = get_object_or_404(Goat, pk=goat_id)
            FarmEvent.objects.create(
                title=f"Planned Breeding: {goat.name} × {mate_name}",
                date=plan_date,
                category='Breeding',
            )
            messages.success(request, f"Breeding event planned for {goat.name}.")
            return redirect('breeding_planner')

    goats = Goat.objects.exclude(status='Deceased').order_by('name')
    context = get_common_context()
    context.update({'goats': goats})
    return render(request, 'farm/breeding_planner.html', context)


@login_required
@require_GET
def api_heat_cycles(request, goat_id):
    goat = get_object_or_404(Goat, pk=goat_id)
    last_breeding = goat.breeding_logs.order_by('-breeding_date').first()
    start_date = last_breeding.breeding_date if last_breeding else timezone.now().date()

    cycles = []
    for i in range(1, 7):
        cycle_start = start_date + timedelta(days=HEAT_CYCLE_DAYS * i)
        cycle_end = cycle_start + timedelta(days=BREEDING_WINDOW_DAYS - 1)
        cycles.append({
            'cycle': i,
            'start': cycle_start.isoformat(),
            'end': cycle_end.isoformat(),
            'title': f"Heat Window #{i}: {goat.name}",
        })
    return JsonResponse({'goat': goat.name, 'reference_date': start_date.isoformat(), 'cycles': cycles})


@login_required
@require_GET
def api_check_inbreeding(request):
    goat1_id = request.GET.get('goat1')
    goat2_id = request.GET.get('goat2')
    if not goat1_id or not goat2_id:
        return JsonResponse({'error': 'Two goat IDs required'}, status=400)

    def get_ancestors(goat, depth=3):
        """Collect ancestor IDs up to given depth."""
        ancestors = set()
        if not goat or depth == 0:
            return ancestors
        if goat.dam_id:
            ancestors.add(goat.dam_id)
            ancestors |= get_ancestors(goat.dam, depth - 1)
        if goat.sire_id:
            ancestors.add(goat.sire_id)
            ancestors |= get_ancestors(goat.sire, depth - 1)
        return ancestors

    goat1 = get_object_or_404(
        Goat.objects.select_related(
            'dam', 'sire',
            'dam__dam', 'dam__sire', 'sire__dam', 'sire__sire',
            'dam__dam__dam', 'dam__dam__sire', 'dam__sire__dam', 'dam__sire__sire',
            'sire__dam__dam', 'sire__dam__sire', 'sire__sire__dam', 'sire__sire__sire',
        ), pk=goat1_id)
    goat2 = get_object_or_404(
        Goat.objects.select_related(
            'dam', 'sire',
            'dam__dam', 'dam__sire', 'sire__dam', 'sire__sire',
            'dam__dam__dam', 'dam__dam__sire', 'dam__sire__dam', 'dam__sire__sire',
            'sire__dam__dam', 'sire__dam__sire', 'sire__sire__dam', 'sire__sire__sire',
        ), pk=goat2_id)

    ancestors1 = get_ancestors(goat1)
    ancestors2 = get_ancestors(goat2)
    shared_ids = ancestors1 & ancestors2

    shared_names = list(Goat.objects.filter(id__in=shared_ids).values_list('name', flat=True)) if shared_ids else []

    return JsonResponse({
        'goat1': goat1.name,
        'goat2': goat2.name,
        'has_shared_ancestors': len(shared_names) > 0,
        'shared_ancestors': shared_names,
    })
