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

from ovs.celery import celery
from ovs.dal.hybrids.vpool import VPool
from ovs.dal.lists.vmachinelist import VMachineList
from ovs.dal.lists.storagedriverlist import StorageDriverList
from ovs.extensions.fs.exportfs import Nfsexports
from ovs.extensions.hypervisor.factory import Factory
from ovs.lib.vmachine import VMachineController
from ovs.log.logHandler import LogHandler

logger = LogHandler('lib', name='vpool')


class VPoolController(object):
    """
    Contains all BLL related to VPools
    """

    @staticmethod
    @celery.task(name='ovs.vpool.mountpoint_available_from_voldrv')
    def mountpoint_available_from_voldrv(mountpoint, storagedriver_id):
        """
        Hook for (re)exporting the NFS mountpoint
        """
        storagedriver = StorageDriverList.get_by_storagedriver_id(storagedriver_id)
        if storagedriver is None:
            raise RuntimeError('A Storage Driver with id {0} could not be found.'.format(storagedriver_id))
        if storagedriver.storagerouter.pmachine.hvtype == 'VMWARE':
            nfs = Nfsexports()
            nfs.unexport(mountpoint)
            nfs.export(mountpoint)
            nfs.trigger_rpc_mountd()

    @staticmethod
    @celery.task(name='ovs.vpool.sync_with_hypervisor')
    def sync_with_hypervisor(vpool_guid):
        """
        Syncs all vMachines of a given vPool with the hypervisor
        """
        vpool = VPool(vpool_guid)
        for storagedriver in vpool.storagedrivers:
            pmachine = storagedriver.storagerouter.pmachine
            hypervisor = Factory.get(pmachine)
            for vm_object in hypervisor.get_vms_by_nfs_mountinfo(storagedriver.storage_ip, storagedriver.mountpoint):
                search_vpool = None if pmachine.hvtype == 'KVM' else vpool
                vmachine = VMachineList.get_by_devicename_and_vpool(
                    devicename=vm_object['backing']['filename'],
                    vpool=search_vpool
                )
                VMachineController.update_vmachine_config(vmachine, vm_object, pmachine)

    @staticmethod
    def can_be_served_on(storagerouter_guid):
        """
        temporary check to avoid creating 2 ganesha nfs exported vpools
        as this is not yet supported on volumedriverlevel
        """
        _ = storagerouter_guid
        return True

    @staticmethod
    @celery.task(name='ovs.vpool.set_configparams')
    def set_configparams(vpool_guid, configparams):
        """
        Sets configuration parameters to a given vpool/vdisk. Items not passed are (re)set.
        """
        vpool = VPool(vpool_guid)
        resolved_configs = {}
        for vdisk in vpool.vdisks:
            resolved_configs[vdisk.guid] = vdisk.resolved_configuration
        raw_config = vpool.configuration
        keys = ['iops', 'cache_strategy', 'cache_size', 'foc']
        for key in keys:
            if key not in configparams and key in raw_config:
                del raw_config[key]
            if key in configparams:
                raw_config[key] = configparams[key]
        vpool.configuration = raw_config
        vpool.save()
        for vdisk in vpool.vdisks:
            vdisk.invalidate_dynamics(['resolved_configuration'])
            resolved_config = resolved_configs[vdisk.guid]
            new_resolved_config = vdisk.resolved_configuration
            for key in keys:
                if resolved_config.get(key) != new_resolved_config.get(key):
                    # @TODO: update the 'key' property on the disk.
                    logger.info('Updating property {0} on vDisk {1} to {2}'.format(key, vdisk.guid, new_resolved_config.get(key)))
