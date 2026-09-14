from django.shortcuts import render, redirect
from django.http import JsonResponse

class LoginRequired404Middleware:
    PUBLIC_URL_PREFIXES = (
        '/login',
        '/signup',
        '/user/request_user',
        '/logout',
        '/admin',
        '/static',
        '/media',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        if not request.user.is_authenticated:
            # Redirect unauthenticated visits on "/" to login page instead of showing 404
            if path == '/':
                return redirect('login')

            is_public = any(path.startswith(prefix) for prefix in self.PUBLIC_URL_PREFIXES)
            if not is_public:
                if path.startswith('/api/'):
                    return JsonResponse({
                        'status': 'error',
                        'message': '404 Not Found'
                    }, status=404)
                return render(request, '404.html', status=404)

        response = self.get_response(request)

        if response.status_code == 404 and 'text/html' in response.get('Content-Type', ''):
            if getattr(response, 'template_name', None) != ['404.html']:
                return render(request, '404.html', status=404)

        return response
