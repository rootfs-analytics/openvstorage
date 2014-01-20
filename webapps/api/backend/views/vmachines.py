# license see http://www.openvstorage.com/licenses/opensource/
"""
VMachine module
"""
import json

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action, link
from rest_framework.exceptions import NotAcceptable
from django.http import Http404
from ovs.dal.lists.vmachinelist import VMachineList
from ovs.dal.lists.volumestoragerouterlist import VolumeStorageRouterList
from ovs.dal.hybrids.vmachine import VMachine
from ovs.dal.hybrids.pmachine import PMachine
from ovs.dal.datalist import DataList
from ovs.dal.dataobjectlist import DataObjectList
from ovs.lib.vmachine import VMachineController
from ovs.dal.exceptions import ObjectNotFoundException
from backend.serializers.serializers import SimpleSerializer, FullSerializer
from backend.decorators import required_roles, expose, validate


class VMachineViewSet(viewsets.ViewSet):
    """
    Information about machines
    """
    permission_classes = (IsAuthenticated,)

    @expose(internal=True, customer=True)
    @required_roles(['view'])
    def list(self, request, format=None):
        """
        Overview of all machines
        """
        _ = request, format
        vmachines = VMachineList.get_vmachines().reduced
        serializer = SimpleSerializer(vmachines, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @expose(internal=True, customer=True)
    @required_roles(['view'])
    @validate(VMachine)
    def retrieve(self, request, obj):
        """
        Load information about a given vMachine
        """
        _ = request
        return Response(FullSerializer(VMachine, instance=obj).data, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VMachine)
    def rollback(self, request, obj):
        """
        Clones a machine
        """
        task = VMachineController.rollback.delay(machineguid=obj.guid,
                                                 timestamp=request.DATA['timestamp'])
        return Response(task.id, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VMachine)
    def snapshot(self, request, obj):
        """
        Snapshots a given machine
        """
        label = str(request.DATA['name'])
        is_consistent = True if request.DATA['consistent'] else False  # Assure boolean type
        task = VMachineController.snapshot.delay(machineguid=obj.guid,
                                                 label=label,
                                                 is_consistent=is_consistent)
        return Response(task.id, status=status.HTTP_200_OK)

    @link()
    @expose(internal=True)
    @required_roles(['view'])
    @validate(VMachine)
    def get_vsas(self, request, obj):
        """
        Returns a list of VSA vMachine guids
        """
        _ = request
        vsa_vmachine_guids = []
        for vdisk in obj.vdisks:
            if vdisk.vsrid:
                vsr = VolumeStorageRouterList.get_by_vsrid(vdisk.vsrid)
                vsa_vmachine_guids.append(vsr.serving_vmachine.guid)
        return Response(vsa_vmachine_guids, status=status.HTTP_200_OK)

    @link()
    @expose(internal=True)
    @required_roles(['view'])
    @validate(VMachine)
    def get_vpools(self, request, obj):
        """
        Returns the vPool guid(s) associated with the given vMachine
        """
        _ = request
        vpool_guids = []
        for vdisk in obj.vdisks:
            vpool_guids.append(vdisk.vpool.guid)
        return Response(vpool_guids, status=status.HTTP_200_OK)

    @link()
    @expose(internal=True)
    @required_roles(['view'])
    @validate(VMachine)
    def get_children(self, request, obj):
        """
        Returns a list of vMachines guid(s) of children of a given vMachine
        """
        _ = request
        children_vmachine_guids = set()
        for vdisk in obj.vdisks:
            for cdisk in vdisk.child_vdisks:
                children_vmachine_guids.add(cdisk.vmachine_guid)
        return Response(children_vmachine_guids, status=status.HTTP_200_OK)

    @expose(internal=True)
    @required_roles(['view'])
    def filter(self, request, pk=None, format=None):
        """
        Filters vMachines based on a filter object
        """
        _ = request, pk, format
        query_result = DataList({'object': VMachine,
                                 'data': DataList.select.DESCRIPTOR,
                                 'query': request.DATA['query']}).data  # noqa
        # pylint: enable=line-too-long
        vmachines = DataObjectList(query_result, VMachine).reduced
        serializer = SimpleSerializer(vmachines, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VMachine)
    def set_as_template(self, request, obj):
        """
        Sets a given machine as template
        """
        _ = request
        task = VMachineController.set_as_template.delay(machineguid=obj.guid)
        return Response(task.id, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VMachine)
    def create_from_template(self, request, obj):
        """
        Creates a vMachine based on a vTemplate
        """
        try:
            pmachine = PMachine(request.DATA['pmachineguid'])
        except ObjectNotFoundException:
            raise Http404
        if obj.is_vtemplate is False:
            raise NotAcceptable
        task = VMachineController.create_from_template.delay(machineguid=obj.guid,
                                                             pmachineguid=pmachine.guid,
                                                             name=str(request.DATA['name']),
                                                             description=str(request.DATA['description']))
        return Response(task.id, status=status.HTTP_200_OK)

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VMachine)
    def create_multiple_from_template(self, request, obj):
        """
        Creates a certain amount of vMachines based on a vTemplate
        """
        pmachineguids = request.DATA['pmachineguids']
        if len(pmachineguids) == 0:
            raise NotAcceptable
        try:
            for pmachienguid in pmachineguids:
                _ = PMachine(pmachienguid)
        except ObjectNotFoundException:
            raise Http404
        if obj.is_vtemplate is False:
            raise NotAcceptable
        amount = request.DATA['amount']
        start = request.DATA['start']
        if not isinstance(amount, int) or not isinstance(start, int):
            raise NotAcceptable
        amount = max(1, amount)
        start = max(0, start)
        task = VMachineController.create_multiple_from_template.delay(machineguid=obj.guid,
                                                                      pmachineguids=pmachineguids,
                                                                      amount=amount,
                                                                      start=start,
                                                                      name=str(request.DATA['name']),
                                                                      description=str(request.DATA['description']))
        return Response(task.id, status=status.HTTP_200_OK)
