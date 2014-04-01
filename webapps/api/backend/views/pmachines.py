# Copyright 2014 CloudFounders NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
PMachine module
"""
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ovs.dal.lists.pmachinelist import PMachineList
from ovs.dal.hybrids.pmachine import PMachine
from backend.serializers.serializers import FullSerializer
from backend.decorators import required_roles, expose, validate
from backend.toolbox import Toolbox


class PMachineViewSet(viewsets.ViewSet):
    """
    Information about pMachines
    """
    permission_classes = (IsAuthenticated,)

    @expose(internal=True)
    @required_roles(['view'])
    def list(self, request, format=None):
        """
        Overview of all pMachines
        """
        _ = format
        pmachines = PMachineList.get_pmachines()
        pmachines, serializer, contents = Toolbox.handle_list(pmachines, request)
        serialized = serializer(PMachine, contents=contents, instance=pmachines, many=True)
        return Response(serialized.data, status=status.HTTP_200_OK)

    @expose(internal=True)
    @required_roles(['view'])
    @validate(PMachine)
    def retrieve(self, request, obj):
        """
        Load information about a given pMachine
        """
        contents = Toolbox.handle_retrieve(request)
        return Response(FullSerializer(PMachine, contents=contents, instance=obj).data, status=status.HTTP_200_OK)
