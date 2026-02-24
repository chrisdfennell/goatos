from django.shortcuts import redirect
from django.conf import settings


class PinGateMiddleware:
    """Simple PIN-based authentication middleware.

    Checks if the user has entered the correct PIN (stored in session).
    Redirects to the PIN entry page if not authenticated.
    Set FARM_PIN in .env to enable. Leave unset to disable.
    """

    EXEMPT_URLS = ['/pin/', '/admin/', '/static/', '/media/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If no PIN is configured, skip authentication entirely
        if not getattr(settings, 'FARM_PIN', None):
            return self.get_response(request)

        # Allow exempt URLs through
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return self.get_response(request)

        # Check if user has authenticated
        if not request.session.get('pin_authenticated'):
            return redirect('pin_login')

        return self.get_response(request)
