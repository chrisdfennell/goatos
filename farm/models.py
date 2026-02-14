from django.db import models
from django.utils import timezone
from datetime import timedelta

from .constants import GESTATION_DAYS

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

    name = models.CharField(max_length=100)
    breed = models.CharField(max_length=100)
    age = models.IntegerField(default=0, verbose_name="Approx Age (if birthdate unknown)")
    birthdate = models.DateField(null=True, blank=True, help_text="YYYY-MM-DD")
    is_fainting = models.BooleanField(default=False, help_text="Does this goat faint when scared?")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Healthy')
    bio = models.TextField(blank=True)
    image = models.ImageField(upload_to='goats/', blank=True, null=True)

    # Pedigree Fields
    dam = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='kids_dam', verbose_name="Dam (Mother)")
    sire = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='kids_sire', verbose_name="Sire (Father)")

    # USDA Compliance
    scrapie_tag = models.CharField(max_length=20, unique=True, null=True, blank=True, help_text="Official USDA Scrapie Tag ID")
    microchip_id = models.CharField(max_length=30, blank=True, default="", help_text="Microchip/EID number")

    def __str__(self):
        return f"{self.name} ({self.status})"

    @property
    def display_age(self):
        if self.birthdate:
            today = timezone.now().date()
            years = today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
            return f"{years} Years"
        return f"{self.age} Years"

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

class DailyTask(models.Model):
    TIME_CHOICES = [('AM', 'Morning'), ('PM', 'Evening'), ('ANY', 'Anytime')]
    name = models.CharField(max_length=200)
    time_of_day = models.CharField(max_length=3, choices=TIME_CHOICES, default='ANY')

    def __str__(self):
        return f"[{self.get_time_of_day_display()}] {self.name}"

class TaskCompletion(models.Model):
    task = models.ForeignKey(DailyTask, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True, db_index=True)
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
    next_due_date = models.DateField(null=True, blank=True, db_index=True)

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
    due_date = models.DateField(blank=True, null=True, db_index=True, help_text="Auto-calculated if left blank")
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.due_date and self.breeding_date:
            self.due_date = self.breeding_date + timedelta(days=GESTATION_DAYS)
        super().save(*args, **kwargs)

class FeedItem(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. Alfalfa Hay, Goat Pellets")
    quantity = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=20, default="lbs", help_text="e.g. Bales, Bags, lbs")
    low_stock_threshold = models.DecimalField(max_digits=7, decimal_places=2, default=5.00, help_text="Alert when stock drops below this")
    barcode = models.CharField(max_length=50, blank=True, default="", help_text="UPC/EAN barcode")

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def is_low(self):
        return self.quantity <= self.low_stock_threshold

class MilkLog(models.Model):
    TIME_CHOICES = [('AM', 'Morning'), ('PM', 'Evening')]
    goat = models.ForeignKey(Goat, on_delete=models.CASCADE, related_name='milk_logs')
    date = models.DateField(default=timezone.now, db_index=True)
    time = models.CharField(max_length=2, choices=TIME_CHOICES, default='AM')
    amount = models.DecimalField(max_digits=5, decimal_places=2, help_text="Amount in lbs")
    butterfat = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Butterfat %")
    protein = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Protein %")
    somatic_cell_count = models.PositiveIntegerField(null=True, blank=True, help_text="SCC (x1000 cells/ml)")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.goat.name} - {self.date} {self.time} ({self.amount} lbs)"

# --- FINANCE MODEL ---
class Transaction(models.Model):
    TYPES = [('Expense', 'Expense'), ('Income', 'Income')]
    CATEGORIES = [
        ('Feed', 'Feed & Hay'),
        ('Vet', 'Vet & Medical'),
        ('Equipment', 'Equipment & Supplies'),
        ('Goat Sale', 'Goat Sale'),
        ('Product Sale', 'Product Sale (Milk/Soap)'),
        ('Other', 'Other')
    ]

    date = models.DateField(default=timezone.now, db_index=True)
    type = models.CharField(max_length=10, choices=TYPES, default='Expense')
    category = models.CharField(max_length=20, choices=CATEGORIES, default='Other')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.date} - {self.type}: ${self.amount}"

    class Meta:
        ordering = ['-date']

# --- WEIGHT MODEL ---
class WeightLog(models.Model):
    goat = models.ForeignKey('Goat', on_delete=models.CASCADE, related_name='weight_logs')
    date = models.DateField(default=timezone.now, db_index=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in lbs")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['date'] # Ascending for graph

    def __str__(self):
        return f"{self.goat.name} - {self.weight} lbs"

# --- CALENDAR MODEL ---
class FarmEvent(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField(default=timezone.now, verbose_name="Start Date", db_index=True)
    end_date = models.DateField(null=True, blank=True, verbose_name="End Date")
    category = models.CharField(max_length=50, default='General', help_text="e.g. Vet, Show, Maintenance")
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.date} - {self.title}"

# --- NEW MEDICINE MODEL ---
class Medicine(models.Model):
    UNIT_CHOICES = [('ml', 'ml/cc'), ('g', 'grams'), ('pill', 'pills/bolus'), ('oz', 'ounces')]

    name = models.CharField(max_length=100)
    batch = models.CharField(max_length=50, blank=True, help_text="Batch/Lot Number")
    expiration_date = models.DateField(null=True, blank=True, db_index=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Current stock level")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='ml')

    # Dosage Logic: e.g. "1 ml" per "25 lbs"
    dosage_amount = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, help_text="Dose Amount")
    dosage_weight_interval = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Per X lbs bodyweight. Set to 0 for fixed dose.")

    barcode = models.CharField(max_length=50, blank=True, default="", help_text="UPC/EAN barcode")
    notes = models.TextField(blank=True, help_text="Withdrawal times, warnings, etc.")

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def is_expired(self):
        return self.expiration_date and self.expiration_date < timezone.now().date()

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
