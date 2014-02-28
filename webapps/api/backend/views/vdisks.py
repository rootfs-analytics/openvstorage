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
VDisk module
"""
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from ovs.dal.lists.vdisklist import VDiskList
from ovs.dal.hybrids.vdisk import VDisk
from ovs.dal.hybrids.vmachine import VMachine
from ovs.dal.hybrids.vpool import VPool
from ovs.lib.vdisk import VDiskController
from backend.serializers.serializers import FullSerializer
from backend.decorators import required_roles, expose, validate
from backend.toolbox import Toolbox


class VDiskViewSet(viewsets.ViewSet):
    """
    Information about vDisks
    """
    permission_classes = (IsAuthenticated,)

    @expose(internal=True, customer=True)
    @required_roles(['view'])
    def list(self, request, format=None):
        """
        Overview of all vDisks
        """
        _ = format
        vmachineguid = request.QUERY_PARAMS.get('vmachineguid', None)
        vpoolguid = request.QUERY_PARAMS.get('vpoolguid', None)
        if vmachineguid is not None:
            vmachine = VMachine(vmachineguid)
            if vmachine.is_internal:
                vdisks = []
                for vsr in vmachine.served_vsrs:
                    for vdisk in vsr.vpool.vdisks:
                        if vdisk.vsrid == vsr.vsrid:
                            vdisks.append(vdisk)
            else:
                vdisks = vmachine.vdisks
        elif vpoolguid is not None:
            vpool = VPool(vpoolguid)
            vdisks = vpool.vdisks
        else:
            vdisks = VDiskList.get_vdisks()
        vdisks, serializer, contents = Toolbox.handle_list(vdisks, request, default_sort='vpool_guid,devicename')
        serialized = serializer(VDisk, contents=contents, instance=vdisks, many=True)
        return Response(serialized.data, status=status.HTTP_200_OK)

    @expose(internal=True, customer=True)
    @required_roles(['view'])
    @validate(VDisk)
    def retrieve(self, request, obj):
        """
        Load information about a given vDisk
        """
        contents = Toolbox.handle_retrieve(request)
        return Response(FullSerializer(VDisk, contents=contents, instance=obj).data, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VDisk)
    def rollback(self, request, obj):
        """
        Rollbacks a vDisk to a given timestamp
        """
        _ = format
        task = VDiskController.rollback.delay(diskguid=obj.guid,
                                              timestamp=request.DATA['timestamp'])
        return Response(task.id, status=status.HTTP_200_OK)

