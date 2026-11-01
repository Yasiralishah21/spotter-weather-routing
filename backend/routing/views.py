import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from routing.services.analyze import analyze_trip
from routing.services.errors import UpstreamError
from routing.services.geocode import search_places

logger = logging.getLogger(__name__)


@require_GET
def health(_request):
    return JsonResponse({"status": "ok"})


@require_GET
def geocode(request):
    query = request.GET.get("q", "")
    try:
        results = search_places(query)
    except UpstreamError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse({"results": results})


@require_http_methods(["POST"])
def analyze(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be JSON."}, status=400)
    try:
        return JsonResponse(analyze_trip(payload))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except UpstreamError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except Exception:
        logger.exception("analyze failed")
        return JsonResponse(
            {"error": "Something went wrong while planning the trip."},
            status=500,
        )
