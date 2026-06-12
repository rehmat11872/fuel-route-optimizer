from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class RouteOptimizerError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "route_optimizer_error"

    def __init__(self, message: str, code: str | None = None, status_code: int | None = None):
        self.message = message
        self.code = code or self.default_code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)


class RoutingServiceError(RouteOptimizerError):
    default_code = "routing_service_error"
    status_code = status.HTTP_502_BAD_GATEWAY


class FuelStationError(RouteOptimizerError):
    default_code = "fuel_station_error"


def api_exception_handler(exc, context):
    if isinstance(exc, RouteOptimizerError):
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=exc.status_code,
        )

    response = exception_handler(exc, context)
    if response is not None:
        return response

    return Response(
        {"detail": "An unexpected error occurred.", "code": "internal_error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
