from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
import re
from farm import views

urlpatterns = [
    path('admin/', admin.site.urls),
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
    path('tools/', views.tools_dashboard, name='tools_dashboard'),
    path('external-goats/', views.external_goats, name='external_goats'),

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

    # PIN Gate
    path('pin/', views.pin_login, name='pin_login'),
    path('pin/logout/', views.pin_logout, name='pin_logout'),

    # Add Goat
    path('add-goat/', views.add_goat, name='add_goat'),

    # CSV Exports
    path('export/goats/', views.export_goats_csv, name='export_goats'),
    path('export/finances/', views.export_finances_csv, name='export_finances'),
    path('export/milk/', views.export_milk_csv, name='export_milk'),
    path('export/medical/', views.export_medical_csv, name='export_medical'),

    # Vet CRUD
    path('vet/add/', views.add_vet, name='add_vet'),
    path('vet/<int:vet_id>/delete/', views.delete_vet, name='delete_vet'),

    # Task CRUD
    path('task/add/', views.add_task, name='add_task'),
    path('task/<int:task_id>/delete/', views.delete_task, name='delete_task'),

    # Feed Item CRUD
    path('feed/add/', views.add_feed_item, name='add_feed_item'),
    path('feed/<int:item_id>/delete/', views.delete_feed_item, name='delete_feed_item'),

    # Edit Goat
    path('goat/<int:goat_id>/edit/', views.edit_goat, name='edit_goat'),

    # Delete Records
    path('record/medical/<int:record_id>/delete/', views.delete_medical_record, name='delete_medical_record'),
    path('record/milk/<int:log_id>/delete/', views.delete_milk_log, name='delete_milk_log'),
    path('record/weight/<int:log_id>/delete/', views.delete_weight_log, name='delete_weight_log'),
    path('record/feeding/<int:log_id>/delete/', views.delete_feeding_log, name='delete_feeding_log'),
    path('record/breeding/<int:log_id>/delete/', views.delete_breeding_log, name='delete_breeding_log'),
    path('record/log/<int:log_id>/delete/', views.delete_goat_log, name='delete_goat_log'),
    path('record/photo/<int:photo_id>/delete/', views.delete_goat_photo, name='delete_goat_photo'),
    path('record/transaction/<int:txn_id>/delete/', views.delete_transaction, name='delete_transaction'),

    # Sales CRUD
    path('sales/add/', views.add_sale, name='add_sale'),
    path('sales/<int:sale_id>/toggle-paid/', views.toggle_sale_paid, name='toggle_sale_paid'),
    path('sales/<int:sale_id>/delete/', views.delete_sale, name='delete_sale'),

    # Customer CRUD
    path('customer/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customer/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),

    # Pasture / Grazing Rotation
    path('pasture/assign/', views.assign_pasture, name='assign_pasture'),
    path('pasture/<int:assignment_id>/end/', views.end_pasture_assignment, name='end_pasture_assignment'),
    path('api/pasture/<int:area_id>/history/', views.api_rotation_history, name='api_rotation_history'),

    # Map Markers
    path('marker/add/', views.add_map_marker, name='add_map_marker'),
    path('marker/<int:marker_id>/delete/', views.delete_map_marker, name='delete_map_marker'),

    # Pasture Conditions
    path('pasture/<int:area_id>/condition/', views.add_pasture_condition, name='add_pasture_condition'),
    path('api/pasture/<int:area_id>/conditions/', views.api_pasture_conditions, name='api_pasture_conditions'),

    # Grazing Area Edit/Delete API
    path('api/area/<int:area_id>/update/', views.update_grazing_area, name='update_grazing_area'),
    path('api/area/<int:area_id>/delete/', views.delete_grazing_area, name='delete_grazing_area'),

    # Full Map + KML Export
    path('map/', views.map_dashboard, name='map_dashboard'),
    path('export/grazing-areas/kml/', views.export_grazing_areas_kml, name='export_grazing_areas_kml'),

    # Analytics Dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),

    # Medical Schedules
    path('schedule/add/', views.add_medical_schedule, name='add_medical_schedule'),
    path('schedule/<int:schedule_id>/delete/', views.delete_medical_schedule, name='delete_medical_schedule'),

    # Backup/Restore
    path('tools/backup/', views.backup_database, name='backup_database'),
    path('tools/backup-media/', views.backup_media, name='backup_media'),
    path('tools/restore/', views.restore_database, name='restore_database'),

    # PWA
    path('sw.js', views.service_worker, name='service_worker'),

    # ===== NEW FEATURES (Phase 2) =====

    # Kidding Records (Feature 1)
    path('kidding/add/', views.add_kidding_record, name='add_kidding_record'),
    path('kidding/<int:record_id>/delete/', views.delete_kidding_record, name='delete_kidding_record'),

    # Kidding Season Dashboard (Feature 4)
    path('kidding-season/', views.kidding_season_dashboard, name='kidding_season_dashboard'),

    # FAMACHA & Body Condition Scoring (Feature 2)
    path('goat/<int:goat_id>/health-score/', views.add_health_score, name='add_health_score'),
    path('health-score/<int:score_id>/delete/', views.delete_health_score, name='delete_health_score'),
    path('health-scores/', views.health_scores_dashboard, name='health_scores_dashboard'),

    # Heat Detection / Estrus (Feature 3)
    path('goat/<int:goat_id>/heat/', views.add_heat_observation, name='add_heat_observation'),
    path('heat/<int:observation_id>/delete/', views.delete_heat_observation, name='delete_heat_observation'),

    # Activity Feed (Feature 5)
    path('activity/', views.activity_feed, name='activity_feed'),

    # Cost-Per-Goat Analysis (Feature 6)
    path('cost-analysis/', views.cost_analysis, name='cost_analysis'),

    # Document Vault (Feature 7)
    path('goat/<int:goat_id>/document/', views.add_goat_document, name='add_goat_document'),
    path('document/<int:doc_id>/delete/', views.delete_goat_document, name='delete_goat_document'),

    # Supplier Database (Feature 8)
    path('suppliers/', views.suppliers_dashboard, name='suppliers_dashboard'),
    path('supplier/<int:supplier_id>/delete/', views.delete_supplier, name='delete_supplier'),

    # Barn / Pen Management (Feature 9)
    path('barn/', views.barn_dashboard, name='barn_dashboard'),
    path('pen/<int:pen_id>/delete/', views.delete_pen, name='delete_pen'),

]

# Always serve media files (runsslserver doesn't have a separate web server)
urlpatterns += [
    path(re.sub(r'^/', '', settings.MEDIA_URL) + '<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]