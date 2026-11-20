from rest_framework import permissions


class IsTripOwner(permissions.BasePermission):
    """
    Object-level permission to allow trip owners to access their trip.
    If trip.user is None, allow read/email access (for unauthenticated frontend guest sessions).
    """

    def has_object_permission(self, request, view, obj):
        # Unauthenticated/guest trips are accessible
        if obj.user is None:
            return True
        # If user is attached, must be the owner
        return request.user and request.user.is_authenticated and obj.user_id == request.user.id
