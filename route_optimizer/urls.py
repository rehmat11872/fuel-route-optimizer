from django.urls import path

from route_optimizer.views import HealthCheckView, OptimizeRouteView


urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("optimize-route/", OptimizeRouteView.as_view(), name="optimize-route"),
]
