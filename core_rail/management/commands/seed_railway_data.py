import datetime
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from django.contrib.auth.models import User
from core_rail.models import Zone, Division, Corridor, Station, TrainSchedule, GoodsForecast, UserProfile
from maintenance.models import MachineAsset, MaintenanceDemand
from scheduler.models import CorridorBlockWindow, BlockSchedule, OptimizationRun, ConflictAlert
from scheduler.optimizer import optimize_block_schedule, calculate_criticality_score


class Command(BaseCommand):
    help = 'Seeds realistic Indian Railways data for Rail-Sync AI (Corridors, COA Timetables, TMS/SMMS/TDMS demands, and Auth Users)'

    def handle(self, *args, **options):
        self.stdout.write("Initializing Rail-Sync AI Database with realistic railway operational data...")

        # 1. Clear existing data safely
        BlockSchedule.objects.all().delete()
        OptimizationRun.objects.all().delete()
        ConflictAlert.objects.all().delete()
        MaintenanceDemand.objects.all().delete()
        MachineAsset.objects.all().delete()
        GoodsForecast.objects.all().delete()
        TrainSchedule.objects.all().delete()
        Station.objects.all().delete()
        Corridor.objects.all().delete()
        Division.objects.all().delete()
        Zone.objects.all().delete()

        # 2. Zones & Divisions
        ncr = Zone.objects.create(code='NCR', name='North Central Railway')
        nr = Zone.objects.create(code='NR', name='Northern Railway')
        wr = Zone.objects.create(code='WR', name='Western Railway')

        pryj_div = Division.objects.create(zone=ncr, code='PRYJ', name='Prayagraj Division')
        dli_div = Division.objects.create(zone=nr, code='DLI', name='Delhi Division')
        bct_div = Division.objects.create(zone=wr, code='BCT', name='Mumbai Central Division')

        # 2b. Demo User Accounts (Connected with Django Auth DB)
        # 1) Chief Controller (Admin)
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser('admin', 'chief.controller@railnet.gov.in', 'admin123')
            admin_user.first_name = 'Chief'
            admin_user.last_name = 'Controller'
            admin_user.save()
            UserProfile.objects.create(
                user=admin_user,
                department='COA',
                designation='Chief Controller (Operating & COA)',
                employee_id='IR-HQ-001',
                division=pryj_div
            )

        # 2) Civil Engineering (TMS)
        if not User.objects.filter(username='tms_engineer').exists():
            tms_user = User.objects.create_user('tms_engineer', 'vikram.mehta@railnet.gov.in', 'rail123')
            tms_user.first_name = 'Vikram'
            tms_user.last_name = 'Mehta'
            tms_user.save()
            UserProfile.objects.create(
                user=tms_user,
                department='TMS',
                designation='Senior Section Engineer (P-Way / Track)',
                employee_id='IR-ENG-8821',
                division=pryj_div
            )

        # 3) Signal & Telecom (SMMS)
        if not User.objects.filter(username='smms_engineer').exists():
            smms_user = User.objects.create_user('smms_engineer', 'ananya.iyer@railnet.gov.in', 'rail123')
            smms_user.first_name = 'Ananya'
            smms_user.last_name = 'Iyer'
            smms_user.save()
            UserProfile.objects.create(
                user=smms_user,
                department='SMMS',
                designation='Divisional Signal & Telecom Engineer (DSTE)',
                employee_id='IR-SNT-4032',
                division=pryj_div
            )

        # 4) Traction Distribution (TDMS)
        if not User.objects.filter(username='tdms_engineer').exists():
            tdms_user = User.objects.create_user('tdms_engineer', 'rajesh.verma@railnet.gov.in', 'rail123')
            tdms_user.first_name = 'Rajesh'
            tdms_user.last_name = 'Verma'
            tdms_user.save()
            UserProfile.objects.create(
                user=tdms_user,
                department='TDMS',
                designation='Sr. Divisional Electrical Engineer (Sr. DEE/TRD)',
                employee_id='IR-TRD-1194',
                division=pryj_div
            )
        self.stdout.write("Created demo users for TMS, SMMS, TDMS, and COA Chief Controller.")

        # 3. Corridors
        corridor1 = Corridor.objects.create(
            division=pryj_div,
            code='GZB-CNB',
            name='Ghaziabad - Kanpur Grand Chord',
            start_station='Ghaziabad (GZB)',
            end_station='Kanpur Central (CNB)',
            start_km=20.0,
            end_km=435.0,
            line_type='DOUBLE',
            is_electrified=True,
            max_permissible_speed=130,
            gmt=48.5,
            daily_trains=142,
            corridor_window_start=datetime.time(1, 0),
            corridor_window_end=datetime.time(4, 30)
        )

        corridor2 = Corridor.objects.create(
            division=pryj_div,
            code='CNB-DDU',
            name='Kanpur - Prayagraj - Pt. Deen Dayal Upadhyaya Trunk',
            start_station='Kanpur Central (CNB)',
            end_station='Pt. DD Upadhyaya Jn (DDU)',
            start_km=435.0,
            end_km=780.0,
            line_type='TRIPLE',
            is_electrified=True,
            max_permissible_speed=130,
            gmt=56.2,
            daily_trains=165,
            corridor_window_start=datetime.time(1, 15),
            corridor_window_end=datetime.time(4, 45)
        )

        corridor3 = Corridor.objects.create(
            division=dli_div,
            code='NDLS-AGC',
            name='New Delhi - Mathura - Agra Cantt Semi-High Speed',
            start_station='New Delhi (NDLS)',
            end_station='Agra Cantt (AGC)',
            start_km=0.0,
            end_km=195.0,
            line_type='DOUBLE',
            is_electrified=True,
            max_permissible_speed=160,
            gmt=42.0,
            daily_trains=130,
            corridor_window_start=datetime.time(0, 45),
            corridor_window_end=datetime.time(4, 15)
        )

        # 4. Stations
        stations_c1 = [
            ('GZB', 'Ghaziabad Jn', 20.0, 6),
            ('ALJN', 'Aligarh Jn', 126.0, 5),
            ('TDL', 'Tundla Jn', 205.0, 7),
            ('ETW', 'Etawah Jn', 297.0, 4),
            ('CNB', 'Kanpur Central', 435.0, 10),
        ]
        for code, name, km, loops in stations_c1:
            Station.objects.create(corridor=corridor1, code=code, name=name, km_post=km, loop_line_count=loops)

        stations_c3 = [
            ('NDLS', 'New Delhi', 0.0, 12),
            ('PWL', 'Palwal', 60.5, 4),
            ('MTJ', 'Mathura Jn', 140.0, 8),
            ('AGC', 'Agra Cantt', 195.0, 6),
        ]
        for code, name, km, loops in stations_c3:
            Station.objects.create(corridor=corridor3, code=code, name=name, km_post=km, loop_line_count=loops)

        # 5. Track Machines & TRD Assets
        csm = MachineAsset.objects.create(
            machine_id='CSM-952',
            machine_name='Plasser Continuous Action Tamper 09-32 CSM',
            machine_type='CSM',
            department='TMS',
            base_depot='Tundla Machine Siding',
            is_available=True
        )
        bcm = MachineAsset.objects.create(
            machine_id='BCM-412',
            machine_name='Ballast Cleaning Machine RM-80 BCM',
            machine_type='BCM',
            department='TMS',
            base_depot='Aligarh P-Way Depot',
            is_available=True
        )
        unimat = MachineAsset.objects.create(
            machine_id='UNIMAT-08',
            machine_name='Points & Crossing Tamper Unimat 4S',
            machine_type='UNIMAT',
            department='TMS',
            base_depot='Kanpur Central Depot',
            is_available=True
        )
        tw = MachineAsset.objects.create(
            machine_id='TW-8W-104',
            machine_name='8-Wheeler TRD Tower Wagon Self-Propelled',
            machine_type='TOWER_WAGON',
            department='TDMS',
            base_depot='Aligarh TRD Depot',
            is_available=True
        )

        # 6. COA Timetable (Train Schedules)
        trains = [
            ('22436', 'Vande Bharat Express (NDLS-BSB)', 'VANDE_BHARAT', corridor1, 'DN', datetime.time(6, 0), datetime.time(10, 0), 1),
            ('22435', 'Vande Bharat Express (BSB-NDLS)', 'VANDE_BHARAT', corridor1, 'UP', datetime.time(19, 0), datetime.time(23, 0), 1),
            ('12302', 'Howrah Rajdhani Express', 'RAJDHANI', corridor1, 'DN', datetime.time(17, 30), datetime.time(21, 30), 1),
            ('12301', 'Howrah - NDLS Rajdhani', 'RAJDHANI', corridor1, 'UP', datetime.time(5, 30), datetime.time(9, 30), 1),
            ('12004', 'Lucknow Swarna Shatabdi', 'SHATABDI', corridor1, 'DN', datetime.time(6, 45), datetime.time(11, 0), 2),
            ('12418', 'Prayagraj Express', 'MAIL_EXPRESS', corridor1, 'UP', datetime.time(4, 0), datetime.time(7, 30), 2),
            ('12582', 'Banaras Superfast', 'MAIL_EXPRESS', corridor1, 'DN', datetime.time(23, 15), datetime.time(3, 45), 3),
            ('64101', 'Ghaziabad - Aligarh MEMU', 'PASSENGER', corridor1, 'DN', datetime.time(12, 10), datetime.time(14, 40), 4),
            ('12050', 'Gatimaan Express (NZM-VGLB)', 'VANDE_BHARAT', corridor3, 'DN', datetime.time(8, 10), datetime.time(9, 50), 1),
            ('12952', 'Mumbai Rajdhani Express', 'RAJDHANI', corridor3, 'UP', datetime.time(6, 15), datetime.time(8, 30), 1),
        ]
        for t_no, t_name, t_type, corr, dirn, ent, ext, prio in trains:
            TrainSchedule.objects.create(
                train_number=t_no,
                train_name=t_name,
                train_type=t_type,
                corridor=corr,
                direction=dirn,
                entry_time=ent,
                exit_time=ext,
                priority=prio,
                days_of_run='Daily'
            )

        # 7. COA Goods Forecasts
        today = timezone.now().date()
        goods = [
            ('BOXN-COAL-7812', 'COAL', corridor1, 'DN', today, datetime.time(2, 0), datetime.time(5, 0), True, 3800),
            ('BTPN-POL-3490', 'PETROLEUM', corridor1, 'UP', today, datetime.time(1, 30), datetime.time(4, 0), True, 2900),
            ('CONCOR-FAST-1109', 'CONTAINER', corridor1, 'DN', today + timedelta(days=1), datetime.time(12, 0), datetime.time(15, 0), False, 3200),
            ('BCN-FOOD-9021', 'FOODGRAIN', corridor3, 'UP', today, datetime.time(2, 15), datetime.time(4, 45), True, 3100),
        ]
        for r_id, comm, corr, dirn, fdate, wstart, wend, can_reg, ton in goods:
            GoodsForecast.objects.create(
                rake_id=r_id,
                commodity=comm,
                corridor=corr,
                direction=dirn,
                forecast_date=fdate,
                target_window_start=wstart,
                target_window_end=wend,
                can_be_regulated=can_reg,
                tonnage=ton
            )

        # 8. Maintenance Demands from TMS, SMMS, and TDMS
        # IMPORTANT: We purposefully set co-located locations (e.g. km 124-128 near Aligarh, and km 203-207 near Tundla)
        # to trigger the AI Shadow Block bundling across Engineering, Signal, and Electrical!
        demands_data = [
            # Location Group 1: Aligarh Section (km 124.0 - 128.0) - Co-location opportunity!
            {
                'demand_id': 'TMS-2026-081',
                'source_system': 'TMS',
                'corridor': corridor1,
                'track_line': 'UP',
                'km_start': 124.5,
                'km_end': 127.8,
                'activity_name': 'Deep Screening by BCM Machine & Ballast Regulation',
                'activity_code': 'TMS_BCM_SCRN',
                'defect_description': 'Excessive caked ballast and mud pumping causing poor track ride quality. Deep screening urgently due.',
                'criticality': 'URGENT_I',
                'duration_hours': 3.5,
                'requires_power_block': True,
                'requires_traffic_block': True,
                'speed_restriction_imposed': True,
                'speed_restriction_kmh': 45,
                'due_date': today - timedelta(days=6),
                'overdue_days': 6,
                'assigned_machine': bcm,
                'manpower_required': 24,
            },
            {
                'demand_id': 'TDMS-2026-104',
                'source_system': 'TDMS',
                'corridor': corridor1,
                'track_line': 'UP',
                'km_start': 125.0,
                'km_end': 127.5,
                'activity_name': 'OHE Contact Wire Renewal & Cantilever Overhaul',
                'activity_code': 'TDMS_OHE_RNWL',
                'defect_description': 'Contact wire diameter worn down to 9.2mm (condemning limit 8.5mm). Overhaul of dropper wires and cantilevers required.',
                'criticality': 'URGENT_I',
                'duration_hours': 3.0,
                'requires_power_block': True,
                'requires_traffic_block': False,
                'speed_restriction_imposed': False,
                'due_date': today - timedelta(days=4),
                'overdue_days': 4,
                'assigned_machine': tw,
                'manpower_required': 12,
            },
            {
                'demand_id': 'SMMS-2026-052',
                'source_system': 'SMMS',
                'corridor': corridor1,
                'track_line': 'UP',
                'km_start': 126.0,
                'km_end': 126.3,
                'activity_name': 'Track Circuit Impedance Bond & Axle Counter Head Replacement',
                'activity_code': 'SMMS_TC_BOND',
                'defect_description': 'Low insulation resistance in track circuit bond wire. Intermittent track drop reported during heavy dew.',
                'criticality': 'NORMAL_II',
                'duration_hours': 2.0,
                'requires_power_block': False,
                'requires_traffic_block': True,
                'speed_restriction_imposed': False,
                'due_date': today - timedelta(days=2),
                'overdue_days': 2,
                'manpower_required': 6,
            },

            # Location Group 2: Tundla Junction Section (km 204.0 - 207.0) - Turnout Co-location!
            {
                'demand_id': 'TMS-2026-094',
                'source_system': 'TMS',
                'corridor': corridor1,
                'track_line': 'DN',
                'km_start': 204.2,
                'km_end': 206.0,
                'activity_name': 'Turnout Point 204 Tamping & CMS Crossing Renewal',
                'activity_code': 'TMS_TURNOUT_TAMP',
                'defect_description': 'Gauge face wear on CMS crossing exceeding permissible 8mm. Turnout geometry packing overdue.',
                'criticality': 'URGENT_I',
                'duration_hours': 3.0,
                'requires_power_block': False,
                'requires_traffic_block': True,
                'speed_restriction_imposed': True,
                'speed_restriction_kmh': 30,
                'due_date': today - timedelta(days=9),
                'overdue_days': 9,
                'assigned_machine': unimat,
                'manpower_required': 18,
            },
            {
                'demand_id': 'SMMS-2026-061',
                'source_system': 'SMMS',
                'corridor': corridor1,
                'track_line': 'DN',
                'km_start': 204.8,
                'km_end': 205.2,
                'activity_name': 'Point Machine Overhaul & Friction Clutch Testing (Pt 204)',
                'activity_code': 'SMMS_PT_OVERHAUL',
                'defect_description': 'Quarterly POH of Electric Point Machine Siemens 143mm stroke. Throw rod alignment testing.',
                'criticality': 'NORMAL_II',
                'duration_hours': 2.5,
                'requires_power_block': False,
                'requires_traffic_block': True,
                'speed_restriction_imposed': False,
                'due_date': today,
                'overdue_days': 0,
                'manpower_required': 8,
            },
            {
                'demand_id': 'TDMS-2026-118',
                'source_system': 'TDMS',
                'corridor': corridor1,
                'track_line': 'DN',
                'km_start': 204.5,
                'km_end': 206.5,
                'activity_name': 'Insulator High-Pressure Hot-Line Jet Washing & Isolator Maintenance',
                'activity_code': 'TDMS_INSUL_WASH',
                'defect_description': 'Heavy pollution and coal dust deposition on 25kV OHE pin & bracket insulators near Tundla yard.',
                'criticality': 'ROUTINE_III',
                'duration_hours': 2.0,
                'requires_power_block': True,
                'requires_traffic_block': False,
                'speed_restriction_imposed': False,
                'due_date': today + timedelta(days=5),
                'overdue_days': 0,
                'assigned_machine': tw,
                'manpower_required': 10,
            },

            # Emergency Defect on Corridor 3 (Semi-high speed route)
            {
                'demand_id': 'TMS-2026-003',
                'source_system': 'TMS',
                'corridor': corridor3,
                'track_line': 'UP',
                'km_start': 84.1,
                'km_end': 84.3,
                'activity_name': 'Emergency Rail Fracture Rectification & Weld Renewal',
                'activity_code': 'TMS_RAIL_FRACT',
                'defect_description': 'Transverse fatigue crack detected by USFD testing on 60kg 90UTS rail. Critical risk of complete fracture under 160 km/h traffic.',
                'criticality': 'EMERGENCY',
                'duration_hours': 2.0,
                'requires_power_block': False,
                'requires_traffic_block': True,
                'speed_restriction_imposed': True,
                'speed_restriction_kmh': 20,
                'due_date': today,
                'overdue_days': 1,
                'manpower_required': 14,
            },

            # Standalone Routine Demand on Corridor 2
            {
                'demand_id': 'TMS-2026-112',
                'source_system': 'TMS',
                'corridor': corridor2,
                'track_line': 'DN',
                'km_start': 510.0,
                'km_end': 518.0,
                'activity_name': 'Plain Track Continuous Tamping by CSM Machine',
                'activity_code': 'TMS_PLAIN_TAMP',
                'defect_description': 'Cyclic track tamping for maintaining track quality index (TQI) below 36 on high GMT freight trunk.',
                'criticality': 'NORMAL_II',
                'duration_hours': 3.5,
                'requires_power_block': False,
                'requires_traffic_block': True,
                'speed_restriction_imposed': False,
                'due_date': today + timedelta(days=2),
                'overdue_days': 0,
                'assigned_machine': csm,
                'manpower_required': 16,
            },
            {
                'demand_id': 'TDMS-2026-129',
                'source_system': 'TDMS',
                'corridor': corridor2,
                'track_line': 'DN',
                'km_start': 512.0,
                'km_end': 516.0,
                'activity_name': 'OHE Neutral Section Assembly POH & PTFE Rod Replacement',
                'activity_code': 'TDMS_NEUTRAL_SEC',
                'defect_description': 'Overhaul of short neutral section assembly to ensure continuous power delivery to electric locomotives.',
                'criticality': 'NORMAL_II',
                'duration_hours': 3.0,
                'requires_power_block': True,
                'requires_traffic_block': False,
                'speed_restriction_imposed': False,
                'due_date': today + timedelta(days=3),
                'overdue_days': 0,
                'assigned_machine': tw,
                'manpower_required': 10,
            },
            {
                'demand_id': 'SMMS-2026-077',
                'source_system': 'SMMS',
                'corridor': corridor2,
                'track_line': 'DN',
                'km_start': 514.2,
                'km_end': 514.8,
                'activity_name': 'Electronic Interlocking (EI) Diagnostic & Standby CPU Switchover Test',
                'activity_code': 'SMMS_EI_DIAG',
                'defect_description': 'Routine preventive health check of Kyosan Electronic Interlocking hardware and vital relay room inspection.',
                'criticality': 'ROUTINE_III',
                'duration_hours': 2.0,
                'requires_power_block': False,
                'requires_traffic_block': False,
                'speed_restriction_imposed': False,
                'due_date': today + timedelta(days=7),
                'overdue_days': 0,
                'manpower_required': 4,
            },
        ]

        for item in demands_data:
            assigned_m = item.pop('assigned_machine', None)
            d = MaintenanceDemand.objects.create(assigned_machine=assigned_m, **item)
            calculate_criticality_score(d)
            d.save()

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(demands_data)} demands across TMS, SMMS, and TDMS."))

        # 9. Trigger Initial AI Optimization Run
        self.stdout.write("Running initial AI Multi-Department Optimization Engine...")
        result = optimize_block_schedule(horizon='WEEKLY', strategy='MULTI_OBJECTIVE_BALANCED')
        self.stdout.write(self.style.SUCCESS(f"Optimization completed: {result['blocks_generated']} blocks generated, "
                                             f"{result['coordinated_blocks']} multi-department shadow blocks bundled, "
                                             f"Synergy: {result['synergy_rate']}%, "
                                             f"Downtime Saved: {result['total_downtime_saved_hours']} hrs."))
