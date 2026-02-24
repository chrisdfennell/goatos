from django.contrib import admin
from .models import (Goat, GoatLog, GrazingArea, DailyTask, TaskCompletion, Vet, MedicalRecord,
    FeedingLog, BreedingLog, FeedItem, MilkLog, FarmSettings, Transaction, WeightLog, FarmEvent,
    Medicine, GoatPhoto, Customer, WaitingList, Sale, MeatHarvest, PastureAssignment, MapMarker,
    PastureCondition, MedicalSchedule, KiddingRecord, HealthScore, HeatObservation, GoatDocument,
    Supplier, Pen, PenAssignment)

@admin.register(Goat)
class GoatAdmin(admin.ModelAdmin):
    list_display = ('name', 'breed', 'gender', 'status', 'display_age', 'sire', 'dam')
    list_filter = ('status', 'breed', 'gender', 'is_fainting')
    search_fields = ('name', 'bio')
    # Enables a searchable dropdown for parents (useful if you have many goats)
    autocomplete_fields = ['dam', 'sire']

@admin.register(GoatLog)
class GoatLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'goat', 'short_note')
    list_filter = ('date', 'goat')
    
    def short_note(self, obj):
        return obj.note[:50]

@admin.register(GrazingArea)
class GrazingAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'color')

@admin.register(DailyTask)
class DailyTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'time_of_day')
    list_filter = ('time_of_day',)

@admin.register(TaskCompletion)
class TaskCompletionAdmin(admin.ModelAdmin):
    list_display = ('task', 'date', 'completed')
    list_filter = ('date', 'completed')

@admin.register(Vet)
class VetAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')

@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('date', 'goat', 'record_type', 'next_due_date')
    list_filter = ('record_type', 'goat')

@admin.register(FeedingLog)
class FeedingLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'goat', 'feed_type', 'amount')
    list_filter = ('feed_type', 'goat')

@admin.register(BreedingLog)
class BreedingLogAdmin(admin.ModelAdmin):
    list_display = ('goat', 'mate_name', 'breeding_date', 'due_date')
    list_filter = ('goat',)

@admin.register(FeedItem)
class FeedItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit', 'is_low')
    list_editable = ('quantity',)

@admin.register(MilkLog)
class MilkLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'time', 'goat', 'amount')
    list_filter = ('date', 'goat', 'time')

@admin.register(FarmSettings)
class FarmSettingsAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude')
    # Prevent creating multiple setting instances in Admin
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'type', 'category', 'amount', 'description', 'goat', 'supplier')
    list_filter = ('type', 'category', 'date')
    search_fields = ('description',)

@admin.register(WeightLog)
class WeightLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'goat', 'weight')
    list_filter = ('goat', 'date')

@admin.register(FarmEvent)
class FarmEventAdmin(admin.ModelAdmin):
    list_display = ('date', 'end_date', 'title', 'category')
    list_filter = ('date', 'category')

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit', 'expiration_date', 'dosage_instruction')
    list_filter = ('unit',)
    search_fields = ('name', 'batch')

@admin.register(GoatPhoto)
class GoatPhotoAdmin(admin.ModelAdmin):
    list_display = ('goat', 'caption', 'date_added')
    list_filter = ('goat', 'date_added')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'date_added')
    search_fields = ('name', 'email')

@admin.register(WaitingList)
class WaitingListAdmin(admin.ModelAdmin):
    list_display = ('customer', 'preferred_gender', 'preferred_dam', 'status', 'date_added')
    list_filter = ('status', 'preferred_gender')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('goat', 'customer', 'sale_date', 'sale_price', 'is_paid_in_full')
    list_filter = ('is_paid_in_full', 'sale_date')
    search_fields = ('goat__name', 'customer__name')
    date_hierarchy = 'sale_date'

@admin.register(MeatHarvest)
class MeatHarvestAdmin(admin.ModelAdmin):
    list_display = ('goat', 'harvest_date', 'live_weight', 'hanging_weight', 'calculated_yield')
    list_filter = ('harvest_date',)
    search_fields = ('goat__name', 'notes')
    date_hierarchy = 'harvest_date'
    
    def calculated_yield(self, obj):
        return f"{obj.yield_percentage:.1f}%"
    calculated_yield.short_description = 'Yield %'


@admin.register(PastureAssignment)
class PastureAssignmentAdmin(admin.ModelAdmin):
    list_display = ('grazing_area', 'start_date', 'end_date', 'is_active')
    list_filter = ('grazing_area', 'start_date')
    filter_horizontal = ('goats',)


@admin.register(MapMarker)
class MapMarkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'marker_type', 'latitude', 'longitude')
    list_filter = ('marker_type',)


@admin.register(PastureCondition)
class PastureConditionAdmin(admin.ModelAdmin):
    list_display = ('grazing_area', 'date', 'score')
    list_filter = ('grazing_area', 'score')


@admin.register(MedicalSchedule)
class MedicalScheduleAdmin(admin.ModelAdmin):
    list_display = ('record_type', 'goat', 'interval_days', 'last_performed', 'next_due')
    list_filter = ('record_type',)


@admin.register(KiddingRecord)
class KiddingRecordAdmin(admin.ModelAdmin):
    list_display = ('dam', 'kidding_date', 'birth_type', 'num_alive', 'num_stillborn', 'assisted')
    list_filter = ('birth_type', 'assisted', 'kidding_date')
    search_fields = ('dam__name',)


@admin.register(HealthScore)
class HealthScoreAdmin(admin.ModelAdmin):
    list_display = ('goat', 'date', 'famacha_score', 'body_condition_score')
    list_filter = ('famacha_score', 'date')
    search_fields = ('goat__name',)


@admin.register(HeatObservation)
class HeatObservationAdmin(admin.ModelAdmin):
    list_display = ('goat', 'date_observed', 'signs')
    list_filter = ('date_observed',)
    search_fields = ('goat__name',)


@admin.register(GoatDocument)
class GoatDocumentAdmin(admin.ModelAdmin):
    list_display = ('goat', 'title', 'doc_type', 'date_uploaded')
    list_filter = ('doc_type',)
    search_fields = ('goat__name', 'title')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'phone', 'email', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'contact_name')


@admin.register(Pen)
class PenAdmin(admin.ModelAdmin):
    list_display = ('name', 'pen_type', 'capacity', 'occupant_count')
    list_filter = ('pen_type',)


@admin.register(PenAssignment)
class PenAssignmentAdmin(admin.ModelAdmin):
    list_display = ('goat', 'pen', 'date_in', 'date_out', 'is_active')
    list_filter = ('pen', 'date_in')