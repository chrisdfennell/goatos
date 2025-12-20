from django import forms
from .models import MeatHarvest

class MeatHarvestForm(forms.ModelForm):
    class Meta:
        model = MeatHarvest
        fields = ['goat', 'harvest_date', 'live_weight', 'hanging_weight', 'notes']
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }