from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from .models import (
    Goat, Vet, DailyTask, TaskCompletion, FeedItem, MilkLog,
    Transaction, FarmSettings, MedicalRecord, FeedingLog, BreedingLog,
    WeightLog, GoatLog, GoatPhoto, FarmEvent, Medicine, Customer,
    WaitingList, Sale, MeatHarvest, GrazingArea
)


class GoatModelTest(TestCase):
    def setUp(self):
        self.goat = Goat.objects.create(
            name="Daisy", breed="Nigerian Dwarf", gender="Doe",
            status="Healthy", birthdate=date(2022, 3, 15), age=2
        )

    def test_str(self):
        self.assertEqual(str(self.goat), "Daisy (Healthy)")

    def test_display_age_with_birthdate(self):
        self.assertIn("Years", self.goat.display_age)

    def test_display_age_without_birthdate(self):
        goat = Goat.objects.create(name="Buck", breed="Boer", age=3)
        self.assertEqual(goat.display_age, "3 Years")

    def test_age_in_days_with_birthdate(self):
        expected = (date.today() - date(2022, 3, 15)).days
        self.assertEqual(self.goat.age_in_days, expected)

    def test_age_in_days_without_birthdate(self):
        goat = Goat.objects.create(name="Buck", breed="Boer", age=3)
        self.assertEqual(goat.age_in_days, 3 * 365)

    def test_gender_choices(self):
        for code, _ in Goat.GENDER_CHOICES:
            goat = Goat.objects.create(name=f"Test-{code}", breed="Test", gender=code)
            self.assertEqual(goat.gender, code)


class BreedingLogModelTest(TestCase):
    def setUp(self):
        self.goat = Goat.objects.create(name="Mama", breed="Pygmy")

    def test_auto_due_date(self):
        log = BreedingLog.objects.create(
            goat=self.goat, mate_name="Buck", breeding_date=date(2024, 1, 1)
        )
        self.assertEqual(log.due_date, date(2024, 1, 1) + timedelta(days=150))

    def test_manual_due_date_preserved(self):
        manual_date = date(2024, 7, 1)
        log = BreedingLog.objects.create(
            goat=self.goat, mate_name="Buck",
            breeding_date=date(2024, 1, 1), due_date=manual_date
        )
        self.assertEqual(log.due_date, manual_date)


class FeedItemModelTest(TestCase):
    def test_is_low(self):
        item = FeedItem.objects.create(name="Hay", quantity=3, low_stock_threshold=5)
        self.assertTrue(item.is_low)

    def test_not_low(self):
        item = FeedItem.objects.create(name="Grain", quantity=10, low_stock_threshold=5)
        self.assertFalse(item.is_low)


class MedicineModelTest(TestCase):
    def test_is_expired(self):
        med = Medicine.objects.create(
            name="Expired Med", quantity=10,
            expiration_date=date.today() - timedelta(days=1)
        )
        self.assertTrue(med.is_expired)

    def test_not_expired(self):
        med = Medicine.objects.create(
            name="Fresh Med", quantity=10,
            expiration_date=date.today() + timedelta(days=30)
        )
        self.assertFalse(med.is_expired)

    def test_dosage_instruction_weight_based(self):
        med = Medicine.objects.create(
            name="Test", quantity=10, dosage_amount=1, dosage_weight_interval=25
        )
        self.assertIn("/", med.dosage_instruction)

    def test_dosage_instruction_fixed(self):
        med = Medicine.objects.create(
            name="Test", quantity=10, dosage_amount=2, dosage_weight_interval=0
        )
        self.assertIn("Fixed", med.dosage_instruction)


class MeatHarvestModelTest(TestCase):
    def test_yield_percentage(self):
        goat = Goat.objects.create(name="Test", breed="Boer")
        harvest = MeatHarvest.objects.create(
            goat=goat, live_weight=100, hanging_weight=50
        )
        self.assertEqual(harvest.yield_percentage, 50.0)

    def test_yield_zero_weight(self):
        goat = Goat.objects.create(name="Test", breed="Boer")
        harvest = MeatHarvest.objects.create(
            goat=goat, live_weight=0, hanging_weight=0
        )
        self.assertEqual(harvest.yield_percentage, 0)


# =====================
# VIEW TESTS
# =====================

class ViewTestBase(TestCase):
    """Base class with common setup for view tests."""
    def setUp(self):
        FarmSettings.objects.get_or_create(pk=1)
        self.client = Client()
        self.goat = Goat.objects.create(
            name="Daisy", breed="Nigerian Dwarf", gender="Doe",
            status="Healthy", birthdate=date(2022, 3, 15)
        )

    def _disable_pin(self):
        """Ensure PIN gate doesn't block tests."""
        session = self.client.session
        session['pin_authenticated'] = True
        session.save()


class IndexViewTest(ViewTestBase):
    def test_index_loads(self):
        self._disable_pin()
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daisy")

    def test_index_shows_goat_gender(self):
        self._disable_pin()
        response = self.client.get(reverse('index'))
        self.assertContains(response, "Doe")

    def test_index_shows_alerts(self):
        self._disable_pin()
        FeedItem.objects.create(name="Hay", quantity=2, low_stock_threshold=5)
        response = self.client.get(reverse('index'))
        self.assertContains(response, "Hay")


class GoatDetailViewTest(ViewTestBase):
    def test_detail_loads(self):
        self._disable_pin()
        response = self.client.get(reverse('goat_detail', args=[self.goat.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daisy")

    def test_edit_button_present(self):
        self._disable_pin()
        response = self.client.get(reverse('goat_detail', args=[self.goat.id]))
        self.assertContains(response, "Edit Profile")

    def test_add_daily_log(self):
        self._disable_pin()
        response = self.client.post(
            reverse('goat_detail', args=[self.goat.id]),
            {'note': 'Test log entry'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GoatLog.objects.count(), 1)

    def test_delete_buttons_present(self):
        self._disable_pin()
        record = MedicalRecord.objects.create(
            goat=self.goat, record_type='Vaccine',
            date=date.today(), notes='Test vaccine'
        )
        response = self.client.get(reverse('goat_detail', args=[self.goat.id]))
        delete_url = reverse('delete_medical_record', args=[record.id])
        self.assertContains(response, delete_url)


class VetCRUDTest(ViewTestBase):
    def test_add_vet(self):
        self._disable_pin()
        response = self.client.post(reverse('add_vet'), {
            'name': 'Dr. Smith', 'phone': '555-1234',
            'address': '123 Main St', 'email': 'dr@vet.com'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vet.objects.count(), 1)
        self.assertEqual(Vet.objects.first().name, 'Dr. Smith')

    def test_delete_vet(self):
        self._disable_pin()
        vet = Vet.objects.create(name='Dr. Smith', phone='555-1234', address='123 Main')
        response = self.client.post(reverse('delete_vet', args=[vet.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vet.objects.count(), 0)

    def test_delete_vet_requires_post(self):
        self._disable_pin()
        vet = Vet.objects.create(name='Dr. Smith', phone='555-1234', address='123 Main')
        response = self.client.get(reverse('delete_vet', args=[vet.id]))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Vet.objects.count(), 1)


class TaskCRUDTest(ViewTestBase):
    def test_add_task(self):
        self._disable_pin()
        response = self.client.post(reverse('add_task'), {
            'name': 'Feed goats', 'time_of_day': 'AM'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DailyTask.objects.count(), 1)

    def test_delete_task(self):
        self._disable_pin()
        task = DailyTask.objects.create(name='Feed goats', time_of_day='AM')
        response = self.client.post(reverse('delete_task', args=[task.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DailyTask.objects.count(), 0)

    def test_toggle_task(self):
        self._disable_pin()
        task = DailyTask.objects.create(name='Feed goats', time_of_day='AM')
        response = self.client.post(reverse('toggle_task', args=[task.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TaskCompletion.objects.filter(task=task, completed=True).exists()
        )

    def test_toggle_task_ajax(self):
        self._disable_pin()
        task = DailyTask.objects.create(name='Feed goats')
        response = self.client.post(
            reverse('toggle_task', args=[task.id]),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['completed'])


class FeedItemCRUDTest(ViewTestBase):
    def test_add_feed_item(self):
        self._disable_pin()
        response = self.client.post(reverse('add_feed_item'), {
            'name': 'Alfalfa', 'quantity': '10', 'unit': 'bales',
            'low_stock_threshold': '3'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedItem.objects.count(), 1)

    def test_delete_feed_item(self):
        self._disable_pin()
        item = FeedItem.objects.create(name='Hay', quantity=10)
        response = self.client.post(reverse('delete_feed_item', args=[item.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedItem.objects.count(), 0)

    def test_update_inventory(self):
        self._disable_pin()
        item = FeedItem.objects.create(name='Hay', quantity=10)
        self.client.post(reverse('update_inventory', args=[item.id]), {'amount': '5'})
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('15.00'))

    def test_update_inventory_prevents_negative(self):
        self._disable_pin()
        item = FeedItem.objects.create(name='Hay', quantity=3)
        self.client.post(reverse('update_inventory', args=[item.id]), {'amount': '-10'})
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal('0.00'))


class GoatEditTest(ViewTestBase):
    def test_edit_goat_form_loads(self):
        self._disable_pin()
        response = self.client.get(reverse('edit_goat', args=[self.goat.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daisy")

    def test_edit_goat_saves(self):
        self._disable_pin()
        response = self.client.post(
            reverse('edit_goat', args=[self.goat.id]),
            {'name': 'Daisy Mae', 'breed': 'Nigerian Dwarf', 'gender': 'Doe',
             'status': 'Healthy', 'age': 2}
        )
        self.assertEqual(response.status_code, 302)
        self.goat.refresh_from_db()
        self.assertEqual(self.goat.name, 'Daisy Mae')


class DeleteRecordTests(ViewTestBase):
    def test_delete_medical_record(self):
        self._disable_pin()
        record = MedicalRecord.objects.create(
            goat=self.goat, record_type='Vaccine', date=date.today()
        )
        response = self.client.post(reverse('delete_medical_record', args=[record.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MedicalRecord.objects.count(), 0)

    def test_delete_weight_log(self):
        self._disable_pin()
        log = WeightLog.objects.create(goat=self.goat, date=date.today(), weight=50)
        response = self.client.post(reverse('delete_weight_log', args=[log.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WeightLog.objects.count(), 0)

    def test_delete_feeding_log(self):
        self._disable_pin()
        log = FeedingLog.objects.create(
            goat=self.goat, feed_type='Hay', amount='1 flake', date=date.today()
        )
        response = self.client.post(reverse('delete_feeding_log', args=[log.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedingLog.objects.count(), 0)

    def test_delete_breeding_log(self):
        self._disable_pin()
        log = BreedingLog.objects.create(
            goat=self.goat, mate_name='Buck', breeding_date=date.today()
        )
        response = self.client.post(reverse('delete_breeding_log', args=[log.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BreedingLog.objects.count(), 0)

    def test_delete_milk_log(self):
        self._disable_pin()
        log = MilkLog.objects.create(goat=self.goat, date=date.today(), amount=1.5)
        response = self.client.post(reverse('delete_milk_log', args=[log.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MilkLog.objects.count(), 0)

    def test_delete_goat_log(self):
        self._disable_pin()
        log = GoatLog.objects.create(goat=self.goat, note='Test note')
        response = self.client.post(reverse('delete_goat_log', args=[log.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GoatLog.objects.count(), 0)

    def test_delete_transaction(self):
        self._disable_pin()
        txn = Transaction.objects.create(
            date=date.today(), type='Expense', category='Feed', amount=50
        )
        response = self.client.post(reverse('delete_transaction', args=[txn.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_delete_requires_post(self):
        """All delete endpoints should reject GET requests."""
        self._disable_pin()
        record = MedicalRecord.objects.create(
            goat=self.goat, record_type='Vaccine', date=date.today()
        )
        response = self.client.get(reverse('delete_medical_record', args=[record.id]))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(MedicalRecord.objects.count(), 1)


class SalesViewTest(ViewTestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(name='John Doe', phone='555-1234')

    def test_sales_list_loads(self):
        self._disable_pin()
        response = self.client.get(reverse('sales_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sales Ledger")

    def test_sales_revenue_computed(self):
        self._disable_pin()
        Sale.objects.create(
            customer=self.customer, goat=self.goat,
            sale_date=date.today(), sale_price=500, deposit_amount=100,
            is_paid_in_full=False
        )
        Sale.objects.create(
            customer=self.customer, goat=self.goat,
            sale_date=date.today(), sale_price=300, deposit_amount=300,
            is_paid_in_full=True
        )
        response = self.client.get(reverse('sales_list'))
        # Total revenue = 500 + 300 = 800
        self.assertContains(response, '800.00')
        # Pending = 500 - 100 = 400
        self.assertContains(response, '400.00')

    def test_add_sale(self):
        self._disable_pin()
        response = self.client.post(reverse('add_sale'), {
            'customer': self.customer.id, 'goat': self.goat.id,
            'sale_date': '2024-06-01', 'sale_price': '250',
            'deposit_amount': '50'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)

    def test_toggle_sale_paid(self):
        self._disable_pin()
        sale = Sale.objects.create(
            customer=self.customer, goat=self.goat,
            sale_date=date.today(), sale_price=500, is_paid_in_full=False
        )
        self.client.post(reverse('toggle_sale_paid', args=[sale.id]))
        sale.refresh_from_db()
        self.assertTrue(sale.is_paid_in_full)
        # Toggle back
        self.client.post(reverse('toggle_sale_paid', args=[sale.id]))
        sale.refresh_from_db()
        self.assertFalse(sale.is_paid_in_full)

    def test_delete_sale(self):
        self._disable_pin()
        sale = Sale.objects.create(
            customer=self.customer, goat=self.goat,
            sale_date=date.today(), sale_price=500
        )
        response = self.client.post(reverse('delete_sale', args=[sale.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 0)


class CustomerCRUDTest(ViewTestBase):
    def test_add_customer(self):
        self._disable_pin()
        response = self.client.post(reverse('crm_dashboard'), {
            'customer_name': 'Jane Doe',
            'customer_email': 'jane@example.com',
            'customer_phone': '555-9876',
            'customer_notes': 'Interested in doelings'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.count(), 1)

    def test_edit_customer(self):
        self._disable_pin()
        customer = Customer.objects.create(name='Jane', phone='555-1111')
        response = self.client.post(
            reverse('edit_customer', args=[customer.id]),
            {'name': 'Jane Doe', 'email': 'jane@new.com', 'phone': '555-2222', 'notes': ''}
        )
        self.assertEqual(response.status_code, 302)
        customer.refresh_from_db()
        self.assertEqual(customer.name, 'Jane Doe')
        self.assertEqual(customer.phone, '555-2222')

    def test_delete_customer(self):
        self._disable_pin()
        customer = Customer.objects.create(name='Jane')
        response = self.client.post(reverse('delete_customer', args=[customer.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.count(), 0)


class DashboardViewTests(ViewTestBase):
    def test_milk_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('milk_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_milk_log_post(self):
        self._disable_pin()
        response = self.client.post(reverse('milk_dashboard'), {
            'goat': self.goat.id, 'date': '2024-06-01',
            'time': 'AM', 'amount': '2.5'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MilkLog.objects.count(), 1)

    def test_breeding_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('breeding_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_silo_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('silo_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_finance_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('finance_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_finance_add_transaction(self):
        self._disable_pin()
        response = self.client.post(reverse('finance_dashboard'), {
            'date': '2024-06-01', 'type': 'Expense',
            'category': 'Feed', 'amount': '45.99',
            'description': '10 bales of hay'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_weight_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('weight_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_calendar_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('calendar_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_medicine_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('medicine_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_tools_dashboard(self):
        self._disable_pin()
        response = self.client.get(reverse('tools_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_meat_locker(self):
        self._disable_pin()
        response = self.client.get(reverse('meat_locker'))
        self.assertEqual(response.status_code, 200)


class AddGoatViewTest(ViewTestBase):
    def test_add_goat_form_loads(self):
        self._disable_pin()
        response = self.client.get(reverse('add_goat'))
        self.assertEqual(response.status_code, 200)

    def test_add_goat_post(self):
        self._disable_pin()
        response = self.client.post(reverse('add_goat'), {
            'name': 'Pepper', 'breed': 'Pygmy', 'gender': 'Buck',
            'status': 'Healthy', 'age': 1
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Goat.objects.filter(name='Pepper').exists())


class SecurityTests(ViewTestBase):
    def test_toggle_sick_requires_post(self):
        self._disable_pin()
        response = self.client.get(reverse('toggle_sick', args=[self.goat.id]))
        self.assertEqual(response.status_code, 405)

    def test_quick_milk_requires_post(self):
        self._disable_pin()
        response = self.client.get(reverse('quick_milk', args=[self.goat.id]))
        self.assertEqual(response.status_code, 405)

    def test_delete_event_requires_post(self):
        self._disable_pin()
        event = FarmEvent.objects.create(title='Test', date=date.today())
        response = self.client.get(reverse('delete_event_api', args=[event.id]))
        self.assertEqual(response.status_code, 405)

    def test_move_event_requires_post(self):
        self._disable_pin()
        response = self.client.get(reverse('move_event'))
        self.assertEqual(response.status_code, 405)


class CSVExportTest(ViewTestBase):
    def test_export_goats(self):
        self._disable_pin()
        response = self.client.get(reverse('export_goats'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('goats_export.csv', response['Content-Disposition'])

    def test_export_finances(self):
        self._disable_pin()
        response = self.client.get(reverse('export_finances'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_export_milk(self):
        self._disable_pin()
        response = self.client.get(reverse('export_milk'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_export_medical(self):
        self._disable_pin()
        response = self.client.get(reverse('export_medical'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')


class PinGateTest(TestCase):
    def setUp(self):
        FarmSettings.objects.get_or_create(pk=1)

    def test_pin_login_page_loads(self):
        response = self.client.get(reverse('pin_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GoatOS')

    def test_pin_login_wrong_pin(self):
        with self.settings(FARM_PIN='1234'):
            response = self.client.post(reverse('pin_login'), {'pin': '0000'})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Incorrect PIN')

    def test_pin_login_correct_pin(self):
        with self.settings(FARM_PIN='1234'):
            response = self.client.post(reverse('pin_login'), {'pin': '1234'})
            self.assertEqual(response.status_code, 302)

    def test_pin_logout(self):
        session = self.client.session
        session['pin_authenticated'] = True
        session.save()
        response = self.client.get(reverse('pin_logout'))
        self.assertEqual(response.status_code, 302)


class SuccessMessageTests(ViewTestBase):
    """Verify success messages are shown after POST actions."""

    def test_add_vet_shows_message(self):
        self._disable_pin()
        response = self.client.post(
            reverse('add_vet'),
            {'name': 'Dr. Test', 'phone': '555-0000', 'address': 'Here'},
            follow=True
        )
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Vet contact added' in str(m) for m in messages))

    def test_add_task_shows_message(self):
        self._disable_pin()
        response = self.client.post(
            reverse('add_task'),
            {'name': 'Test task', 'time_of_day': 'AM'},
            follow=True
        )
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Task added' in str(m) for m in messages))

    def test_finance_transaction_shows_message(self):
        self._disable_pin()
        response = self.client.post(
            reverse('finance_dashboard'),
            {'date': '2024-01-01', 'type': 'Expense', 'category': 'Feed',
             'amount': '25', 'description': 'Test'},
            follow=True
        )
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Transaction recorded' in str(m) for m in messages))
