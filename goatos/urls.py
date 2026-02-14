from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from farm import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.index, name='index'),
    
    # Feature Dashboards
    path('milk/', views.milk_dashboard, name='milk_dashboard'),
    path('breeding/', views.breeding_dashboard, name='breeding_dashboard'),
    path('silo/', views.silo_dashboard, name='silo_dashboard'),
    path('finance/', views.finance_dashboard, name='finance_dashboard'),
    path('weight/', views.weight_dashboard, name='weight_dashboard'),
    path('calendar/', views.calendar_dashboard, name='calendar_dashboard'),
    path('medicine/', views.medicine_dashboard, name='medicine_dashboard'),
    path('crm/', views.crm_dashboard, name='crm_dashboard'),
    path('sales/', views.sales_list, name='sales_list'),
    path('tools/', views.tools_dashboard, name='tools_dashboard'), # NEW

    # Settings & Updates
    path('update_settings/', views.update_settings, name='update_settings'),
    path('silo/update/<int:item_id>/', views.update_inventory, name='update_inventory'),

    # Goat Detail & Actions
    path('goat/<int:goat_id>/', views.goat_detail, name='goat_detail'),
    path('goat/<int:goat_id>/status/', views.update_goat_status, name='update_goat_status'),
    path('goat/<int:goat_id>/delete/', views.delete_goat, name='delete_goat'),
    path('goat/<int:goat_id>/add_medical/', views.add_medical_record, name='add_medical_record'),
    path('goat/<int:goat_id>/add_feeding/', views.add_feeding_record, name='add_feeding_record'),
    path('goat/<int:goat_id>/add_breeding/', views.add_breeding_record, name='add_breeding_record'),
    path('goat/<int:goat_id>/add_weight/', views.add_weight_record, name='add_weight_record'),
    path('goat/<int:goat_id>/card/', views.stall_card, name='stall_card'),
    path('goat/<int:goat_id>/pedigree/', views.goat_pedigree, name='goat_pedigree'),

    # Quick Actions
    path('quick/milk/<int:goat_id>/', views.quick_milk, name='quick_milk'),
    path('quick/sick/<int:goat_id>/', views.toggle_sick, name='toggle_sick'),

    # Index Interactive
    path('save_area/', views.save_grazing_area, name='save_grazing_area'),
    path('toggle_task/<int:task_id>/', views.toggle_task, name='toggle_task'),

    # Calendar API
    path('api/tasks/<str:date_str>/', views.get_daily_tasks, name='get_daily_tasks'),
    path('api/task/<int:task_id>/toggle/<str:date_str>/', views.toggle_task_date, name='toggle_task_date'),
    path('api/event/move/', views.move_event, name='move_event'),
    path('api/event/resize/', views.resize_event, name='resize_event'),
    path('api/event/update/', views.update_event_api, name='update_event_api'),
    path('api/event/delete/<int:event_id>/', views.delete_event_api, name='delete_event_api'),
    
    # Meat Locker
    path('meat/', views.meat_locker, name='meat_locker'),

    # CSV Exports
    path('milk/export/csv/', views.export_milk_csv, name='export_milk_csv'),
    path('finance/export/csv/', views.export_transactions_csv, name='export_transactions_csv'),
    path('medical/export/csv/', views.export_medical_csv, name='export_medical_csv'),
    path('goat/<int:goat_id>/medical/export/csv/', views.export_medical_csv, name='export_goat_medical_csv'),

    # Admin Tools
    path('admin-tools/backup/', views.backup_database, name='backup_database'),
    path('admin-tools/restore/', views.restore_database, name='restore_database'),

    # Barcode API
    path('api/barcode/', views.api_lookup_barcode, name='api_lookup_barcode'),

    # Breeding Planner
    path('breeding/planner/', views.breeding_planner, name='breeding_planner'),
    path('api/heat-cycles/<int:goat_id>/', views.api_heat_cycles, name='api_heat_cycles'),
    path('api/check-inbreeding/', views.api_check_inbreeding, name='api_check_inbreeding'),

    # Print Reports
    path('reports/herd/', views.print_herd_summary, name='print_herd_summary'),
    path('reports/goat/<int:goat_id>/health/', views.print_goat_health, name='print_goat_health'),
    path('reports/breeding/', views.print_breeding_report, name='print_breeding_report'),
    path('reports/finance/', views.print_financial_summary, name='print_financial_summary'),

    # REST API
    path('api/goats/', views.api_goats_list, name='api_goats_list'),
    path('api/goats/<int:goat_id>/', views.api_goat_detail, name='api_goat_detail'),
    path('api/milk/', views.api_milk_list, name='api_milk_list'),
    path('api/finance/', views.api_finance_list, name='api_finance_list'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)