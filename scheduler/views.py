import json
import datetime
from datetime import timedelta
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

from core_rail.models import Zone, Division, Corridor, Station, TrainSchedule, GoodsForecast, UserProfile
from maintenance.models import MachineAsset, MaintenanceDemand
from scheduler.models import CorridorBlockWindow, BlockSchedule, OptimizationRun, ConflictAlert
from scheduler.optimizer import optimize_block_schedule, replan_emergency_defect, calculate_criticality_score


def custom_404_view(request, exception=None):
    """
    Renders the responsive & attractive 404 error page.
    """
    return render(request, '404.html', status=404)


def login_required_404(view_func):
    """
    Backend Security: Whenever user is not logged in, return 404 Error.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'status': 'error',
                    'message': '404 Not Found'
                }, status=404)
            return render(request, '404.html', status=404)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@login_required_404
def dashboard_view(request):
    """
    Executive Operations Center Dashboard:
    Summarizes high-level KPIs, corridor statuses, pending vs scheduled demands,
    synergy rate, total downtime saved, and active conflict alerts.
    """
    corridors = Corridor.objects.all().prefetch_related('scheduled_blocks', 'maintenance_demands')
    total_demands = MaintenanceDemand.objects.count()
    pending_demands = MaintenanceDemand.objects.filter(status__in=['PENDING', 'AI_RECOMMENDED', 'DEFERRED']).count()
    scheduled_demands = MaintenanceDemand.objects.filter(status__in=['SCHEDULED', 'BUNDLED']).count()
    
    # Calculate savings and coordination statistics
    latest_run = OptimizationRun.objects.first()
    blocks = BlockSchedule.objects.all()
    total_blocks_count = blocks.count()
    coordinated_blocks_count = blocks.filter(is_coordinated=True).count()
    
    total_saved_minutes = blocks.aggregate(s=Sum('estimated_downtime_saved_minutes'))['s'] or 0
    total_saved_hours = round(total_saved_minutes / 60.0, 1)

    synergy_rate = round((coordinated_blocks_count / total_blocks_count * 100), 1) if total_blocks_count > 0 else 0.0
    asset_availability = latest_run.asset_availability_score if latest_run else 98.4

    # Alerts & active speed restrictions
    alerts = ConflictAlert.objects.filter(is_resolved=False)[:5]
    active_tsrs = MaintenanceDemand.objects.filter(speed_restriction_imposed=True).count()
    critical_overdue = MaintenanceDemand.objects.filter(Q(criticality='EMERGENCY') | Q(overdue_days__gt=5)).count()

    # Upcoming blocks for next 3 days
    today = timezone.now().date()
    upcoming_blocks = BlockSchedule.objects.filter(scheduled_date__gte=today).order_by('scheduled_date', 'start_time')[:6]

    # Department demand counts
    tms_count = MaintenanceDemand.objects.filter(source_system='TMS').count()
    smms_count = MaintenanceDemand.objects.filter(source_system='SMMS').count()
    tdms_count = MaintenanceDemand.objects.filter(source_system='TDMS').count()

    context = {
        'corridors': corridors,
        'total_demands': total_demands,
        'pending_demands': pending_demands,
        'scheduled_demands': scheduled_demands,
        'total_blocks_count': total_blocks_count,
        'coordinated_blocks_count': coordinated_blocks_count,
        'total_saved_hours': total_saved_hours,
        'synergy_rate': synergy_rate,
        'asset_availability': asset_availability,
        'alerts': alerts,
        'active_tsrs': active_tsrs,
        'critical_overdue': critical_overdue,
        'upcoming_blocks': upcoming_blocks,
        'tms_count': tms_count,
        'smms_count': smms_count,
        'tdms_count': tdms_count,
        'latest_run': latest_run,
    }
    return render(request, 'dashboard.html', context)


@login_required_404
def data_hub_view(request):
    """
    Integrated Data Hub:
    Displays raw and prioritized data feeds from TMS (Track), SMMS (S&T), TDMS (OHE),
    plus COA Passenger Timetable & Goods Forecasts.
    """
    tab = request.GET.get('tab', 'demands')
    dept_filter = request.GET.get('dept', 'ALL')
    corridor_filter = request.GET.get('corridor', 'ALL')
    search_query = request.GET.get('q', '').strip()

    demands_qs = MaintenanceDemand.objects.all().select_related('corridor', 'assigned_machine')
    if dept_filter != 'ALL':
        demands_qs = demands_qs.filter(source_system=dept_filter)
    if corridor_filter != 'ALL':
        demands_qs = demands_qs.filter(corridor__code=corridor_filter)
    if search_query:
        demands_qs = demands_qs.filter(
            Q(demand_id__icontains=search_query) |
            Q(activity_name__icontains=search_query) |
            Q(defect_description__icontains=search_query)
        )

    # Corridors & machines
    corridors = Corridor.objects.all()
    machines = MachineAsset.objects.all()
    train_schedules = TrainSchedule.objects.all().select_related('corridor')
    goods_forecasts = GoodsForecast.objects.all().select_related('corridor')

    context = {
        'tab': tab,
        'dept_filter': dept_filter,
        'corridor_filter': corridor_filter,
        'search_query': search_query,
        'demands': demands_qs,
        'corridors': corridors,
        'machines': machines,
        'train_schedules': train_schedules,
        'goods_forecasts': goods_forecasts,
        'total_tms': MaintenanceDemand.objects.filter(source_system='TMS').count(),
        'total_smms': MaintenanceDemand.objects.filter(source_system='SMMS').count(),
        'total_tdms': MaintenanceDemand.objects.filter(source_system='TDMS').count(),
    }
    return render(request, 'data_hub.html', context)


@login_required_404
def optimizer_studio_view(request):
    """
    AI Optimization Studio & What-If Simulation:
    Allows running AI algorithms with custom parameters, inspecting Before-vs-After AI metrics,
    and simulating emergency track defect injection.
    """
    latest_run = OptimizationRun.objects.first()
    runs_history = OptimizationRun.objects.all()[:8]
    corridors = Corridor.objects.all()
    
    # Calculate Before vs After AI comparison metrics
    blocks = BlockSchedule.objects.all()
    total_blocks = blocks.count()
    coordinated_blocks = blocks.filter(is_coordinated=True).count()
    
    # In manual decentralized planning, each task took a separate block:
    manual_blocks_count = MaintenanceDemand.objects.filter(status__in=['SCHEDULED', 'BUNDLED']).count()
    manual_total_hours = sum(d.duration_hours for d in MaintenanceDemand.objects.filter(status__in=['SCHEDULED', 'BUNDLED']))
    ai_total_hours = sum(b.duration_hours for b in blocks)
    downtime_saved_hours = max(0.0, round(manual_total_hours - ai_total_hours, 1))

    context = {
        'latest_run': latest_run,
        'runs_history': runs_history,
        'corridors': corridors,
        'total_blocks': total_blocks,
        'coordinated_blocks': coordinated_blocks,
        'manual_blocks_count': manual_blocks_count,
        'manual_total_hours': round(manual_total_hours, 1),
        'ai_total_hours': round(ai_total_hours, 1),
        'downtime_saved_hours': downtime_saved_hours,
    }
    return render(request, 'optimizer_studio.html', context)


@login_required_404
def master_schedule_view(request):
    """
    Master Schedule & Interactive Gantt Timeline:
    Displays scheduled blocks across Weekly and Monthly horizons, highlighting
    multi-department bundling synergies, train clashes, and time-slot spans.
    """
    horizon_filter = request.GET.get('horizon', 'WEEKLY')
    corridor_filter = request.GET.get('corridor', 'ALL')
    dept_filter = request.GET.get('dept', 'ALL')

    blocks_qs = BlockSchedule.objects.all().select_related('corridor', 'primary_demand').prefetch_related('bundled_demands')
    if horizon_filter != 'ALL':
        blocks_qs = blocks_qs.filter(horizon=horizon_filter)
    if corridor_filter != 'ALL':
        blocks_qs = blocks_qs.filter(corridor__code=corridor_filter)
    if dept_filter != 'ALL':
        blocks_qs = blocks_qs.filter(
            Q(primary_department=dept_filter) |
            Q(participating_departments__icontains=dept_filter)
        )

    corridors = Corridor.objects.all()
    
    # Group blocks by date for timeline/gantt display
    dates_grouped = {}
    for block in blocks_qs:
        d_str = block.scheduled_date.strftime('%Y-%m-%d')
        if d_str not in dates_grouped:
            dates_grouped[d_str] = []
        dates_grouped[d_str].append(block)

    context = {
        'blocks': blocks_qs,
        'dates_grouped': dates_grouped,
        'corridors': corridors,
        'horizon_filter': horizon_filter,
        'corridor_filter': corridor_filter,
        'dept_filter': dept_filter,
        'total_scheduled': blocks_qs.count(),
        'coordinated_count': blocks_qs.filter(is_coordinated=True).count(),
    }
    return render(request, 'master_schedule.html', context)


@login_required_404
def department_portal_view(request):
    """
    Department Block Demanding Portal (BDMS Integration):
    Allows field engineers of TMS, SMMS, and TDMS to file block requests,
    view real-time AI conflict analysis, and discover co-located shadow block opportunities.
    """
    dept = request.GET.get('dept', 'TMS')
    demands = MaintenanceDemand.objects.filter(source_system=dept).select_related('corridor', 'assigned_machine')
    corridors = Corridor.objects.all()
    machines = MachineAsset.objects.filter(department=dept)

    context = {
        'active_dept': dept,
        'demands': demands,
        'corridors': corridors,
        'machines': machines,
    }
    return render(request, 'department_portal.html', context)


@login_required_404
def analytics_view(request):
    """
    Analytics & Asset Downtime Reduction Metrics:
    Visual charts and breakdown of availability %, downtime saved per corridor,
    multi-department cooperation index, and train punctuality safety margins.
    """
    corridors = Corridor.objects.all()
    blocks = BlockSchedule.objects.all()
    
    # Per corridor breakdown
    corridor_stats = []
    for c in corridors:
        c_blocks = blocks.filter(corridor=c)
        saved_mins = c_blocks.aggregate(s=Sum('estimated_downtime_saved_minutes'))['s'] or 0
        corridor_stats.append({
            'code': c.code,
            'name': c.name,
            'blocks_count': c_blocks.count(),
            'coordinated_count': c_blocks.filter(is_coordinated=True).count(),
            'saved_hours': round(saved_mins / 60.0, 1),
            'gmt': c.gmt,
        })

    # Department distribution
    tms_blocks = blocks.filter(participating_departments__icontains='TMS').count()
    smms_blocks = blocks.filter(participating_departments__icontains='SMMS').count()
    tdms_blocks = blocks.filter(participating_departments__icontains='TDMS').count()

    runs = OptimizationRun.objects.all()[:10]

    context = {
        'corridor_stats': corridor_stats,
        'tms_blocks': tms_blocks,
        'smms_blocks': smms_blocks,
        'tdms_blocks': tdms_blocks,
        'runs': runs,
    }
    return render(request, 'analytics.html', context)


# ==========================================
# AJAX / REST API ENDPOINTS
# ==========================================

@require_POST
@login_required_404
def api_run_optimizer(request):
    """
    Trigger the AI Optimizer on demand via AJAX.
    """
    try:
        data = json.loads(request.body) if request.body else {}
        horizon = data.get('horizon', 'WEEKLY')
        strategy = data.get('strategy', 'MULTI_OBJECTIVE_BALANCED')
        
        result = optimize_block_schedule(horizon=horizon, strategy=strategy)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@login_required_404
def api_inject_emergency(request):
    """
    Simulates injection of an emergency defect (e.g. Broken Rail or OHE Snap)
    to test dynamic re-planning.
    """
    try:
        data = json.loads(request.body) if request.body else {}
        corridor_id = data.get('corridor_id')
        corridor = Corridor.objects.get(id=corridor_id) if corridor_id else Corridor.objects.first()

        defect_type = data.get('defect_type', 'RAIL_FRACTURE')
        today = timezone.now().date()

        if defect_type == 'RAIL_FRACTURE':
            demand = MaintenanceDemand.objects.create(
                demand_id=f"EMG-TMS-{timezone.now().strftime('%H%M%S')}",
                source_system='TMS',
                corridor=corridor,
                track_line='UP',
                km_start=132.4,
                km_end=132.6,
                activity_name='EMERGENCY: Rail Web Fracture Detected by Keyman',
                activity_code='TMS_EMG_FRACT',
                defect_description='Complete rail break discovered at weld joint km 132/4. Speed restricted to stop/dead slow. Emergency clamp applied.',
                criticality='EMERGENCY',
                duration_hours=2.0,
                requires_power_block=False,
                requires_traffic_block=True,
                speed_restriction_imposed=True,
                speed_restriction_kmh=15,
                due_date=today,
                overdue_days=0,
                manpower_required=16,
            )
        else: # OHE Breakdown
            demand = MaintenanceDemand.objects.create(
                demand_id=f"EMG-TDMS-{timezone.now().strftime('%H%M%S')}",
                source_system='TDMS',
                corridor=corridor,
                track_line='DN',
                km_start=178.0,
                km_end=178.5,
                activity_name='EMERGENCY: OHE Catenary Dropper Snapped',
                activity_code='TDMS_EMG_CATENARY',
                defect_description='Panto entangling risk. Overhanging catenary dropper wire near neutral section. Immediate 25kV power block required.',
                criticality='EMERGENCY',
                duration_hours=1.5,
                requires_power_block=True,
                requires_traffic_block=True,
                speed_restriction_imposed=True,
                speed_restriction_kmh=20,
                due_date=today,
                overdue_days=0,
                manpower_required=10,
            )

        emergency_block = replan_emergency_defect(demand)

        return JsonResponse({
            'status': 'success',
            'message': f'Emergency {demand.activity_name} injected successfully!',
            'demand_id': demand.demand_id,
            'block_id': emergency_block.block_id,
            'ai_score': demand.ai_priority_score,
            'notes': demand.ai_urgency_notes
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@login_required_404
def api_submit_demand(request):
    """
    Allows submitting a new maintenance demand with immediate AI scoring.
    """
    try:
        data = json.loads(request.body)
        corridor = get_object_or_404(Corridor, id=data['corridor_id'])
        
        assigned_machine = None
        if data.get('machine_id'):
            assigned_machine = MachineAsset.objects.filter(id=data['machine_id']).first()

        due_date = datetime.datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        today = timezone.now().date()
        overdue_days = max(0, (today - due_date).days) if due_date < today else 0

        demand = MaintenanceDemand.objects.create(
            demand_id=data['demand_id'],
            source_system=data['source_system'],
            corridor=corridor,
            track_line=data['track_line'],
            km_start=float(data['km_start']),
            km_end=float(data['km_end']),
            activity_name=data['activity_name'],
            defect_description=data['defect_description'],
            criticality=data['criticality'],
            duration_hours=float(data.get('duration_hours', 2.5)),
            requires_power_block=data.get('requires_power_block', False),
            requires_traffic_block=data.get('requires_traffic_block', True),
            speed_restriction_imposed=data.get('speed_restriction_imposed', False),
            speed_restriction_kmh=int(data['speed_restriction_kmh']) if data.get('speed_restriction_kmh') else None,
            due_date=due_date,
            overdue_days=overdue_days,
            assigned_machine=assigned_machine,
            manpower_required=int(data.get('manpower_required', 10)),
            status='PENDING'
        )

        score, notes = calculate_criticality_score(demand)
        demand.save()

        # Check for co-located demands that could be bundled
        co_located = MaintenanceDemand.objects.filter(
            corridor=corridor,
            track_line__in=[demand.track_line, 'BOTH'],
            status__in=['PENDING', 'AI_RECOMMENDED']
        ).exclude(id=demand.id).filter(
            Q(km_start__range=(demand.km_start - 10.0, demand.km_end + 10.0)) |
            Q(km_end__range=(demand.km_start - 10.0, demand.km_end + 10.0))
        )

        co_located_list = [{
            'id': c.demand_id,
            'dept': c.source_system,
            'activity': c.activity_name,
            'km': f"{c.km_start:.1f}-{c.km_end:.1f}"
        } for c in co_located]

        return JsonResponse({
            'status': 'success',
            'demand_id': demand.demand_id,
            'ai_score': score,
            'notes': notes,
            'co_located_candidates': co_located_list
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_GET
@login_required_404
def api_check_co_location(request):
    """
    Live AI assistance: As a user types km and corridor in the form,
    this endpoint looks up existing demands in the vicinity from other departments.
    """
    corridor_id = request.GET.get('corridor_id')
    km_start = request.GET.get('km_start')
    km_end = request.GET.get('km_end')
    dept = request.GET.get('dept', '')

    if not (corridor_id and km_start and km_end):
        return JsonResponse({'candidates': []})

    try:
        km_s = float(km_start)
        km_e = float(km_end)
        
        candidates = MaintenanceDemand.objects.filter(
            corridor_id=corridor_id
        ).exclude(source_system=dept).filter(
            Q(km_start__range=(km_s - 8.0, km_e + 8.0)) |
            Q(km_end__range=(km_s - 8.0, km_e + 8.0))
        )[:5]

        results = [{
            'id': c.demand_id,
            'dept': c.source_system,
            'activity': c.activity_name,
            'km': f"{c.km_start:.1f} - {c.km_end:.1f}",
            'criticality': c.get_criticality_display(),
            'score': c.ai_priority_score
        } for c in candidates]

        return JsonResponse({'candidates': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def login_view(request):
    """
    Railway Operations Authentication Login:
    Authenticates field engineers & operating controllers against Django integrated database.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    error_message = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            error_message = "Invalid Indian Railways portal credentials. Please check your username and password."

    return render(request, 'login.html', {'error_message': error_message})


def signup_view(request):
    """
    Department Staff Registration:
    Creates user account and associates UserProfile with department (TMS, SMMS, TDMS, COA).
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    error_message = None
    divisions = Division.objects.all()

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        department = request.POST.get('department', 'TMS')
        designation = request.POST.get('designation', 'Senior Section Engineer')
        employee_id = request.POST.get('employee_id', '').strip()
        division_id = request.POST.get('division_id')

        if not username or not password:
            error_message = "Username and password are required."
        elif password != password_confirm:
            error_message = "Passwords do not match."
        elif len(password) < 5:
            error_message = "Password must be at least 5 characters."
        elif User.objects.filter(username=username).exists():
            error_message = f"Username '{username}' is already registered in the railway portal."
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            div = Division.objects.filter(id=division_id).first() if division_id else None
            UserProfile.objects.create(
                user=user,
                department=department,
                designation=designation,
                employee_id=employee_id,
                division=div
            )
            login(request, user)
            return redirect('dashboard')

    return render(request, 'signup.html', {
        'error_message': error_message,
        'divisions': divisions
    })


def logout_view(request):
    """
    Safely terminates session and redirects to login.
    """
    logout(request)
    return redirect('login')


