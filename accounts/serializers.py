from rest_framework import serializers


class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True, trim_whitespace=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8, required=True)


class LoginRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True, trim_whitespace=True)
    password = serializers.CharField(write_only=True, required=True)


class RequestOTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class VerifyOTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(min_length=6, max_length=6, required=True, trim_whitespace=True)

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Code must consist of 6 digits.")
        return value


class UserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
