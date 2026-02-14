from django import forms
from .models import (
    MeatHarvest, MilkLog, Transaction, Medicine, FarmEvent,
    Customer, WaitingList, WeightLog, FeedingLog, BreedingLog,
    MedicalRecord, GoatLog, GrazingArea, Goat,
)

_DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})


class MeatHarvestForm(forms.ModelForm):
    class Meta:
        model = MeatHarvest
        fields = ['goat', 'harvest_date', 'live_weight', 'hanging_weight', 'notes']
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class MilkLogForm(forms.ModelForm):
    class Meta:
        model = MilkLog
        fields = ['goat', 'date', 'time', 'amount', 'butterfat', 'protein', 'somatic_cell_count']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'date', 'category', 'amount', 'description']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = [
            'name', 'quantity', 'unit', 'dosage_amount',
            'dosage_weight_interval', 'batch', 'expiration_date', 'barcode', 'notes',
        ]
        widgets = {'expiration_date': forms.DateInput(attrs={'type': 'date'})}


class FarmEventForm(forms.ModelForm):
    class Meta:
        model = FarmEvent
        fields = ['title', 'date', 'end_date', 'category']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'notes']


class WaitingListForm(forms.ModelForm):
    class Meta:
        model = WaitingList
        fields = ['customer', 'preferred_dam', 'preferred_gender', 'notes']


class WeightLogForm(forms.ModelForm):
    class Meta:
        model = WeightLog
        fields = ['date', 'weight', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class FeedingLogForm(forms.ModelForm):
    class Meta:
        model = FeedingLog
        fields = ['date', 'feed_type', 'amount', 'notes', 'quantity', 'unit', 'feed_item']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class BreedingLogForm(forms.ModelForm):
    class Meta:
        model = BreedingLog
        fields = ['mate_name', 'breeding_date', 'notes']
        widgets = {'breeding_date': forms.DateInput(attrs={'type': 'date'})}


class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ['record_type', 'date', 'notes', 'next_due_date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class GoatLogForm(forms.ModelForm):
    class Meta:
        model = GoatLog
        fields = ['note']


class GrazingAreaForm(forms.ModelForm):
    class Meta:
        model = GrazingArea
        fields = ['name', 'color', 'coordinates']


class GoatForm(forms.ModelForm):
    class Meta:
        model = Goat
        fields = [
            'name', 'breed', 'birthdate', 'age', 'is_fainting', 'bio',
            'image', 'dam', 'sire', 'scrapie_tag', 'microchip_id', 'grazing_area',
        ]
        widgets = {
            'birthdate': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
        }
