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
VPool module
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import link, action
from rest_framework.exceptions import NotAcceptable
from ovs.dal.lists.vpoollist import VPoolList
from ovs.dal.hybrids.vpool import VPool
from ovs.dal.hybrids.storageappliance import StorageAppliance
from ovs.lib.vpool import VPoolController
from ovs.lib.storageappliance import StorageApplianceController
from ovs.dal.hybrids.storagerouter import StorageRouter
from backend.decorators import required_roles, expose, validate, get_list, get_object, celery_task


class VPoolViewSet(viewsets.ViewSet):
    """
    Information about vPools
    """
    permission_classes = (IsAuthenticated,)
    prefix = r'vpools'
    base_name = 'vpools'

    @expose(internal=True, customer=True)
    @required_roles(['view'])
    @get_list(VPool, 'name')
    def list(self, request, format=None, hints=None):
        """
        Overview of all vPools
        """
        _ = request, format, hints
        return VPoolList.get_vpools()

    @expose(internal=True, customer=True)
    @required_roles(['view'])
    @validate(VPool)
    @get_object(VPool)
    def retrieve(self, request, obj):
        """
        Load information about a given vPool
        """
        _ = request
        return obj

    @action()
    @expose(internal=True)
    @required_roles(['view', 'create'])
    @validate(VPool)
    @celery_task()
    def sync_vmachines(self, request, obj):
        """
        Syncs the vMachine of this vPool
        """
        _ = request
        return VPoolController.sync_with_hypervisor.delay(obj.guid)

    @link()
    @expose(internal=True)
    @required_roles(['view'])
    @validate(VPool)
    @get_list(StorageAppliance)
    def storageappliances(self, request, obj, hints):
        """
        Retreives a list of StorageAppliances, serving a given vPool
        """
        _ = request
        storageappliance_guids = []
        storageappliance = []
        for storagerouter in obj.storagerouters:
            storageappliance_guids.append(storagerouter.storageappliance_guid)
            if hints['full'] is True:
                storageappliance.append(storagerouter.storageappliance)
        return storageappliance if hints['full'] is True else storageappliance_guids

    @action()
    @expose(internal=True, customer=True)
    @required_roles(['view', 'create'])
    @validate(VPool)
    @celery_task()
    def update_storagerouters(self, request, obj):
        """
        Update Storage Routers for a given vPool (both adding and removing Storage Routers)
        """
        storageappliances = []
        if 'storageappliance_guids' in request.DATA:
            if request.DATA['storageappliance_guids'].strip() != '':
                for storageappliance_guid in request.DATA['storageappliance_guids'].strip().split(','):
                    storageappliance = StorageAppliance(storageappliance_guid)
                    storageappliances.append((storageappliance.ip, storageappliance.machineid))
        if 'storagerouter_guid' not in request.DATA:
            raise NotAcceptable('No Storage Router guid passed')
        storagerouter_guids = []
        if 'storagerouter_guids' in request.DATA:
            if request.DATA['storagerouter_guids'].strip() != '':
                for storagerouter_guid in request.DATA['storagerouter_guids'].strip().split(','):
                    storagerouter = StorageRouter(storagerouter_guid)
                    if storagerouter.vpool_guid != obj.guid:
                        raise NotAcceptable('Given Storage Router does not belong to this vPool')
                    storagerouter_guids.append(storagerouter.guid)

        storagerouter = StorageRouter(request.DATA['storagerouter_guid'])
        parameters = {'vpool_name':          obj.name,
                      'backend_type':        obj.backend_type,
                      'connection_host':     None if obj.backend_connection is None else obj.backend_connection.split(':')[0],
                      'connection_port':     None if obj.backend_connection is None else int(obj.backend_connection.split(':')[1]),
                      'connection_timeout':  0,  # Not in use anyway
                      'connection_username': obj.backend_login,
                      'connection_password': obj.backend_password,
                      'mountpoint_bfs':      storagerouter.mountpoint_bfs,
                      'mountpoint_temp':     storagerouter.mountpoint_temp,
                      'mountpoint_md':       storagerouter.mountpoint_md,
                      'mountpoint_cache':    storagerouter.mountpoint_cache,
                      'storage_ip':          storagerouter.storage_ip,
                      'vrouter_port':        storagerouter.port}
        for field in parameters:
            if not parameters[field] is int:
                parameters[field] = str(parameters[field])

        return StorageApplianceController.update_storagerouters.delay(storagerouter_guids, storageappliances, parameters)
