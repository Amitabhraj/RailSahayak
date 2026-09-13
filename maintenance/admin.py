from django.contrib import admin
from .models import MachineAsset, MaintenanceDemand

admin.site.register(MachineAsset)
admin.site.register(MaintenanceDemand)
