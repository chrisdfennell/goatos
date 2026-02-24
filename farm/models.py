from django.db import models
from django.utils import timezone
from datetime import date, timedelta
import json

# --- SETTINGS MODEL ---
class FarmSettings(models.Model):
    name = models.CharField(max_length=200, default="My Homestead")
    owner = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    google_maps_api_key = models.CharField(max_length=100, blank=True, default="", help_text="Your Google Maps API Key")

    def __str__(self):
        return self.name

class Goat(models.Model):
    STATUS_CHOICES = [
        ('Healthy', 'Healthy'),
        ('Sick', 'Sick'),
        ('Vet', 'At Vet'),
        ('Deceased', 'Deceased'),
    ]
    GENDER_CHOICES = [
        ('Doe', 'Doe (Female)'),
        ('Buck', 'Buck (Male)'),
        ('Wether', 'Wether (Castrated Male)'),
        ('Doeling', 'Doeling (Young Female)'),
        ('Buckling', 'Buckling (Young Male)'),
    ]

    name = models.CharField(max_length=100)
    breed = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Doe', blank=True)
    age = models.IntegerField(default=0, verbose_name="Approx Age (if birthdate unknown)")
    birthdate = models.DateField(null=True, blank=True)
    is_fainting = models.BooleanField(default=False, help_text="Does this goat faint when scared?")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Healthy')
    bio = models.TextField(blank=True)
    image = models.ImageField(upload_to='goats/', blank=True, null=True)

    # Pedigree Fields
    dam = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='kids_dam', verbose_name="Dam (Mother)")
    sire = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='kids_sire', verbose_name="Sire (Father)")

    def __str__(self):
        return f"{self.name} ({self.status})"

    @property
    def display_age(self):
        if self.birthdate:
            today = date.today()
            total_days = (today - self.birthdate).days
            if total_days < 7:
                return f"{total_days} Days"
            elif total_days < 30:
                weeks = total_days // 7
                return f"{weeks} Week{'s' if weeks != 1 else ''}"
            elif total_days < 365:
                months = total_days // 30
                weeks = (total_days % 30) // 7
                if weeks > 0:
                    return f"{months} Month{'s' if months != 1 else ''}, {weeks} Week{'s' if weeks != 1 else ''}"
                return f"{months} Month{'s' if months != 1 else ''}"
            else:
                years = today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
                return f"{years} Year{'s' if years != 1 else ''}"
        return f"{self.age} Years"

    @property
    def age_in_days(self):
        if self.birthdate:
            return (date.today() - self.birthdate).days
        return self.age * 365  # Approximate from manual age field

class GoatLog(models.Model):
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='logs')
    date = models.DateTimeField(auto_now_add=True)
    note = models.TextField()

    def __str__(self):
        return f"{self.goat.name} - {self.date.strftime('%Y-%m-%d')}"

class GrazingArea(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default='#FF0000')
    coordinates = models.TextField(help_text="JSON list of {lat, lng} points")

    def __str__(self):
        return self.name

    @property
    def days_resting(self):
        last = self.assignments.filter(end_date__isnull=False).order_by('-end_date').first()
        if last and last.end_date:
            return (date.today() - last.end_date).days
        return None

    @property
    def active_assignment(self):
        return self.assignments.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=date.today())
        ).first()

    @property
    def latest_condition(self):
        return self.conditions.order_by('-date').first()


class PastureAssignment(models.Model):
    grazing_area = models.ForeignKey(GrazingArea, on_delete=models.CASCADE, related_name='assignments')
    goats = models.ManyToManyField('Goat', related_name='pasture_assignments', blank=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank if currently active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.grazing_area.name}: {self.start_date} - {self.end_date or 'Active'}"

    @property
    def is_active(self):
        return self.end_date is None or self.end_date >= date.today()


class MapMarker(models.Model):
    MARKER_TYPES = [
        ('Barn', 'Barn'), ('Shelter', 'Shelter'), ('Water', 'Water Trough'),
        ('Feeder', 'Feeder'), ('Gate', 'Gate'), ('Other', 'Other'),
    ]
    name = models.CharField(max_length=100)
    marker_type = models.CharField(max_length=20, choices=MARKER_TYPES, default='Other')
    latitude = models.FloatField()
    longitude = models.FloatField()
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.marker_type})"


class PastureCondition(models.Model):
    grazing_area = models.ForeignKey(GrazingArea, on_delete=models.CASCADE, related_name='conditions')
    date = models.DateField(default=timezone.now)
    score = models.IntegerField(help_text="Forage quality 1-5")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.grazing_area.name} - Score {self.score} ({self.date})"


class MedicalSchedule(models.Model):
    RECORD_TYPES = [
        ('Vaccine', 'Vaccination'), ('Deworm', 'Deworming'),
        ('Hoof', 'Hoof Trim'), ('Checkup', 'General Checkup'),
    ]
    goat = models.ForeignKey('Goat', on_delete=models.CASCADE, null=True, blank=True, related_name='medical_schedules', help_text="Leave blank for herd-wide schedule")
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    interval_days = models.IntegerField(help_text="Days between treatments")
    last_performed = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        target = self.goat.name if self.goat else "Entire Herd"
        return f"{self.get_record_type_display()} - {target} (every {self.interval_days} days)"

    @property
    def next_due(self):
        return self.last_performed + timedelta(days=self.interval_days)

    @property
    def is_due_soon(self):
        return self.next_due <= date.today() + timedelta(days=14)

class DailyTask(models.Model):
    TIME_CHOICES = [('AM', 'Morning'), ('PM', 'Evening'), ('ANY', 'Anytime')]
    name = models.CharField(max_length=200)
    time_of_day = models.CharField(max_length=3, choices=TIME_CHOICES, default='ANY')
    
    def __str__(self):
        return f"[{self.get_time_of_day_display()}] {self.name}"

class TaskCompletion(models.Model):
    task = models.ForeignKey(DailyTask, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('task', 'date')

class Vet(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, help_text="e.g. 555-123-4567")
    address = models.TextField(help_text="Full address for map navigation")
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name

class MedicalRecord(models.Model):
    RECORD_TYPES = [
        ('Vaccine', 'Vaccination'),
        ('Deworm', 'Deworming'),
        ('Hoof', 'Hoof Trim'),
        ('Checkup', 'General Checkup'),
        ('Illness', 'Illness/Injury'),
    ]
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='medical_records')
    date = models.DateField(default=timezone.now)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    notes = models.TextField(blank=True)
    next_due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.goat.name} - {self.record_type}"

class FeedingLog(models.Model):
    FEED_TYPES = [('Hay', 'Hay'), ('Grain', 'Grain'), ('Minerals', 'Minerals'), ('Treats', 'Treats'), ('Other', 'Other')]
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='feeding_logs')
    date = models.DateField(default=timezone.now)
    feed_type = models.CharField(max_length=20, choices=FEED_TYPES)
    amount = models.CharField(max_length=100, help_text="e.g. 1 Scoop, 2 Flakes")
    notes = models.TextField(blank=True)

class BreedingLog(models.Model):
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='breeding_logs')
    mate_name = models.CharField(max_length=100, verbose_name="Buck/Partner Name")
    breeding_date = models.DateField()
    due_date = models.DateField(blank=True, null=True, help_text="Auto-calculated (150 days) if left blank")
    notes = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        if not self.due_date and self.breeding_date:
            self.due_date = self.breeding_date + timedelta(days=150)
        super().save(*args, **kwargs)

class FeedItem(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. Alfalfa Hay, Goat Pellets")
    quantity = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, default="lbs", help_text="e.g. Bales, Bags, lbs")
    low_stock_threshold = models.DecimalField(max_digits=7, decimal_places=2, default=5.00, help_text="Alert when stock drops below this")

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"
    
    @property
    def is_low(self):
        return self.quantity <= self.low_stock_threshold

class MilkLog(models.Model):
    TIME_CHOICES = [('AM', 'Morning'), ('PM', 'Evening')]
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='milk_logs')
    date = models.DateField(default=timezone.now)
    time = models.CharField(max_length=2, choices=TIME_CHOICES, default='AM')
    amount = models.DecimalField(max_digits=5, decimal_places=2, help_text="Amount in lbs")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.goat.name} - {self.date} {self.time} ({self.amount} lbs)"

# --- FINANCE MODEL ---
class Transaction(models.Model):
    TYPES = [('Expense', 'Expense 💸'), ('Income', 'Income 💰')]
    CATEGORIES = [
        ('Feed', 'Feed & Hay'),
        ('Vet', 'Vet & Medical'),
        ('Equipment', 'Equipment & Supplies'),
        ('Goat Sale', 'Goat Sale'),
        ('Product Sale', 'Product Sale (Milk/Soap)'),
        ('Other', 'Other')
    ]
    
    date = models.DateField(default=timezone.now)
    type = models.CharField(max_length=10, choices=TYPES, default='Expense')
    category = models.CharField(max_length=20, choices=CATEGORIES, default='Other')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    goat = models.ForeignKey('Goat', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions', help_text="Optional: link expense to a specific goat")
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    def __str__(self):
        return f"{self.date} - {self.type}: ${self.amount}"

    class Meta:
        ordering = ['-date']

# --- WEIGHT MODEL ---
class WeightLog(models.Model):
    goat = models.ForeignKey('Goat', on_delete=models.CASCADE, related_name='weight_logs')
    date = models.DateField(default=timezone.now)
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in lbs")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['date'] # Ascending for graph

    def __str__(self):
        return f"{self.goat.name} - {self.weight} lbs"

# --- CALENDAR MODEL ---
class FarmEvent(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField(default=timezone.now, verbose_name="Start Date")
    end_date = models.DateField(null=True, blank=True, verbose_name="End Date") # Added
    category = models.CharField(max_length=50, default='General', help_text="e.g. Vet, Show, Maintenance")
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.date} - {self.title}"

# --- NEW MEDICINE MODEL ---
class Medicine(models.Model):
    UNIT_CHOICES = [('ml', 'ml/cc'), ('g', 'grams'), ('pill', 'pills/bolus'), ('oz', 'ounces')]
    
    name = models.CharField(max_length=100)
    batch = models.CharField(max_length=50, blank=True, help_text="Batch/Lot Number")
    expiration_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Current stock level")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='ml')
    
    # Dosage Logic: e.g. "1 ml" per "25 lbs"
    dosage_amount = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, help_text="Dose Amount")
    dosage_weight_interval = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Per X lbs bodyweight. Set to 0 for fixed dose.")
    
    notes = models.TextField(blank=True, help_text="Withdrawal times, warnings, etc.")

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"
    
    @property
    def is_expired(self):
        return self.expiration_date and self.expiration_date < date.today()
        
    @property
    def dosage_instruction(self):
        if self.dosage_weight_interval > 0:
            return f"{self.dosage_amount}{self.unit} / {self.dosage_weight_interval}lbs"
        return f"{self.dosage_amount}{self.unit} (Fixed)"

# --- GALLERY MODEL ---
class GoatPhoto(models.Model):
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='goat_gallery/')
    caption = models.CharField(max_length=200, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo of {self.goat.name}"

    class Meta:
        verbose_name = "Goat Photo"
        verbose_name_plural = "Goat Photos"

# ---CRM MODELS ---
class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    date_added = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name

class WaitingList(models.Model):
    GENDER_CHOICES = [('Any', 'Any'), ('Doe', 'Doe'), ('Buck', 'Buck'), ('Wether', 'Wether')]
    STATUS_CHOICES = [('Active', 'Active'), ('Fulfilled', 'Fulfilled'), ('Cancelled', 'Cancelled')]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='waitlist_entries')
    preferred_dam = models.ForeignKey(Goat, on_delete=models.SET_NULL, null=True, blank=True, related_name='waitlist_requests', help_text="Optional specific doe")
    preferred_gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Any')
    date_added = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.customer.name} - {self.preferred_gender} (Status: {self.status})"

class Sale(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='purchases')
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='sales')
    sale_date = models.DateField(help_text="Date the sale was finalized")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_paid_in_full = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Sale: {self.goat.name} to {self.customer.name}"

class MeatHarvest(models.Model):
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='harvests')
    harvest_date = models.DateField(default=timezone.now)
    live_weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight before processing (lbs)")
    hanging_weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Carcass weight (lbs)")
    notes = models.TextField(blank=True, help_text="Cut details, quality notes, etc.")

    def __str__(self):
        return f"{self.goat.name} - {self.harvest_date}"

    @property
    def yield_percentage(self):
        if self.live_weight and self.live_weight > 0:
            return (self.hanging_weight / self.live_weight) * 100
        return 0


# =====================================================
# NEW FEATURE MODELS (Phase 2)
# =====================================================

# --- Feature 1: Kidding Records ---
class KiddingRecord(models.Model):
    BIRTH_TYPES = [
        ('Single', 'Single'), ('Twins', 'Twins'),
        ('Triplets', 'Triplets'), ('Quads', 'Quads'),
    ]
    PRESENTATION_CHOICES = [
        ('Normal', 'Normal'), ('Breach', 'Breach'), ('Other', 'Other'),
    ]

    breeding_log = models.ForeignKey(BreedingLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='kidding_records')
    dam = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='kidding_records')
    kidding_date = models.DateField(default=timezone.now)
    num_kids_born = models.IntegerField(default=1)
    num_alive = models.IntegerField(default=1)
    num_stillborn = models.IntegerField(default=0)
    birth_type = models.CharField(max_length=10, choices=BIRTH_TYPES, default='Single')
    presentation = models.CharField(max_length=10, choices=PRESENTATION_CHOICES, default='Normal')
    assisted = models.BooleanField(default=False)
    complications = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-kidding_date']

    def __str__(self):
        return f"{self.dam.name} - {self.birth_type} on {self.kidding_date}"


# --- Feature 2: FAMACHA & Body Condition Scoring ---
class HealthScore(models.Model):
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='health_scores')
    date = models.DateField(default=timezone.now)
    famacha_score = models.IntegerField(null=True, blank=True, help_text="1=Red(healthy) to 5=White(anemic)")
    body_condition_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True, help_text="1=Emaciated to 5=Obese (0.5 steps)")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        parts = [f"{self.goat.name} - {self.date}"]
        if self.famacha_score:
            parts.append(f"FAMACHA:{self.famacha_score}")
        if self.body_condition_score:
            parts.append(f"BCS:{self.body_condition_score}")
        return " ".join(parts)


# --- Feature 3: Heat Detection / Estrus ---
class HeatObservation(models.Model):
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='heat_observations')
    date_observed = models.DateField(default=timezone.now)
    signs = models.CharField(max_length=200, blank=True, help_text="e.g. flagging, mounting, mucus discharge")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_observed']

    def __str__(self):
        return f"{self.goat.name} - Heat on {self.date_observed}"

    @property
    def next_heat_date(self):
        return self.date_observed + timedelta(days=21)

    @property
    def breeding_window_end(self):
        """Optimal breeding window is 12-36 hours after heat onset"""
        return self.date_observed + timedelta(days=1, hours=12)


# --- Feature 7: Document Vault ---
class GoatDocument(models.Model):
    DOC_TYPES = [
        ('Registration', 'Registration Papers'),
        ('Vet Report', 'Vet Report'),
        ('Receipt', 'Purchase Receipt'),
        ('Insurance', 'Insurance'),
        ('Certificate', 'Certificate'),
        ('Other', 'Other'),
    ]

    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='goat_documents/')
    title = models.CharField(max_length=200)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES, default='Other')
    date_uploaded = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_uploaded']

    def __str__(self):
        return f"{self.goat.name} - {self.title}"

    @property
    def file_extension(self):
        return self.file.name.split('.')[-1].lower() if '.' in self.file.name else ''


# --- Feature 8: Supplier / Vendor Database ---
class Supplier(models.Model):
    CATEGORIES = [
        ('Feed', 'Feed & Hay'), ('Equipment', 'Equipment'),
        ('Vet', 'Veterinary'), ('Shearing', 'Shearing'),
        ('Fencing', 'Fencing'), ('Other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='Other')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


# --- Feature 9: Pen / Barn Management ---
class Pen(models.Model):
    PEN_TYPES = [
        ('Kidding', 'Kidding Pen'), ('Buck', 'Buck Pen'),
        ('Doe', 'Doe Pen'), ('Kid', 'Kid Pen'),
        ('Sick', 'Sick Pen'), ('General', 'General'),
    ]

    name = models.CharField(max_length=100)
    pen_type = models.CharField(max_length=10, choices=PEN_TYPES, default='General')
    capacity = models.IntegerField(default=5)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_pen_type_display()})"

    @property
    def current_occupants(self):
        return self.assignments.filter(
            models.Q(date_out__isnull=True)
        ).select_related('goat')

    @property
    def occupant_count(self):
        return self.assignments.filter(date_out__isnull=True).count()

    @property
    def is_over_capacity(self):
        return self.occupant_count > self.capacity


class PenAssignment(models.Model):
    pen = models.ForeignKey(Pen, on_delete=models.CASCADE, related_name='assignments')
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='pen_assignments')
    date_in = models.DateField(default=timezone.now)
    date_out = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_in']

    def __str__(self):
        return f"{self.goat.name} in {self.pen.name}"

    @property
    def is_active(self):
        return self.date_out is None