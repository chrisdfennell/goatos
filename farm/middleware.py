from django.shortcuts import redirect
from django.conf import settings
from django.http import JsonResponse
import zoneinfo
import os


class TimezoneMiddleware:
    """Set the process timezone from FarmSettings so date.today() and
    timezone.localdate() use the farm's configured timezone."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._tz_loaded = False

    def __call__(self, request):
        if not self._tz_loaded:
            try:
                from farm.models import FarmSettings
                fs = FarmSettings.objects.first()
                if fs and fs.timezone:
                    os.environ['TZ'] = fs.timezone
                    settings.TIME_ZONE = fs.timezone
                    try:
                        import time
                        time.tzset()
                    except AttributeError:
                        pass  # Windows doesn't have tzset
            except Exception:
                pass
            self._tz_loaded = True
        return self.get_response(request)


class AjaxFormMiddleware:
    """Convert redirect responses to JSON for AJAX form submissions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                and response.status_code in (301, 302)):
            return JsonResponse({'success': True, 'redirect': response.url})
        return response


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
