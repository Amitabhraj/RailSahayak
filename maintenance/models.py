from django.db import models
from core_rail.models import Corridor

class MachineAsset(models.Model):
    MACHINE_TYPES = [
        ('CSM', 'Continuous Action Tamper (CSM)'),
        ('DUOMAT', 'Plain Track Tamper (Duomat)'),
        ('BCM', 'Ballast Cleaning Machine (BCM)'),
        ('UNIMAT', 'Point & Crossing Tamper (Unimat)'),
        ('RGM', 'Rail Grinding Machine (RGM)'),
        ('TOWER_WAGON', '8-Wheeler TRD Tower Wagon (OHE)'),
        ('WIRING_TRAIN', 'OHE Wiring Special Train'),
    ]

    DEPARTMENT_CHOICES = [
        ('TMS', 'Engineering (Track)'),
        ('TDMS', 'Electrical (TRD / OHE)'),
        ('SMMS', 'S&T (Signal & Telecom)'),
    ]

    machine_id = models.CharField(max_length=30, unique=True)
    machine_name = models.CharField(max_length=100)
    machine_type = models.CharField(max_length=20, choices=MACHINE_TYPES)
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES)
    base_depot = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)
    maintenance_due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.machine_id} - {self.get_machine_type_display()} ({self.base_depot})"

class MaintenanceDemand(models.Model):
    SYSTEM_CHOICES = [
        ('TMS', 'TMS (Track Management System - Engineering)'),
        ('SMMS', 'SMMS (Signal Maintenance & Management - S&T)'),
        ('TDMS', 'TDMS (Traction Distribution - Electrical/TRD)'),
    ]

    CRITICALITY_LEVELS = [
        ('EMERGENCY', 'Category 1: Emergency Defect / Immediate Risk'),
        ('URGENT_I', 'Category 2: Urgent / Overdue / Safety Impact'),
        ('NORMAL_II', 'Category 3: Cyclic Maintenance Due'),
        ('ROUTINE_III', 'Category 4: Routine Preventive / Inspection'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending AI Scheduling'),
        ('AI_RECOMMENDED', 'AI Bundling Recommended'),
        ('SCHEDULED', 'Scheduled in Block Plan'),
        ('COMPLETED', 'Executed & Closed'),
        ('DEFERRED', 'Deferred to Next Horizon'),
    ]

    TRACK_LINE_CHOICES = [
        ('UP', 'UP Line'),
        ('DN', 'DOWN Line'),
        ('BOTH', 'Both Lines / Crossover'),
        ('YARD', 'Yard / Loop Lines'),
    ]

    demand_id = models.CharField(max_length=40, unique=True)
    source_system = models.CharField(max_length=10, choices=SYSTEM_CHOICES)
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE, related_name='maintenance_demands')
    track_line = models.CharField(max_length=10, choices=TRACK_LINE_CHOICES, default='UP')
    km_start = models.FloatField()
    km_end = models.FloatField()
    activity_name = models.CharField(max_length=150)
    activity_code = models.CharField(max_length=50, blank=True)
    defect_description = models.TextField()
    criticality = models.CharField(max_length=20, choices=CRITICALITY_LEVELS, default='NORMAL_II')
    duration_hours = models.FloatField(default=3.0, help_text="Required block duration in hours")
    
    # Block type dependencies
    requires_power_block = models.BooleanField(default=False, help_text="Needs OHE 25kV traction power shutdown")
    requires_traffic_block = models.BooleanField(default=True, help_text="Needs rail line closure")
    speed_restriction_imposed = models.BooleanField(default=False, help_text="Temporary Speed Restriction (TSR) already active")
    speed_restriction_kmh = models.IntegerField(null=True, blank=True, help_text="Current TSR limit, e.g. 30 km/h")
    
    # Planning fields
    due_date = models.DateField()
    overdue_days = models.IntegerField(default=0)
    assigned_machine = models.ForeignKey(MachineAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='demands')
    manpower_required = models.IntegerField(default=15, help_text="Number of staff / gang strength")
    
    # AI Engine Outputs
    ai_priority_score = models.FloatField(default=50.0, help_text="Score 0 - 100 calculated by AI")
    ai_urgency_notes = models.TextField(blank=True, help_text="Explanation of AI risk score")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ai_priority_score', '-criticality']

    def __str__(self):
        return f"[{self.source_system}] {self.demand_id} - {self.activity_name} (km {self.km_start:.1f}-{self.km_end:.1f})"

    @property
    def section_length_km(self):
        return round(abs(self.km_end - self.km_start), 2)

