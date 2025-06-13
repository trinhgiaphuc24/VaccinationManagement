from rest_framework.permissions import BasePermission

class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.userRole == 'staff'

class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.userRole == 'patient'

class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user