from django.db import models

class Zone(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Division(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='divisions')
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} ({self.zone.code})"

class Corridor(models.Model):
    LINE_CHOICES = [
        ('SINGLE', 'Single Line'),
        ('DOUBLE', 'Double Line (UP/DN)'),
        ('TRIPLE', '3rd Line Added'),
        ('QUAD', 'Quadruple (4 Lines)'),
    ]

    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='corridors')
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    start_station = models.CharField(max_length=100)
    end_station = models.CharField(max_length=100)
    start_km = models.FloatField(default=0.0)
    end_km = models.FloatField(default=100.0)
    line_type = models.CharField(max_length=15, choices=LINE_CHOICES, default='DOUBLE')
    is_electrified = models.BooleanField(default=True)
    max_permissible_speed = models.IntegerField(default=130, help_text="km/h")
    gmt = models.FloatField(default=35.0, help_text="Gross Million Tonnes per Annum")
    daily_trains = models.IntegerField(default=120, help_text="Average daily trains (COA)")
    corridor_window_start = models.TimeField(default='01:00:00', help_text="Typical COA low-traffic slot start")
    corridor_window_end = models.TimeField(default='04:30:00', help_text="Typical COA low-traffic slot end")

    def __str__(self):
        return f"{self.code}: {self.name} (km {self.start_km:.1f} - {self.end_km:.1f})"

    @property
    def length_km(self):
        return max(0.0, self.end_km - self.start_km)

class Station(models.Model):
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE, related_name='stations')
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    km_post = models.FloatField()
    has_loop_lines = models.BooleanField(default=True)
    loop_line_count = models.IntegerField(default=2)

    class Meta:
        ordering = ['km_post']

    def __str__(self):
        return f"{self.code} ({self.name}) @ km {self.km_post}"

class TrainSchedule(models.Model):
    TRAIN_TYPES = [
        ('VANDE_BHARAT', 'Vande Bharat / Premium SF'),
        ('RAJDHANI', 'Rajdhani / Tejas Express'),
        ('SHATABDI', 'Shatabdi Express'),
        ('MAIL_EXPRESS', 'Superfast / Mail Express'),
        ('PASSENGER', 'Passenger / MEMU Local'),
        ('GOODS_SCHEDULED', 'Scheduled Freight Corridor'),
    ]

    DIRECTION_CHOICES = [
        ('UP', 'UP Line (Towards HQ/Delhi)'),
        ('DN', 'DOWN Line'),
        ('BOTH', 'Bidirectional'),
    ]

    PRIORITY_LEVELS = [
        (1, 'Priority 1 - Zero Detention (Rajdhani/Vande Bharat)'),
        (2, 'Priority 2 - Superfast Express'),
        (3, 'Priority 3 - Mail / Regular Express'),
        (4, 'Priority 4 - Suburban / Passenger'),
        (5, 'Priority 5 - Goods / Freight Traffic'),
    ]

    train_number = models.CharField(max_length=15)
    train_name = models.CharField(max_length=120)
    train_type = models.CharField(max_length=20, choices=TRAIN_TYPES, default='MAIL_EXPRESS')
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE, related_name='train_schedules')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='UP')
    entry_time = models.TimeField(help_text="Time entering corridor section")
    exit_time = models.TimeField(help_text="Time clearing corridor section")
    priority = models.IntegerField(choices=PRIORITY_LEVELS, default=3)
    days_of_run = models.CharField(max_length=50, default='Daily')

    class Meta:
        ordering = ['entry_time']

    def __str__(self):
        return f"{self.train_number} - {self.train_name} ({self.get_train_type_display()})"

class GoodsForecast(models.Model):
    COMMODITY_CHOICES = [
        ('COAL', 'Coal / Thermal Power Rake'),
        ('CONTAINER', 'Container / CONCOR Fast Freight'),
        ('PETROLEUM', 'POL Tankers'),
        ('CEMENT', 'Cement / Clinker'),
        ('FOODGRAIN', 'Foodgrains / FCI Rake'),
        ('FERTILIZER', 'Fertilizers'),
        ('EMPTY_RAKE', 'Empty Wagon Repositioning'),
    ]

    rake_id = models.CharField(max_length=30, unique=True)
    commodity = models.CharField(max_length=20, choices=COMMODITY_CHOICES, default='COAL')
    corridor = models.ForeignKey(Corridor, on_delete=models.CASCADE, related_name='goods_forecasts')
    direction = models.CharField(max_length=10, choices=[('UP', 'UP Line'), ('DN', 'DOWN Line')], default='UP')
    forecast_date = models.DateField()
    target_window_start = models.TimeField()
    target_window_end = models.TimeField()
    can_be_regulated = models.BooleanField(default=True, help_text="Can wait in loop siding during block")
    tonnage = models.IntegerField(default=3500, help_text="Trailing load in Metric Tonnes")

    def __str__(self):
        return f"{self.rake_id} ({self.get_commodity_display()} - {self.tonnage}T)"


from django.contrib.auth.models import User

class UserProfile(models.Model):
    DEPARTMENT_CHOICES = [
        ('TMS', 'Engineering (Track / P-Way)'),
        ('SMMS', 'Signalling & Telecom (S&T)'),
        ('TDMS', 'Electrical / TRD (Traction OHE)'),
        ('COA', 'Control Office / Operating (COA)'),
        ('ADMIN', 'Chief Controller / Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES, default='TMS')
    designation = models.CharField(max_length=100, default='Senior Section Engineer')
    employee_id = models.CharField(max_length=30, blank=True, null=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_department_display()})"

