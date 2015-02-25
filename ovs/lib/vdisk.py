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
Module for VDiskController
"""
import pickle
import uuid
import os
import time

from ovs.lib.helpers.decorators import log
from ovs.celery_run import celery
from ovs.dal.hybrids.vdisk import VDisk
from ovs.dal.hybrids.vmachine import VMachine
from ovs.dal.hybrids.pmachine import PMachine
from ovs.dal.hybrids.storagedriver import StorageDriver
from ovs.dal.hybrids.storagerouter import StorageRouter
from ovs.dal.lists.vdisklist import VDiskList
from ovs.dal.lists.storagedriverlist import StorageDriverList
from ovs.dal.lists.vpoollist import VPoolList
from ovs.dal.lists.pmachinelist import PMachineList
from ovs.dal.hybrids.vpool import VPool
from ovs.extensions.hypervisor.factory import Factory
from ovs.extensions.storageserver.storagedriver import StorageDriverClient
from ovs.log.logHandler import LogHandler
from ovs.lib.mdsservice import MDSServiceController
from ovs.extensions.generic.sshclient import SSHClient
from ovs.extensions.generic.system import System
from ovs.extensions.generic.volatilemutex import VolatileMutex
from ovs.extensions.openstack.oscinder import OpenStackCinder
from volumedriver.storagerouter.storagerouterclient import MDSMetaDataBackendConfig, MDSNodeConfig

logger = LogHandler('lib', name='vdisk')


class VDiskController(object):
    """
    Contains all BLL regarding VDisks
    """

    @staticmethod
    @celery.task(name='ovs.disk.list_volumes')
    def list_volumes(vpool_guid=None):
        """
        List all known volumes on a specific vpool or on all
        """
        if vpool_guid is not None:
            vpool = VPool(vpool_guid)
            storagedriver_client = StorageDriverClient.load(vpool)
            response = storagedriver_client.list_volumes()
        else:
            response = []
            for vpool in VPoolList.get_vpools():
                storagedriver_client = StorageDriverClient.load(vpool)
                response.extend(storagedriver_client.list_volumes())
        return response

    @staticmethod
    @celery.task(name='ovs.disk.delete_from_voldrv')
    @log('VOLUMEDRIVER_TASK')
    def delete_from_voldrv(volumename, storagedriver_id):
        """
        Delete a disk
        Triggered by volumedriver messages on the queue
        @param volumename: volume id of the disk
        """
        _ = storagedriver_id  # For logging purposes
        disk = VDiskList.get_vdisk_by_volume_id(volumename)
        if disk is not None:
            mutex = VolatileMutex('{}_{}'.format(volumename, disk.devicename))
            try:
                mutex.acquire(wait=20)
                pmachine = None
                try:
                    pmachine = PMachineList.get_by_storagedriver_id(disk.storagedriver_id)
                except RuntimeError as ex:
                    if 'could not be found' not in str(ex):
                        raise
                    # else: pmachine can't be loaded, because the volumedriver doesn't know about it anymore
                if pmachine is not None:
                    limit = 5
                    hypervisor = Factory.get(pmachine)
                    exists = hypervisor.file_exists(disk.vpool, disk.devicename)
                    while limit > 0 and exists is True:
                        time.sleep(1)
                        exists = hypervisor.file_exists(disk.vpool, disk.devicename)
                        limit -= 1
                    if exists is True:
                        logger.info('Disk {0} still exists, ignoring delete'.format(disk.devicename))
                        return
                logger.info('Delete disk {}'.format(disk.name))
                for mds_service in disk.mds_services:
                    mds_service.delete()
                disk.delete()
            finally:
                mutex.release()

    @staticmethod
    @celery.task(name='ovs.disk.resize_from_voldrv')
    @log('VOLUMEDRIVER_TASK')
    def resize_from_voldrv(volumename, volumesize, volumepath, storagedriver_id):
        """
        Resize a disk
        Triggered by volumedriver messages on the queue

        @param volumepath: path on hypervisor to the volume
        @param volumename: volume id of the disk
        @param volumesize: size of the volume
        """
        pmachine = PMachineList.get_by_storagedriver_id(storagedriver_id)
        storagedriver = StorageDriverList.get_by_storagedriver_id(storagedriver_id)
        hypervisor = Factory.get(pmachine)
        volumepath = hypervisor.clean_backing_disk_filename(volumepath)
        mutex = VolatileMutex('{}_{}'.format(volumename, volumepath))
        try:
            mutex.acquire(wait=30)
            disk = VDiskList.get_vdisk_by_volume_id(volumename)
            if disk is None:
                disk = VDiskList.get_by_devicename_and_vpool(volumepath, storagedriver.vpool)
                if disk is None:
                    disk = VDisk()
        finally:
            mutex.release()
        disk.devicename = volumepath
        disk.volume_id = volumename
        disk.size = volumesize
        disk.vpool = storagedriver.vpool
        disk.save()
        MDSServiceController.ensure_safety(disk)

    @staticmethod
    @celery.task(name='ovs.disk.rename_from_voldrv')
    @log('VOLUMEDRIVER_TASK')
    def rename_from_voldrv(volumename, volume_old_path, volume_new_path, storagedriver_id):
        """
        Rename a disk
        Triggered by volumedriver messages

        @param volumename: volume id of the disk
        @param volume_old_path: old path on hypervisor to the volume
        @param volume_new_path: new path on hypervisor to the volume
        """
        pmachine = PMachineList.get_by_storagedriver_id(storagedriver_id)
        hypervisor = Factory.get(pmachine)
        volume_old_path = hypervisor.clean_backing_disk_filename(volume_old_path)
        volume_new_path = hypervisor.clean_backing_disk_filename(volume_new_path)
        disk = VDiskList.get_vdisk_by_volume_id(volumename)
        if disk:
            logger.info('Move disk {} from {} to {}'.format(disk.name,
                                                            volume_old_path,
                                                            volume_new_path))
            disk.devicename = volume_new_path
            disk.save()

    @staticmethod
    @celery.task(name='ovs.disk.clone')
    def clone(diskguid, snapshotid, devicename, pmachineguid, machinename, machineguid=None):
        """
        Clone a disk
        """
        pmachine = PMachine(pmachineguid)
        hypervisor = Factory.get(pmachine)
        description = '{} {}'.format(machinename, devicename)
        properties_to_clone = ['description', 'size', 'type', 'retentionpolicyguid',
                               'snapshotpolicyguid', 'autobackup']
        vdisk = VDisk(diskguid)
        location = hypervisor.get_backing_disk_path(machinename, devicename)

        new_vdisk = VDisk()
        new_vdisk.copy(vdisk, include=properties_to_clone)
        new_vdisk.parent_vdisk = vdisk
        new_vdisk.name = '{0}-clone'.format(vdisk.name)
        new_vdisk.description = description
        new_vdisk.devicename = hypervisor.clean_backing_disk_filename(location)
        new_vdisk.parentsnapshot = snapshotid
        new_vdisk.vmachine = VMachine(machineguid) if machineguid else vdisk.vmachine
        new_vdisk.vpool = vdisk.vpool
        new_vdisk.save()

        storagedriver = StorageDriverList.get_by_storagedriver_id(vdisk.storagedriver_id)
        if storagedriver is None:
            raise RuntimeError('Could not find StorageDriver with id {0}'.format(vdisk.storagedriver_id))

        mds_service = MDSServiceController.get_preferred_mds(storagedriver.storagerouter, vdisk.vpool)
        if mds_service is None:
            raise RuntimeError('Could not find a MDS service')

        logger.info('Clone snapshot {} of disk {} to location {}'.format(snapshotid, vdisk.name, location))
        volume_id = vdisk.storagedriver_client.create_clone(
            target_path=location,
            metadata_backend_config=MDSMetaDataBackendConfig([MDSNodeConfig(address=str(mds_service.service.storagerouter.ip),
                                                                            port=mds_service.service.ports[0])]),
            parent_volume_id=str(vdisk.volume_id),
            parent_snapshot_id=str(snapshotid),
            node_id=str(vdisk.storagedriver_id)
        )
        new_vdisk.volume_id = volume_id
        new_vdisk.save()
        MDSServiceController.ensure_safety(new_vdisk)

        return {'diskguid': new_vdisk.guid,
                'name': new_vdisk.name,
                'backingdevice': location}

    @staticmethod
    @celery.task(name='ovs.disk.create_snapshot')
    def create_snapshot(diskguid, metadata, snapshotid=None):
        """
        Create a disk snapshot

        @param diskguid: guid of the disk
        @param metadata: dict of metadata
        """
        disk = VDisk(diskguid)
        logger.info('Create snapshot for disk {}'.format(disk.name))
        if snapshotid is None:
            snapshotid = str(uuid.uuid4())
        metadata = pickle.dumps(metadata)
        disk.storagedriver_client.create_snapshot(
            str(disk.volume_id),
            snapshot_id=snapshotid,
            metadata=metadata
        )
        disk.invalidate_dynamics(['snapshots'])
        return snapshotid

    @staticmethod
    @celery.task(name='ovs.disk.delete_snapshot')
    def delete_snapshot(diskguid, snapshotid):
        """
        Delete a disk snapshot

        @param diskguid: guid of the disk
        @param snapshotid: id of the snapshot

        @todo: Check if new volumedriver storagedriver upon deletion
        of a snapshot has built-in protection to block it from being deleted
        if a clone was created from it.
        """
        disk = VDisk(diskguid)
        logger.info('Deleting snapshot {} from disk {}'.format(snapshotid, disk.name))
        disk.storagedriver_client.delete_snapshot(str(disk.volume_id), str(snapshotid))
        disk.invalidate_dynamics(['snapshots'])

    @staticmethod
    @celery.task(name='ovs.disk.set_as_template')
    def set_as_template(diskguid):
        """
        Set a disk as template

        @param diskguid: guid of the disk
        """
        disk = VDisk(diskguid)
        disk.storagedriver_client.set_volume_as_template(str(disk.volume_id))

    @staticmethod
    @celery.task(name='ovs.disk.rollback')
    def rollback(diskguid, timestamp):
        """
        Rolls back a disk based on a given disk snapshot timestamp
        """
        disk = VDisk(diskguid)
        snapshots = [snap for snap in disk.snapshots if snap['timestamp'] == timestamp]
        if not snapshots:
            raise ValueError('No snapshot found for timestamp {}'.format(timestamp))
        snapshotguid = snapshots[0]['guid']
        disk.storagedriver_client.rollback_volume(str(disk.volume_id), snapshotguid)
        disk.invalidate_dynamics(['snapshots'])
        return True

    @staticmethod
    @celery.task(name='ovs.disk.create_from_template')
    def create_from_template(diskguid, machinename, devicename, pmachineguid, machineguid=None, storagedriver_guid=None):
        """
        Create a disk from a template

        @param parentdiskguid: guid of the disk
        @param location: location where virtual device should be created (eg: myVM)
        @param devicename: device file name for the disk (eg: mydisk-flat.vmdk)
        @param machineguid: guid of the machine to assign disk to
        @return diskguid: guid of new disk
        """

        pmachine = PMachine(pmachineguid)
        hypervisor = Factory.get(pmachine)
        disk_path = hypervisor.get_disk_path(machinename, devicename)

        description = '{} {}'.format(machinename, devicename)
        properties_to_clone = [
            'description', 'size', 'type', 'retentionpolicyid',
            'snapshotpolicyid', 'vmachine', 'vpool']

        vdisk = VDisk(diskguid)
        if vdisk.vmachine and not vdisk.vmachine.is_vtemplate:
            # Disk might not be attached to a vmachine, but still be a template
            raise RuntimeError('The given vdisk does not belong to a template')

        if storagedriver_guid is not None:
            storagedriver_id = StorageDriver(storagedriver_guid).storagedriver_id
        else:
            storagedriver_id = vdisk.storagedriver_id
        storagedriver = StorageDriverList.get_by_storagedriver_id(storagedriver_id)
        if storagedriver is None:
            raise RuntimeError('Could not find StorageDriver with id {0}'.format(storagedriver_id))

        new_vdisk = VDisk()
        new_vdisk.copy(vdisk, include=properties_to_clone)
        new_vdisk.vpool = vdisk.vpool
        new_vdisk.devicename = hypervisor.clean_backing_disk_filename(disk_path)
        new_vdisk.parent_vdisk = vdisk
        new_vdisk.name = '{}-clone'.format(vdisk.name)
        new_vdisk.description = description
        new_vdisk.vmachine = VMachine(machineguid) if machineguid else vdisk.vmachine
        new_vdisk.save()

        mds_service = MDSServiceController.get_preferred_mds(storagedriver.storagerouter, vdisk.vpool)
        if mds_service is None:
            raise RuntimeError('Could not find a MDS service')

        logger.info('Create disk from template {} to new disk {} to location {}'.format(
            vdisk.name, new_vdisk.name, disk_path
        ))
        try:
            volume_id = vdisk.storagedriver_client.create_clone_from_template(
                target_path=disk_path,
                metadata_backend_config=MDSMetaDataBackendConfig([MDSNodeConfig(address=str(mds_service.service.storagerouter.ip),
                                                                                port=mds_service.service.ports[0])]),
                parent_volume_id=str(vdisk.volume_id),
                node_id=str(storagedriver_id)
            )
            new_vdisk.volume_id = volume_id
            new_vdisk.save()
            MDSServiceController.ensure_safety(new_vdisk)

        except Exception as ex:
            logger.error('Clone disk on volumedriver level failed with exception: {0}'.format(str(ex)))
            new_vdisk.delete()
            raise

        # Allow "regular" users to use this volume
        # Do not use run for other user than ovs as it blocks asking for root password
        # Do not use run_local for other user as it doesn't have permission
        # So this method only works if this is called by root or ovs
        storagerouter = StorageRouter(new_vdisk.storagerouter_guid)
        mountpoint = storagedriver.mountpoint
        location = "{0}{1}".format(mountpoint, disk_path)
        client = SSHClient(storagerouter.pmachine.ip)
        print(client.run('chmod 664 "{0}"'.format(location)))
        print(client.run('chown ovs:ovs "{0}"'.format(location)))
        return {'diskguid': new_vdisk.guid, 'name': new_vdisk.name,
                'backingdevice': disk_path}

    @staticmethod
    @celery.task(name='ovs.disk.create_volume')
    def create_volume(location, size):
        """
        Create a volume using filesystem calls
        Calls "truncate" to create sparse raw file
        TODO: use volumedriver API
        TODO: model VDisk() and return guid

        @param location: location, filename
        @param size: size of volume, GB
        @return None
        """
        if os.path.exists(location):
            raise RuntimeError('File already exists at %s' % location)
        client = SSHClient()
        try:
            output = client.run_local('truncate -s {0}G "{1}"'.format(size, location))
        except SystemExit as ex:
            raise RuntimeError(str(ex))
        output = output.replace('\xe2\x80\x98', '"').replace('\xe2\x80\x99', '"')
        if not os.path.exists(location):
            raise RuntimeError('Cannot create file %s. Output: %s' % (location, output))
        VDiskController.own_volume(location)

    @staticmethod
    @celery.task(name='ovs.disk.delete_volume')
    def delete_volume(location):
        """
        Create a volume using filesystem calls
        Calls "rm" to delete raw file
        TODO: use volumedriver API
        TODO: delete VDisk from model

        @param location: location, filename
        @return None
        """
        if not os.path.exists(location):
            logger.error('File already deleted at %s' % location)
            return
        client = SSHClient()
        output = client.run('rm -f "{0}"'.format(location))
        output = output.replace('\xe2\x80\x98', '"').replace('\xe2\x80\x99', '"')
        if os.path.exists(location):
            raise RuntimeError('Could not delete file %s, check logs. Output: %s' % (location, output))
        if output == '':
            return True
        raise RuntimeError(output)

    @staticmethod
    @celery.task(name='ovs.disk.extend_volume')
    def extend_volume(location, size):
        """
        Extend a volume using filesystem calls
        Calls "truncate" to create sparse raw file
        TODO: use volumedriver API
        TODO: model VDisk() and return guid

        @param location: location, filename
        @param size: size of volume, GB
        @return None
        """
        if not os.path.exists(location):
            raise RuntimeError('Volume not found at %s, use create_volume first.' % location)
        client = SSHClient()
        print(client.run('truncate -s {0}G "{1}"'.format(size, location)))
        VDiskController.own_volume(location)

    @staticmethod
    def own_volume(location):
        """
        Change permissions and ownership of file
        """
        if not os.path.exists(location):
            raise RuntimeError('Volume not found at %s, use create_volume first.' % location)

        client = SSHClient()
        osc = OpenStackCinder()
        print(client.run('chmod 664 "{0}"'.format(location)))
        try:
            if osc.is_devstack:
                print(client.run('chgrp stack "{0}"'.format(location)))
            elif osc.is_openstack:
                print(client.run('chgrp cinder "{0}"'.format(location)))
        except SystemExit as ex:
            raise RuntimeError(str(ex))
