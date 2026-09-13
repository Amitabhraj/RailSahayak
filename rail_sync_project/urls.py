"""rail_sync_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from scheduler import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard_view, name='dashboard'),
    path('data-hub/', views.data_hub_view, name='data_hub'),
    path('optimizer/', views.optimizer_studio_view, name='optimizer_studio'),
    path('schedule/', views.master_schedule_view, name='master_schedule'),
    path('department-portal/', views.department_portal_view, name='department_portal'),
    path('analytics/', views.analytics_view, name='analytics'),
    
    # Authentication Routes
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    
    # AJAX APIs
    path('api/run-optimizer/', views.api_run_optimizer, name='api_run_optimizer'),
    path('api/inject-emergency/', views.api_inject_emergency, name='api_inject_emergency'),
    path('api/submit-demand/', views.api_submit_demand, name='api_submit_demand'),
    path('api/check-co-location/', views.api_check_co_location, name='api_check_co_location'),
]

handler404 = 'scheduler.views.custom_404_view'

