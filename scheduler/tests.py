import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from core_rail.models import Zone, Division, Corridor, TrainSchedule
from maintenance.models import MaintenanceDemand, MachineAsset
from scheduler.models import BlockSchedule, OptimizationRun
from scheduler.optimizer import calculate_criticality_score, optimize_block_schedule, replan_emergency_defect


class RailSyncAITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.zone = Zone.objects.create(code='NCR', name='North Central Railway')
        self.division = Division.objects.create(zone=self.zone, code='PRYJ', name='Prayagraj')
        self.corridor = Corridor.objects.create(
            division=self.division,
            code='GZB-CNB',
            name='Ghaziabad - Kanpur',
            start_station='GZB',
            end_station='CNB',
            start_km=20.0,
            end_km=435.0,
            gmt=45.0,
            daily_trains=120
        )

        today = timezone.now().date()
        self.demand_tms = MaintenanceDemand.objects.create(
            demand_id='TEST-TMS-01',
            source_system='TMS',
            corridor=self.corridor,
            track_line='UP',
            km_start=125.0,
            km_end=128.0,
            activity_name='Track Tamping by CSM',
            defect_description='Overdue track packing',
            criticality='URGENT_I',
            duration_hours=3.0,
            due_date=today,
            overdue_days=5,
            speed_restriction_imposed=True,
            speed_restriction_kmh=30
        )

        self.demand_tdms = MaintenanceDemand.objects.create(
            demand_id='TEST-TDMS-01',
            source_system='TDMS',
            corridor=self.corridor,
            track_line='UP',
            km_start=125.5,
            km_end=127.5,
            activity_name='OHE Inspection',
            defect_description='Cantilever overhaul',
            criticality='NORMAL_II',
            duration_hours=2.5,
            due_date=today,
            overdue_days=2,
            requires_power_block=True
        )

    def test_criticality_scoring_algorithm(self):
        """Verify AI Criticality & Urgency engine calculates higher risk score for urgent/TSR demands"""
        score_tms, notes_tms = calculate_criticality_score(self.demand_tms)
        score_tdms, notes_tdms = calculate_criticality_score(self.demand_tdms)
        
        self.assertGreater(score_tms, 60.0)
        self.assertGreater(score_tms, score_tdms)
        self.assertIn("TSR ACTIVE", notes_tms)
        self.assertIn("OVERDUE PENALTY", notes_tms)

    def test_multi_department_shadow_bundling(self):
        """Verify co-located TMS and TDMS demands are bundled together into a single coordinated block"""
        result = optimize_block_schedule(horizon='WEEKLY')
        
        self.assertEqual(result['status'], 'success')
        self.assertGreaterEqual(result['blocks_generated'], 1)
        
        # Check generated block
        block = BlockSchedule.objects.first()
        self.assertIsNotNone(block)
        # Verify coordination
        self.assertTrue(block.is_coordinated)
        self.assertIn('TMS', block.participating_departments)
        self.assertIn('TDMS', block.participating_departments)
        self.assertGreater(block.estimated_downtime_saved_minutes, 0)

    def test_emergency_defect_dynamic_replanning(self):
        """Verify emergency defect receives immediate override schedule"""
        today = timezone.now().date()
        emg = MaintenanceDemand.objects.create(
            demand_id='TEST-EMG-01',
            source_system='TMS',
            corridor=self.corridor,
            track_line='DN',
            km_start=90.0,
            km_end=90.2,
            activity_name='Rail Fracture',
            defect_description='Broken rail web',
            criticality='EMERGENCY',
            duration_hours=2.0,
            due_date=today,
            speed_restriction_imposed=True,
            speed_restriction_kmh=15
        )
        emg_block = replan_emergency_defect(emg)
        self.assertIsNotNone(emg_block)
        self.assertEqual(emg_block.status, 'APPROVED_BY_COA')
        self.assertIn('EMERGENCY', emg_block.ai_optimization_notes)

    def test_all_page_views_return_200(self):
        """Verify all 6 pages render without template or database errors"""
        pages = [
            'dashboard',
            'data_hub',
            'optimizer_studio',
            'master_schedule',
            'department_portal',
            'analytics',
        ]
        for p in pages:
            url = reverse(p)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Page {p} returned status {response.status_code}")

    def test_ajax_co_location_scanner(self):
        """Verify live AI pre-check returns nearby co-located candidates"""
        url = reverse('api_check_co_location')
        response = self.client.get(url, {
            'corridor_id': self.corridor.id,
            'km_start': '124.0',
            'km_end': '128.0',
            'dept': 'SMMS'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('candidates', data)
        self.assertGreaterEqual(len(data['candidates']), 1)

    def test_login_page_renders(self):
        """Verify login and signup pages render cleanly"""
        resp_login = self.client.get(reverse('login'))
        resp_signup = self.client.get(reverse('signup'))
        self.assertEqual(resp_login.status_code, 200)
        self.assertEqual(resp_signup.status_code, 200)

    def test_signup_creates_user_and_profile(self):
        """Verify new user registration creates User & UserProfile in integrated database"""
        from django.contrib.auth.models import User
        from core_rail.models import UserProfile

        signup_data = {
            'first_name': 'Suresh',
            'last_name': 'Kumar',
            'username': 'suresh_tms',
            'email': 'suresh@railnet.gov.in',
            'department': 'TMS',
            'designation': 'Assistant Divisional Engineer (ADEN)',
            'employee_id': 'IR-2026-7788',
            'password': 'password123',
            'password_confirm': 'password123',
            'division_id': self.division.id
        }
        response = self.client.post(reverse('signup'), signup_data)
        self.assertEqual(response.status_code, 302)  # Redirects to dashboard upon login

        user = User.objects.filter(username='suresh_tms').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, 'Suresh')
        self.assertEqual(user.profile.department, 'TMS')
        self.assertEqual(user.profile.employee_id, 'IR-2026-7788')

    def test_login_and_logout_flow(self):
        """Verify authentication against Django integrated DB and subsequent logout"""
        from django.contrib.auth.models import User
        user = User.objects.create_user('test_officer', 'officer@railnet.gov.in', 'securepass123')
        
        # Test valid login
        response = self.client.post(reverse('login'), {'username': 'test_officer', 'password': 'securepass123'})
        self.assertEqual(response.status_code, 302)

        # Test logout
        response_logout = self.client.get(reverse('logout'))
        self.assertEqual(response_logout.status_code, 302)


