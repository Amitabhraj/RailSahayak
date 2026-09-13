from django.contrib import admin
from .models import Zone, Division, Corridor, Station, TrainSchedule, GoodsForecast, UserProfile

admin.site.register(Zone)
admin.site.register(Division)
admin.site.register(Corridor)
admin.site.register(Station)
admin.site.register(TrainSchedule)
admin.site.register(GoodsForecast)
admin.site.register(UserProfile)
