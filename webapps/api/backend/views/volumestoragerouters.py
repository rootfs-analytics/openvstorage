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
from rest_framework.decorators import action
from ovs.dal.lists.volumestoragerouterlist import VolumeStorageRouterList
from ovs.dal.lists.vmachinelist import VMachineList
from ovs.dal.hybrids.volumestoragerouter import VolumeStorageRouter
from backend.serializers.serializers import FullSerializer
from backend.decorators import required_roles, expose, validate
from backend.toolbox import Toolbox


class VolumeStorageRouterViewSet(viewsets.ViewSet):
    """
    Information about VolumeStorageRouters
    """
    permission_classes = (IsAuthenticated,)

    @expose(internal=True)
    @required_roles(['view'])
    def list(self, request, format=None):
        """
        Overview of all VolumeStorageRouters
        """
        _ = format
        vsrs = VolumeStorageRouterList.get_volumestoragerouters()
        vsrs, serializer, contents = Toolbox.handle_list(vsrs, request)
        serialized = serializer(VolumeStorageRouter, contents=contents, instance=vsrs, many=True)
        return Response(serialized.data, status=status.HTTP_200_OK)

    @expose(internal=True)
    @required_roles(['view'])
    @validate(VolumeStorageRouter)
    def retrieve(self, request, obj):
        """
        Load information about a given VolumeStorageRouter
        """
        contents = Toolbox.handle_retrieve(request)
        return Response(FullSerializer(VolumeStorageRouter, contents=contents, instance=obj).data, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True)
    @validate(VolumeStorageRouter)
    def can_be_deleted(self, request, obj):
        """
        Checks whether a VSR can be deleted
        """
        _ = request
        result = True
        vmachine = obj.serving_vmachine
        pmachine = vmachine.pmachine
        vmachines = VMachineList.get_customer_vmachines()
        pmachine_guids = [vmachine.pmachine_guid for vmachine in vmachines]
        vpool = obj.vpool
        if pmachine.guid in pmachine_guids:
            result = False
        if any(vdisk for vdisk in vpool.vdisks if vdisk.vsrid == obj.vsrid):
            result = False
        return Response(result, status=status.HTTP_200_OK)
