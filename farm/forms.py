from django import forms
from .models import MeatHarvest, Goat


class MeatHarvestForm(forms.ModelForm):
    class Meta:
        model = MeatHarvest
        fields = ['goat', 'harvest_date', 'live_weight', 'hanging_weight', 'notes']
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class PinForm(forms.Form):
    pin = forms.CharField(
        max_length=20,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter PIN',
            'autofocus': True,
            'style': 'font-size: 1.5em; text-align: center; letter-spacing: 5px;',
        })
    )


class GoatForm(forms.ModelForm):
    class Meta:
        model = Goat
        fields = ['name', 'breed', 'gender', 'birthdate', 'age', 'is_fainting', 'status', 'bio', 'image', 'dam', 'sire', 'registration_number', 'is_external', 'external_owner']
        widgets = {
            'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Goat name'}),
            'breed': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Nigerian Dwarf'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes about this goat...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'dam': forms.Select(attrs={'class': 'form-select'}),
            'sire': forms.Select(attrs={'class': 'form-select'}),
            'is_fainting': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ADGA-12345'}),
            'is_external': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'external_owner': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Breeder / owner name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['dam', 'sire']:
            field = self.fields[field_name]
            field.label_from_instance = self._goat_label

    @staticmethod
    def _goat_label(obj):
        label = obj.name
        if obj.registration_number:
            label += f" — {obj.registration_number}"
        if obj.is_external:
            label += " (External)"
        return label
