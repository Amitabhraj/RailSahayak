from core_rail.models import Zone

def zone_context(request):
    """
    Context processor to provide active railway zones data across all templates.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    
    zone_ids = request.session.get('selected_zone_ids', [])
    all_zones = Zone.objects.all()
    total_zones = all_zones.count()
    active_zones = Zone.objects.filter(id__in=zone_ids)
    
    if total_zones > 0 and len(active_zones) == total_zones:
        label = f"All Zones ({total_zones})"
    elif len(active_zones) == 1:
        label = f"{active_zones[0].code} Zone"
    elif len(active_zones) > 1:
        label = ", ".join([z.code for z in active_zones])
    else:
        label = "No Zone Selected"
        
    return {
        'active_zones': active_zones,
        'active_zones_label': label,
        'active_zone_ids': zone_ids,
        'all_zones_list': all_zones,
    }

