from django.contrib import admin
from .models import CorridorBlockWindow, BlockSchedule, OptimizationRun, ConflictAlert

admin.site.register(CorridorBlockWindow)
admin.site.register(BlockSchedule)
admin.site.register(OptimizationRun)
admin.site.register(ConflictAlert)
