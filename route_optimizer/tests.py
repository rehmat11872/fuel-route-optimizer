from django.test import SimpleTestCase
from rest_framework.test import APIClient

from route_optimizer.services.fuel_data import load_fuel_stations
from route_optimizer.services.openrouteservice import decode_polyline


class ApiSmokeTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST="localhost")

    def test_health_check(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_optimize_route_requires_locations(self):
        response = self.client.post("/api/optimize-route/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("start_location", response.json())
        self.assertIn("end_location", response.json())


class FuelDataTests(SimpleTestCase):
    def test_loads_attached_fuel_price_csv(self):
        stations = load_fuel_stations()

        self.assertGreater(len(stations), 8000)
        self.assertGreater(stations[0].price_per_gallon, 0)


class PolylineTests(SimpleTestCase):
    def test_decodes_openrouteservice_polyline(self):
        coordinates = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")

        self.assertEqual(len(coordinates), 3)
        self.assertAlmostEqual(coordinates[0].latitude, 38.5)
        self.assertAlmostEqual(coordinates[0].longitude, -120.2)
