from django.db import models
from core_rail.models import Corridor
from maintenance.models import MaintenanceDemand

class CorridorBlockWindow(models.Model):
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE, related_name='block_windows')
    window_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    track_line = models.CharField(max_length=10, choices=[('UP', 'UP Line'), ('DN', 'DOWN Line'), ('BOTH', 'Both Lines')], default='UP')
    available_duration_hours = models.FloatField(default=3.5)
    train_density_score = models.IntegerField(default=15, help_text="Estimated traffic passing (lower is better)")
    is_booked = models.BooleanField(default=False)

    class Meta:
        ordering = ['window_date', 'start_time']

    def __str__(self):
        return f"{self.corridor.code} [{self.track_line}] on {self.window_date} ({self.start_time} - {self.end_time})"

class BlockSchedule(models.Model):
    HORIZON_CHOICES = [
        ('WEEKLY', 'Weekly Operational Master Schedule'),
        ('MONTHLY', 'Monthly Strategic Maintenance Plan'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft Plan'),
        ('AI_OPTIMIZED', 'AI Optimized & Bundled'),
        ('APPROVED_BY_COA', 'Approved by Chief Controller (COA)'),
        ('IN_PROGRESS', 'Currently In Execution'),
        ('COMPLETED', 'Block Completed & Track Cleared'),
        ('CANCELLED', 'Cancelled / Rescheduled'),
    ]

    block_id = models.CharField(max_length=40, unique=True)
    horizon = models.CharField(max_length=15, choices=HORIZON_CHOICES, default='WEEKLY')
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE, related_name='scheduled_blocks')
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_hours = models.FloatField(default=3.0)
    track_line = models.CharField(max_length=10, choices=[('UP', 'UP Line'), ('DN', 'DOWN Line'), ('BOTH', 'Both Lines')], default='UP')
    km_start = models.FloatField()
    km_end = models.FloatField()
    
    # Department Coordination
    primary_department = models.CharField(max_length=10, choices=[('TMS', 'TMS (Track)'), ('TDMS', 'TDMS (OHE)'), ('SMMS', 'SMMS (S&T)')])
    primary_demand = models.ForeignKey(MaintenanceDemand, on_delete=models.SET_NULL, null=True, blank=True, related_name='as_primary_block')
    bundled_demands = models.ManyToManyField(MaintenanceDemand, blank=True, related_name='in_block_schedules')
    
    is_coordinated = models.BooleanField(default=False, help_text="Bundles 2+ departments simultaneously")
    participating_departments = models.CharField(max_length=50, default='TMS')
    
    # Operational Impact & Savings
    estimated_downtime_saved_minutes = models.IntegerField(default=0, help_text="Downtime eliminated by bundling co-located works")
    impacted_trains_count = models.IntegerField(default=0, help_text="Number of freight/passenger trains regulated in loops")
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='AI_OPTIMIZED')
    ai_optimization_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'start_time']

    def __str__(self):
        return f"{self.block_id} - {self.corridor.code} [{self.scheduled_date} {self.start_time}-{self.end_time}] ({self.participating_departments})"

    @property
    def total_activities_count(self):
        return 1 + self.bundled_demands.count() if self.primary_demand else self.bundled_demands.count()

class OptimizationRun(models.Model):
    run_id = models.CharField(max_length=50, unique=True)
    horizon = models.CharField(max_length=15, default='WEEKLY')
    strategy = models.CharField(max_length=50, default='MULTI_OBJECTIVE_BALANCED')
    total_demands_analyzed = models.IntegerField(default=0)
    blocks_generated = models.IntegerField(default=0)
    multi_dept_bundled_count = models.IntegerField(default=0)
    synergy_rate_percentage = models.FloatField(default=0.0)
    total_downtime_saved_hours = models.FloatField(default=0.0)
    asset_availability_score = models.FloatField(default=98.5)
    execution_time_ms = models.IntegerField(default=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.run_id} ({self.horizon} - {self.synergy_rate_percentage:.1f}% Synergy)"

class ConflictAlert(models.Model):
    SEVERITY_LEVELS = [
        ('CRITICAL', 'Critical - Track Safety / Collision with Timetable'),
        ('WARNING', 'Warning - High Traffic Density Slot'),
        ('INFO', 'Information - Shadow Block Opportunity Available'),
    ]

    severity = models.CharField(max_length=15, choices=SEVERITY_LEVELS, default='WARNING')
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    details = models.TextField()
    suggested_action = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_resolved', '-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.title}"

