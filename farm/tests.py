from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .constants import GESTATION_DAYS, HEAT_CYCLE_DAYS, HEAT_STRESS_THRESHOLD_F, FREEZE_WARNING_THRESHOLD_F
from .models import (
    Goat, BreedingLog, MeatHarvest, Medicine, FeedItem, FeedingLog,
    MilkLog, Transaction, WeightLog, MedicalRecord,
    FarmSettings, FarmEvent, GrazingArea,
)


def _create_goat(**kwargs):
    defaults = {'name': 'TestGoat', 'breed': 'Nigerian Dwarf', 'status': 'Healthy'}
    defaults.update(kwargs)
    return Goat.objects.create(**defaults)


class BreedingLogModelTests(TestCase):
    def test_gestation_auto_calculated(self):
        goat = _create_goat()
        breeding_date = timezone.now().date() - timedelta(days=10)
        log = BreedingLog.objects.create(goat=goat, mate_name='Buck', breeding_date=breeding_date)
        self.assertEqual(log.due_date, breeding_date + timedelta(days=GESTATION_DAYS))

    def test_explicit_due_date_not_overwritten(self):
        goat = _create_goat()
        explicit_date = timezone.now().date() + timedelta(days=100)
        log = BreedingLog.objects.create(
            goat=goat, mate_name='Buck',
            breeding_date=timezone.now().date(),
            due_date=explicit_date,
        )
        self.assertEqual(log.due_date, explicit_date)


class GoatModelTests(TestCase):
    def test_display_age_with_birthdate(self):
        goat = _create_goat(birthdate=timezone.now().date() - timedelta(days=365 * 3 + 10))
        self.assertIn('3 Years', goat.display_age)

    def test_display_age_without_birthdate(self):
        goat = _create_goat(age=5)
        self.assertEqual(goat.display_age, '5 Years')


class MeatHarvestModelTests(TestCase):
    def test_yield_percentage(self):
        goat = _create_goat()
        harvest = MeatHarvest(goat=goat, live_weight=100, hanging_weight=50)
        self.assertAlmostEqual(harvest.yield_percentage, 50.0)

    def test_yield_zero_live_weight(self):
        goat = _create_goat()
        harvest = MeatHarvest(goat=goat, live_weight=0, hanging_weight=0)
        self.assertEqual(harvest.yield_percentage, 0)


class MedicineModelTests(TestCase):
    def test_is_expired_true(self):
        med = Medicine(
            name='Test Med', quantity=10, unit='ml',
            expiration_date=timezone.now().date() - timedelta(days=1),
        )
        self.assertTrue(med.is_expired)

    def test_is_expired_false(self):
        med = Medicine(
            name='Test Med', quantity=10, unit='ml',
            expiration_date=timezone.now().date() + timedelta(days=30),
        )
        self.assertFalse(med.is_expired)

    def test_dosage_instruction_weight_based(self):
        med = Medicine(name='Ivermectin', quantity=50, unit='ml', dosage_amount=1, dosage_weight_interval=25)
        self.assertEqual(med.dosage_instruction, '1ml / 25lbs')

    def test_dosage_instruction_fixed(self):
        med = Medicine(name='Bolus', quantity=10, unit='pill', dosage_amount=2, dosage_weight_interval=0)
        self.assertEqual(med.dosage_instruction, '2pill (Fixed)')


class FeedItemModelTests(TestCase):
    def test_is_low_true(self):
        item = FeedItem(name='Hay', quantity=3, unit='Bales', low_stock_threshold=5)
        self.assertTrue(item.is_low)

    def test_is_low_false(self):
        item = FeedItem(name='Hay', quantity=10, unit='Bales', low_stock_threshold=5)
        self.assertFalse(item.is_low)


class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_login_page_renders(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GoatOS')

    def test_valid_login_redirects(self):
        response = self.client.post(reverse('login'), {'username': 'farmer', 'password': 'testpass123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_logout_redirects(self):
        self.client.login(username='farmer', password='testpass123')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)


class ViewAccessTests(TestCase):
    """Verify unauthenticated requests redirect to login."""
    def setUp(self):
        FarmSettings.objects.get_or_create(pk=1)

    def test_index_requires_login(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_milk_requires_login(self):
        response = self.client.get(reverse('milk_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_finance_requires_login(self):
        response = self.client.get(reverse('finance_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_api_goats_requires_login(self):
        response = self.client.get(reverse('api_goats_list'))
        self.assertEqual(response.status_code, 302)


class MilkDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.goat = _create_goat()

    def test_post_creates_record(self):
        response = self.client.post(reverse('milk_dashboard'), {
            'goat': self.goat.id,
            'date': timezone.now().date().isoformat(),
            'time': 'AM',
            'amount': '2.50',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MilkLog.objects.count(), 1)

    def test_invalid_post_no_record(self):
        self.client.post(reverse('milk_dashboard'), {
            'goat': '',
            'date': '',
            'time': 'AM',
            'amount': '',
        })
        self.assertEqual(MilkLog.objects.count(), 0)


class FinanceDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_post_creates_transaction(self):
        response = self.client.post(reverse('finance_dashboard'), {
            'type': 'Expense',
            'date': timezone.now().date().isoformat(),
            'category': 'Feed',
            'amount': '49.99',
            'description': 'Hay bales',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 1)


class WeightRecordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.goat = _create_goat()

    def test_add_weight_record(self):
        response = self.client.post(reverse('add_weight_record', args=[self.goat.id]), {
            'date': timezone.now().date().isoformat(),
            'weight': '85.50',
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WeightLog.objects.count(), 1)

    def test_add_medical_record(self):
        response = self.client.post(reverse('add_medical_record', args=[self.goat.id]), {
            'record_type': 'Vaccine',
            'date': timezone.now().date().isoformat(),
            'notes': 'CDT vaccine',
            'next_due_date': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MedicalRecord.objects.count(), 1)


class CSVExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_milk_csv_export(self):
        response = self.client.get(reverse('export_milk_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_transactions_csv_export(self):
        response = self.client.get(reverse('export_transactions_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_medical_csv_export(self):
        response = self.client.get(reverse('export_medical_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')


class APITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.goat = _create_goat(name='Buttercup')

    def test_goats_list_returns_json(self):
        response = self.client.get(reverse('api_goats_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertIn('goats', data)
        self.assertEqual(len(data['goats']), 1)

    def test_goat_detail_returns_correct_data(self):
        response = self.client.get(reverse('api_goat_detail', args=[self.goat.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Buttercup')

    def test_api_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('api_goats_list'))
        self.assertEqual(response.status_code, 302)


# ===== Phase 1-6 Feature Tests =====

class ScrapieTagTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_scrapie_tag_unique(self):
        _create_goat(name='Goat1', scrapie_tag='US-001')
        with self.assertRaises(Exception):
            _create_goat(name='Goat2', scrapie_tag='US-001')

    def test_scrapie_tag_optional(self):
        goat = _create_goat(name='NoTag')
        self.assertIsNone(goat.scrapie_tag)

    def test_api_includes_scrapie_tag(self):
        _create_goat(name='Tagged', scrapie_tag='US-100')
        response = self.client.get(reverse('api_goats_list'))
        data = response.json()
        self.assertEqual(data['goats'][0]['scrapie_tag'], 'US-100')

    def test_api_detail_includes_microchip(self):
        goat = _create_goat(name='Chipped', microchip_id='CHIP-999')
        response = self.client.get(reverse('api_goat_detail', args=[goat.id]))
        data = response.json()
        self.assertEqual(data['microchip_id'], 'CHIP-999')


class MilkQualityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.goat = _create_goat()

    def test_quality_fields_optional(self):
        log = MilkLog.objects.create(goat=self.goat, date=timezone.now().date(), time='AM', amount=3.0)
        self.assertIsNone(log.butterfat)
        self.assertIsNone(log.protein)
        self.assertIsNone(log.somatic_cell_count)

    def test_quality_fields_save(self):
        log = MilkLog.objects.create(
            goat=self.goat, date=timezone.now().date(), time='AM', amount=3.0,
            butterfat=4.50, protein=3.20, somatic_cell_count=150,
        )
        log.refresh_from_db()
        self.assertAlmostEqual(float(log.butterfat), 4.50)
        self.assertAlmostEqual(float(log.protein), 3.20)
        self.assertEqual(log.somatic_cell_count, 150)

    def test_milk_csv_includes_quality(self):
        MilkLog.objects.create(
            goat=self.goat, date=timezone.now().date(), time='AM', amount=3.0,
            butterfat=4.50, protein=3.20, somatic_cell_count=150,
        )
        response = self.client.get(reverse('export_milk_csv'))
        content = response.content.decode()
        self.assertIn('Butterfat', content)
        self.assertIn('4.50', content)


class PrintReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.goat = _create_goat()

    def test_herd_summary_200(self):
        response = self.client.get(reverse('print_herd_summary'))
        self.assertEqual(response.status_code, 200)

    def test_goat_health_200(self):
        response = self.client.get(reverse('print_goat_health', args=[self.goat.id]))
        self.assertEqual(response.status_code, 200)

    def test_breeding_report_200(self):
        response = self.client.get(reverse('print_breeding_report'))
        self.assertEqual(response.status_code, 200)

    def test_financial_summary_200(self):
        response = self.client.get(reverse('print_financial_summary'))
        self.assertEqual(response.status_code, 200)


class PedigreeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.granddam = _create_goat(name='GrandDam')
        self.dam = _create_goat(name='MotherGoat', dam=self.granddam)
        self.sire = _create_goat(name='FatherGoat')
        self.goat = _create_goat(name='BabyGoat', dam=self.dam, sire=self.sire)

    def test_pedigree_renders(self):
        response = self.client.get(reverse('goat_pedigree', args=[self.goat.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MotherGoat')
        self.assertContains(response, 'FatherGoat')

    def test_pedigree_shows_grandparent(self):
        response = self.client.get(reverse('goat_pedigree', args=[self.goat.id]))
        self.assertContains(response, 'GrandDam')

    def test_pedigree_shows_descendants(self):
        response = self.client.get(reverse('goat_pedigree', args=[self.dam.id]))
        self.assertContains(response, 'BabyGoat')


class BackupRestoreTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='adminpass')
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_backup_requires_superuser(self):
        self.client.login(username='farmer', password='testpass123')
        response = self.client.get(reverse('backup_database'))
        self.assertNotEqual(response.status_code, 200)

    def test_backup_superuser_can_access(self):
        self.client.login(username='admin', password='adminpass')
        response = self.client.get(reverse('backup_database'))
        # In-memory test DB has no file, so view redirects to tools_dashboard
        # (not to login). This proves superuser access is granted.
        if response.status_code == 200:
            self.assertIn('goatos_backup_', response['Content-Disposition'])
        else:
            self.assertEqual(response.status_code, 302)
            self.assertIn('tools', response.url)


class BarcodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_barcode_finds_feed(self):
        FeedItem.objects.create(name='Hay Pellets', quantity=50, unit='lbs', barcode='123456789')
        response = self.client.get(reverse('api_lookup_barcode'), {'barcode': '123456789'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'feed')
        self.assertEqual(data['name'], 'Hay Pellets')

    def test_barcode_finds_medicine(self):
        Medicine.objects.create(name='Penicillin', quantity=100, unit='ml', barcode='MED-001')
        response = self.client.get(reverse('api_lookup_barcode'), {'barcode': 'MED-001'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'medicine')

    def test_barcode_not_found(self):
        response = self.client.get(reverse('api_lookup_barcode'), {'barcode': 'DOESNOTEXIST'})
        self.assertEqual(response.status_code, 404)


class BreedingPlannerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.doe = _create_goat(name='Daisy')
        self.buck = _create_goat(name='Thunder')

    def test_planner_page_renders(self):
        response = self.client.get(reverse('breeding_planner'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Breeding Planner')

    def test_plan_breeding_creates_event(self):
        response = self.client.post(reverse('breeding_planner'), {
            'goat_id': self.doe.id,
            'mate_name': 'Thunder',
            'plan_date': timezone.now().date().isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FarmEvent.objects.count(), 1)
        self.assertIn('Daisy', FarmEvent.objects.first().title)

    def test_heat_cycles_returns_6(self):
        BreedingLog.objects.create(
            goat=self.doe, mate_name='Thunder',
            breeding_date=timezone.now().date() - timedelta(days=30),
        )
        response = self.client.get(reverse('api_heat_cycles', args=[self.doe.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['cycles']), 6)

    def test_heat_cycles_spacing(self):
        breed_date = timezone.now().date() - timedelta(days=10)
        BreedingLog.objects.create(goat=self.doe, mate_name='Thunder', breeding_date=breed_date)
        response = self.client.get(reverse('api_heat_cycles', args=[self.doe.id]))
        data = response.json()
        first_start = data['cycles'][0]['start']
        expected = (breed_date + timedelta(days=HEAT_CYCLE_DAYS)).isoformat()
        self.assertEqual(first_start, expected)

    def test_inbreeding_detects_shared_ancestor(self):
        grandma = _create_goat(name='Grandma')
        mom = _create_goat(name='Mom', dam=grandma)
        aunt = _create_goat(name='Aunt', dam=grandma)
        kid1 = _create_goat(name='Kid1', dam=mom)
        kid2 = _create_goat(name='Kid2', dam=aunt)
        response = self.client.get(reverse('api_check_inbreeding'), {'goat1': kid1.id, 'goat2': kid2.id})
        data = response.json()
        self.assertTrue(data['has_shared_ancestors'])
        self.assertIn('Grandma', data['shared_ancestors'])

    def test_inbreeding_no_shared(self):
        g1 = _create_goat(name='Unrelated1')
        g2 = _create_goat(name='Unrelated2')
        response = self.client.get(reverse('api_check_inbreeding'), {'goat1': g1.id, 'goat2': g2.id})
        data = response.json()
        self.assertFalse(data['has_shared_ancestors'])


# ===== Round 3 Feature Tests =====

class GoatFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_add_goat_get(self):
        response = self.client.get(reverse('add_goat'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register')

    def test_add_goat_post(self):
        response = self.client.post(reverse('add_goat'), {
            'name': 'Buttercup',
            'breed': 'Nubian',
            'age': '2',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Goat.objects.filter(name='Buttercup').exists())

    def test_edit_goat_get(self):
        goat = _create_goat(name='Clover')
        response = self.client.get(reverse('edit_goat', args=[goat.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clover')

    def test_edit_goat_post(self):
        goat = _create_goat(name='Clover', breed='Alpine')
        response = self.client.post(reverse('edit_goat', args=[goat.id]), {
            'name': 'Clover',
            'breed': 'Saanen',
            'age': '3',
        })
        self.assertEqual(response.status_code, 302)
        goat.refresh_from_db()
        self.assertEqual(goat.breed, 'Saanen')


class GrazingAreaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.area = GrazingArea.objects.create(
            name='North Pasture', color='#00FF00',
            coordinates='[{"lat": 38.0, "lng": -95.0}]',
        )

    def test_zone_update_via_put(self):
        import json
        response = self.client.put(
            reverse('api_update_grazing_area', args=[self.area.id]),
            data=json.dumps({'name': 'South Pasture', 'color': '#FF0000'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.area.refresh_from_db()
        self.assertEqual(self.area.name, 'South Pasture')

    def test_zone_delete(self):
        goat = _create_goat(name='Zoner', grazing_area=self.area)
        response = self.client.delete(
            reverse('api_delete_grazing_area', args=[self.area.id]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GrazingArea.objects.filter(pk=self.area.id).exists())
        goat.refresh_from_db()
        self.assertIsNone(goat.grazing_area)

    def test_zone_delete_unassigns_goats(self):
        goat = _create_goat(name='PastureGoat', grazing_area=self.area)
        self.client.delete(reverse('api_delete_grazing_area', args=[self.area.id]))
        goat.refresh_from_db()
        self.assertIsNone(goat.grazing_area)


class MapPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)

    def test_map_page_renders(self):
        response = self.client.get(reverse('map_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Farm Map')

    def test_map_page_shows_zones(self):
        GrazingArea.objects.create(
            name='East Field', color='#0000FF',
            coordinates='[{"lat": 38.0, "lng": -95.0}]',
        )
        response = self.client.get(reverse('map_page'))
        self.assertContains(response, 'East Field')


class GoatZoneAssignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.area = GrazingArea.objects.create(
            name='West Field', color='#FF00FF',
            coordinates='[{"lat": 38.0, "lng": -95.0}]',
        )
        self.goat = _create_goat(name='Wanderer')

    def test_assign_goat_to_zone(self):
        import json
        response = self.client.post(
            reverse('api_assign_goat_zone', args=[self.goat.id]),
            data=json.dumps({'zone_id': self.area.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.goat.refresh_from_db()
        self.assertEqual(self.goat.grazing_area, self.area)

    def test_goat_detail_shows_zone(self):
        self.goat.grazing_area = self.area
        self.goat.save()
        response = self.client.get(reverse('goat_detail', args=[self.goat.id]))
        self.assertContains(response, 'West Field')


class FeedConsumptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1)
        self.goat = _create_goat(name='Muncher')
        self.feed_item = FeedItem.objects.create(name='Alfalfa', quantity=100, unit='lbs')

    def test_feeding_with_quantity_deducts_inventory(self):
        response = self.client.post(reverse('add_feeding_record', args=[self.goat.id]), {
            'date': timezone.now().date().isoformat(),
            'feed_type': 'Hay',
            'amount': '2 flakes',
            'quantity': '5.00',
            'unit': 'lbs',
            'feed_item': self.feed_item.id,
        })
        self.assertEqual(response.status_code, 302)
        self.feed_item.refresh_from_db()
        self.assertEqual(float(self.feed_item.quantity), 95.0)

    def test_feeding_without_quantity_no_deduction(self):
        response = self.client.post(reverse('add_feeding_record', args=[self.goat.id]), {
            'date': timezone.now().date().isoformat(),
            'feed_type': 'Grain',
            'amount': '1 scoop',
        })
        self.assertEqual(response.status_code, 302)
        self.feed_item.refresh_from_db()
        self.assertEqual(float(self.feed_item.quantity), 100.0)

    def test_feed_efficiency_in_context(self):
        # Create milk + feed data
        MilkLog.objects.create(goat=self.goat, date=timezone.now().date(), time='AM', amount=5.0)
        FeedingLog.objects.create(
            goat=self.goat, date=timezone.now().date(), feed_type='Hay',
            amount='2 flakes', quantity=10,
        )
        response = self.client.get(reverse('goat_detail', args=[self.goat.id]))
        self.assertEqual(response.status_code, 200)
        # feed_efficiency should be in context (5.0 / 10.0 = 0.5)
        self.assertEqual(response.context['feed_efficiency'], 0.5)


class WeatherForecastTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer', password='testpass123')
        self.client.login(username='farmer', password='testpass123')
        FarmSettings.objects.get_or_create(pk=1, defaults={
            'name': 'Test Farm', 'latitude': 38.0, 'longitude': -95.0,
        })

    def test_index_has_weather_forecast_key(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('weather_forecast', response.context)
        self.assertIn('weather_alerts', response.context)

    def test_heat_alert_threshold(self):
        """Verify the heat stress constant is reasonable."""
        self.assertEqual(HEAT_STRESS_THRESHOLD_F, 95)

    def test_freeze_alert_threshold(self):
        """Verify the freeze warning constant is reasonable."""
        self.assertEqual(FREEZE_WARNING_THRESHOLD_F, 32)
