from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from route_optimizer.serializers import OptimizeRouteRequestSerializer
from route_optimizer.services.optimizer import RouteOptimizationService


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class OptimizeRouteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = OptimizeRouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = RouteOptimizationService().optimize(
            start_location=serializer.validated_data["start_location"],
            end_location=serializer.validated_data["end_location"],
        )
        return Response(result, status=status.HTTP_200_OK)
