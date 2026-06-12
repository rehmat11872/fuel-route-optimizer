from rest_framework import serializers


class OptimizeRouteRequestSerializer(serializers.Serializer):
    start_location = serializers.CharField(max_length=255, trim_whitespace=True)
    end_location = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_start_location(self, value: str) -> str:
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Start location must be at least 3 characters.")
        return value.strip()

    def validate_end_location(self, value: str) -> str:
        if len(value.strip()) < 3:
            raise serializers.ValidationError("End location must be at least 3 characters.")
        return value.strip()

    def validate(self, attrs):
        if attrs["start_location"].lower() == attrs["end_location"].lower():
            raise serializers.ValidationError("Start and end locations must be different.")
        return attrs
