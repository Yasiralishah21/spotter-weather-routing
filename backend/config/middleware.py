from django.http import HttpResponse


class CorsMiddleware:
    """Allow the local Vite app to call the API directly if the proxy is not used."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        allowed = origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:")
        if request.method == "OPTIONS" and allowed:
            response = HttpResponse()
            self._stamp(response, origin)
            return response
        response = self.get_response(request)
        if allowed:
            self._stamp(response, origin)
        return response

    @staticmethod
    def _stamp(response, origin):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        response["Vary"] = "Origin"
