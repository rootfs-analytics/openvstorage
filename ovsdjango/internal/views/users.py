from backend.serializers.user import UserSerializer, PasswordSerializer
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from ovs.dal.exceptions import ObjectNotFoundException
from ovs.dal.hybrids.user import User
from ovs.lib.user import User as APIUser
from django.http import Http404


class UserViewSet(viewsets.ViewSet):
    """
    Manage users
    """
    permission_classes = (IsAuthenticated,)

    def _get_object(self, guid):
        try:
            return User(guid)
        except ObjectNotFoundException:
            raise Http404

    def list(self, request, format=None):
        users = APIUser.get_users()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None, format=None):
        user = self._get_object(pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def create(self, request, format=None):
        serializer = UserSerializer(User(), request.DATA)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None, format=None):
        if pk is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            user = self._get_object(pk)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action()
    def set_password(self, request, pk=None, format=None):
        user = self._get_object(pk)
        serializer = PasswordSerializer(data=request.DATA)
        if serializer.is_valid():
            user.password = serializer.data['password']
            user.save()
            return Response(UserSerializer(user).data, status=status.HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
