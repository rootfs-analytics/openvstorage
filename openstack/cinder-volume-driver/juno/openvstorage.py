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
OpenStack Cinder driver - interface to OVS api
- uses OVS library calls (VDiskController)
- uses Cinder logging
"""

import socket
import time

# External libs: OVS
try:
    from ovs.dal.hybrids.vdisk import VDisk
    from ovs.dal.lists.pmachinelist import PMachineList
    from ovs.dal.lists.vdisklist import VDiskList
    from ovs.dal.lists.vpoollist import VPoolList
    from ovs.lib.vdisk import VDiskController
except ImportError:
    # CI Testing, all external libs are mocked
    # or using the driver without all required libs
    VDisk = None
    PMachineList = None
    VDiskList = None
    VPoolList = None
    VDiskController = None

#Third party
from oslo.config import cfg

#Cinder
from cinder import exception
from cinder.image import image_utils
from cinder.openstack.common import log as logging
from cinder.volume import api
from cinder.volume import driver


LOG = logging.getLogger(__name__)
HELP = 'Vpool to use for volumes - backend is defined by vpool not by us.'
OPTS = [cfg.StrOpt('vpool_name',
                   default = '',
                   help = HELP)]

CONF = cfg.CONF
CONF.register_opts(OPTS)


# Utils
def _debug_vol_info(call, volume):
    """Debug print volume info
    """
    vol_info = []
    for item in sorted(dir(volume)):
        if not item.startswith('__'):
            try:
                vol_info.append("%s: %s" % (item, getattr(volume, item)))
            except Exception as ex:
                LOG.info('DEBUG failed %s' % str(ex))
    LOG.debug('[%s] %s' % (call, str(vol_info)))


class OVSVolumeDriver(driver.VolumeDriver):
    """OVS Volume Driver plugin for Cinder
    (UNOFFICIAL support for Icehouse (stable), Juno (stable))
    This is an unsupported (by OpenStack) driver since Icehouse and Juno
    no longer accept drivers
    Configuration file: /etc/cinder/cinder.conf
    Required parameters in config file:

    # single driver
    volume_driver = cinder.volume.drivers.ovs_volume_driver.OVSVolumeDriver
    volume_backend_name = <VPOOLNAME>
    vpool_name = <VPOOLNAME>

    # multiple drivers
    enabled backends: Open vStorage
    [Open vStorage]
    volume_driver = cinder.volume.drivers.ovs_volume_driver.OVSVolumeDriver
    volume_backend_name = <VPOOLNAME>
    vpool_name = <VPOOLNAME>

    Required configuration:
        cinder type-create <TYPENAME> # e.g. Open vStorage
        cinder type-key <TYPENAME> set volume_backend_name=<VPOOLNAME>
    """
    VERSION = '1.0.6'

    def __init__(self, *args, **kwargs):
        """Init: args, kwargs pass through;
        Options come from CONF
        """
        super(OVSVolumeDriver, self).__init__(*args, **kwargs)
        LOG.info('INIT %s %s %s ' % (CONF.vpool_name, str(args), str(kwargs)))
        self.configuration.append_config_values(OPTS)
        self._vpool_name = self.configuration.vpool_name
        self._vp = VPoolList.get_vpool_by_name(self._vpool_name)
        self._context = None
        self._db = kwargs.get('db', None)
        self._api = api.API()

    # Volume operations

    def initialize_connection(self, volume, connector):
        """Allow connection to connector and return connection info.
        """
        _debug_vol_info("INIT_CONN", volume)

        return {'driver_volume_type': 'file',
                'data': {'vpoolname': self._vpool_name,
                         'device_path': volume.provider_location}}

    def create_volume(self, volume):
        """Creates a volume.
        Called on "cinder create ..." or "nova volume-create ..."
        :param volume: volume reference (sqlalchemy Model)
        """
        _debug_vol_info("CREATE", volume)

        hostname = str(volume.host)
        name = volume.display_name
        if not name:
            name = volume.name
        mountpoint = self._get_hostname_mountpoint(hostname)
        location = '{}/{}.raw'.format(mountpoint, name)
        size = volume.size

        LOG.info('DO_CREATE_VOLUME %s %s' % (location, size))
        VDiskController.create_volume(location = location,
                                      size = size)
        volume['provider_location'] = location

        try:
            ovs_disk = self._find_ovs_model_disk_by_location(location,
                                                             hostname)
        except RuntimeError:
            VDiskController.delete_volume(location = location)
            raise

        ovs_disk.cinder_id = volume.id
        ovs_disk.name = name
        ovs_disk.save()
        return {'provider_location': volume['provider_location']}

    def delete_volume(self, volume):
        """Deletes a logical volume.
        Called on "cinder delete ... "
        :param volume: volume reference (sqlalchemy Model)
        """
        _debug_vol_info("DELETE", volume)

        location = volume.provider_location
        if location is not None:
            LOG.info('DO_DELETE_VOLUME %s' % (location))
            VDiskController.delete_volume(location = location)

    def copy_image_to_volume(self, context, volume, image_service, image_id):
        """Copy image to volume
        Called on "nova volume-create --image-id ..."
        or "cinder create --image-id"
        Downloads image from glance server into local .raw
        :param volume: volume reference (sqlalchemy Model)
        """
        _debug_vol_info("CP_IMG_TO_VOL", volume)
        LOG.info("CP_IMG_TO_VOL %s %s" % (image_service, image_id))

        name = volume.display_name
        if not name:
            name = volume.name
            volume.display_name = volume.name

        # downloading from an existing image
        destination_path = volume.provider_location
        if destination_path:
            try:
                LOG.info('CP_IMG_TO_VOL Deleting existing empty raw file %s '
                         % destination_path)
                VDiskController.delete_volume(location = destination_path)
                LOG.info('CP_IMG_TO_VOL Downloading image to %s'
                         % destination_path)
                image_utils.fetch_to_raw(context,
                                         image_service,
                                         image_id,
                                         destination_path,
                                         '1M',
                                         size = volume['size'])
                LOG.info('CP_IMG_TO_VOL Resizing volume to size %s'
                         % volume['size'])
                self.extend_volume(volume = volume, size_gb = volume['size'])
            except Exception as ex:
                LOG.error('CP_IMG_TO_VOL Internal error %s ' % unicode(ex))
                self.delete_volume(volume)
                raise
            ovs_disk = self._find_ovs_model_disk_by_location(
                volume.provider_location, str(volume.host))
            ovs_disk.name = name
            ovs_disk.save()

    def copy_volume_to_image(self, context, volume, image_service, image_meta):
        """Copy the volume to the specified image.
        Called on "cinder upload-to-image ...volume... ...image-name..."
        :param volume: volume reference (sqlalchemy Model)
        """
        _debug_vol_info("CP_VOL_TO_IMG", volume)
        LOG.info("CP_VOL_TO_IMG %s %s" % (image_service, image_meta))
        super(OVSVolumeDriver, self).copy_volume_to_image(
            context, volume, image_service, image_meta)

    def create_cloned_volume(self, volume, src_vref):
        """Create a cloned volume from another volume.
        Called on "cinder create --source-volid ... "

        :param volume: volume reference - target volume (sqlalchemy Model)
        :param src_vref: volume reference - source volume (sqlalchemy Model)

        OVS: Create clone from template if the source is a template
             Create volume from snapshot if the source is a volume
             - create snapshot of source volume if it doesn't have snapshots
        """
        _debug_vol_info('CREATE_CLONED_VOL', volume)
        _debug_vol_info('CREATE_CLONED_VOL Source', src_vref)

        mountpoint = self._get_hostname_mountpoint(str(volume.host))
        name = volume.display_name
        if not name:
            name = volume.name
            volume.display_name = volume.name

        pmachineguid = self._find_ovs_model_pmachine_guid_by_hostname(
            str(volume.host))

        #source
        source_ovs_disk = self._find_ovs_model_disk_by_location(
            str(src_vref.provider_location), src_vref.host)
        if source_ovs_disk.info['object_type'] == 'TEMPLATE':
            LOG.info('[CREATE_FROM_TEMPLATE] VDisk %s is a template'
                     % source_ovs_disk.devicename)

            # cloning from a template
            LOG.debug('[CREATE FROM TEMPLATE] ovs_disk %s '
                      % (source_ovs_disk.devicename))

            disk_meta = VDiskController.create_from_template(
                diskguid = source_ovs_disk.guid,
                machinename = "",
                devicename = str(name),
                pmachineguid = pmachineguid,
                machineguid = None,
                storagedriver_guid = None)
            volume['provider_location'] = '{}{}'.format(
                mountpoint, disk_meta['backingdevice'])
            LOG.debug('[CREATE FROM TEMPLATE] New volume %s'
                      % volume['provider_location'])
            vdisk = VDisk(disk_meta['diskguid'])
            vdisk.cinder_id = volume.id
            vdisk.name = name
            LOG.debug('[CREATE FROM TEMPLATE] Updating meta %s %s'
                      % (volume.id, name))
            vdisk.save()
        else:
            LOG.info('[THIN CLONE] VDisk %s is not a template'
                     % source_ovs_disk.devicename)
            # We do not support yet full volume clone
            # - requires "emancipate" functionality
            # So for now we'll take a snapshot
            # (or the latest snapshot existing) and clone from that snapshot
            if len(source_ovs_disk.snapshots) == 0:
                metadata = {'label': "Cinder clone snapshot {0}".format(name),
                            'is_consistent': False,
                            'timestamp': time.time(),
                            'machineguid': source_ovs_disk.vmachine_guid,
                            'is_automatic': False}

                LOG.debug('CREATE_SNAP %s %s' % (name, str(metadata)))
                snapshotid = VDiskController.create_snapshot(
                    diskguid = source_ovs_disk.guid,
                    metadata = metadata,
                    snapshotid = None)
                LOG.debug('CREATE_SNAP OK')

            else:
                snapshotid = source_ovs_disk.snapshots[-1]['guid']
            LOG.debug('[CREATE CLONE FROM SNAP] %s ' % snapshotid)

            disk_meta = VDiskController.clone(diskguid = source_ovs_disk.guid,
                                              snapshotid = snapshotid,
                                              devicename = str(name),
                                              pmachineguid = pmachineguid,
                                              machinename = "",
                                              machineguid=None)
            volume['provider_location'] = '{}{}'.format(
                mountpoint, disk_meta['backingdevice'])

            LOG.debug('[CLONE FROM SNAP] Meta: %s' % str(disk_meta))
            LOG.debug('[CLONE FROM SNAP] New volume %s'
                      % volume['provider_location'])
            vdisk = VDisk(disk_meta['diskguid'])
            vdisk.cinder_id = volume.id
            vdisk.name = name
            vdisk.save()
        return {'provider_location': volume['provider_location'],
                'display_name': volume['display_name']}

    # Volumedriver stats

    def get_volume_stats(self, refresh=False):
        """Get volumedriver stats
        If 'refresh' is True, update the stats first.
        """
        LOG.info('VOLUMEDRIVER STATS')
        data = {}
        data['volume_backend_name'] = self._vpool_name
        data['vendor_name'] = 'Open vStorage'
        data['driver_version'] = self.VERSION
        data['storage_protocol'] = 'OVS'

        data['total_capacity_gb'] = 'infinite'
        data['free_capacity_gb'] = 'infinite'
        data['reserved_percentage'] = 0
        data['QoS_support'] = False
        return data

    # Snapshots operations

    def create_snapshot(self, snapshot):
        """Creates a snapshot.
        Called on "nova image-create " or "cinder snapshot-create "
        :param snapshot: snapshot reference (sqlalchemy Model)
        """
        _debug_vol_info('CREATE_SNAP', snapshot)
        volume = snapshot.volume
        _debug_vol_info('CREATE_SNAP_VOL', volume)

        hostname = volume.host
        location = volume.provider_location
        ovs_disk = self._find_ovs_model_disk_by_location(location, hostname)
        metadata = {'label': "{0} (OpenStack)".format(snapshot.display_name),
                    'is_consistent': False,
                    'timestamp': time.time(),
                    'machineguid': ovs_disk.vmachine_guid,
                    'is_automatic': False}

        LOG.debug('CREATE_SNAP %s %s' % (snapshot.display_name, str(metadata)))
        VDiskController.create_snapshot(diskguid = ovs_disk.guid,
                                        metadata = metadata,
                                        snapshotid = str(snapshot.id))
        LOG.debug('CREATE_SNAP OK')

    def delete_snapshot(self, snapshot):
        """Deletes a snapshot.
        :param snapshot: snapshot reference (sqlalchemy Model)
        """
        _debug_vol_info('DELETE_SNAP', snapshot)
        volume = snapshot.volume
        hostname = volume.host
        location = volume.provider_location

        ovs_disk = self._find_ovs_model_disk_by_location(location, hostname)
        LOG.debug('DELETE_SNAP %s' % snapshot.id)
        VDiskController.delete_snapshot(diskguid = ovs_disk.guid,
                                        snapshotid = str(snapshot.id))
        LOG.debug('DELETE_SNAP OK')

    def create_volume_from_snapshot(self, volume, snapshot):
        """Creates a volume from a snapshot.
        Called on "cinder create --snapshot-id ..."
        :param snapshot: snapshot reference (sqlalchemy Model)
        :param volume: volume reference (sqlalchemy Model)

        Volume here is just a ModelObject, it doesn't exist physically,
            it will be created by OVS.
        Diskguid to be passed to the clone method is the ovs diskguid of the
            parent of the snapshot with snapshot.id

        OVS: Clone from arbitrary volume,
        requires volumedriver 3.6 release > 15.08.2014
        """
        _debug_vol_info('CLONE_VOL', volume)
        _debug_vol_info('CLONE_SNAP', snapshot)

        mountpoint = self._get_hostname_mountpoint(str(volume.host))
        ovs_snap_disk = self._find_ovs_model_disk_by_snapshot_id(snapshot.id)
        devicename = volume.display_name
        if not devicename:
            devicename = volume.name
        pmachineguid = self._find_ovs_model_pmachine_guid_by_hostname(
            str(volume.host))

        LOG.info('[CLONE FROM SNAP] %s %s %s %s'
                 % (ovs_snap_disk.guid, snapshot.id, devicename, pmachineguid))
        try:
            disk_meta = VDiskController.clone(diskguid = ovs_snap_disk.guid,
                                              snapshotid = snapshot.id,
                                              devicename = devicename,
                                              pmachineguid = pmachineguid,
                                              machinename = "",
                                              machineguid=None)
            volume['provider_location'] = '{}{}'.format(
                mountpoint, disk_meta['backingdevice'])

            LOG.debug('[CLONE FROM SNAP] Meta: %s' % str(disk_meta))
            LOG.debug('[CLONE FROM SNAP] New volume %s'
                      % volume['provider_location'])
            vdisk = VDisk(disk_meta['diskguid'])
            vdisk.cinder_id = volume.id
            vdisk.name = devicename
            vdisk.save()
        except Exception as ex:
            LOG.error('CLONE FROM SNAP: Internal error %s ' % str(ex))
            self.delete_volume(volume)
            self.delete_snapshot(snapshot)
            raise

        return {'provider_location': volume['provider_location'],
                'display_name': volume['display_name']}

    # Attach/detach volume to instance/host

    def attach_volume(self, context, volume, instance_uuid, host_name,
                      mountpoint):
        """Callback for volume attached to instance or host.
        """
        _debug_vol_info('ATTACH_VOL', volume)
        LOG.info('ATTACH_VOL %s %s %s'
                 % (instance_uuid, host_name, mountpoint))

    def detach_volume(self, context, volume):
        """Callback for volume detached.
        """
        _debug_vol_info('DETACH_VOL', volume)

    # Extend

    def extend_volume(self, volume, size_gb):
        """Extend volume to new size size_gb
        """
        _debug_vol_info('EXTEND_VOL', volume)
        LOG.info('EXTEND_VOL Size %s' % size_gb)
        location = volume.provider_location
        if location is not None:
            LOG.info('DO_EXTEND_VOLUME %s' % (location))
            VDiskController.extend_volume(location = location,
                                          size = size_gb)

    # Override parent behavior (NotImplementedError)
    # Not actually implemented

    def create_export(self, context, volume):
        """Just to override parent behavior
        """
        _debug_vol_info("CREATE_EXP", volume)

    def remove_export(self, context, volume):
        """Just to override parent behavior.
        """
        _debug_vol_info("RM_EXP", volume)

    def ensure_export(self, context, volume):
        """Just to override parent behavior.
        """
        _debug_vol_info("ENS_EXP", volume)

    def terminate_connection(self, volume, connector, force):
        """Just to override parent behavior.
        """
        _debug_vol_info("TERM_CONN", volume)
        LOG.info('TERM_CONN %s %s ' % (str(connector), force))

    def check_for_setup_error(self):
        """Just to override parent behavior.
        """
        if VDisk is None or PMachineList is None or VDiskList is None or\
           VPoolList is None or VDiskController is None:
            msg = 'Open vStorage libraries not found'
            raise exception.VolumeBackendAPIException(data=msg)

    def do_setup(self, context):
        """Any initialization the volume driver does while starting
        """
        _debug_vol_info('SETUP', context)
        self._context = context

    # Internal
    def _get_real_hostname(self, hostname):
        LOG.debug('[_GET REAL HOSTNAME] Hostname %s' % hostname)
        if not hostname or not isinstance(hostname, str):
            return socket.gethostname()
        if "#" in hostname:
            hostname, backend_name = hostname.split('#')
        if "@" in hostname:
            hostname, driver = hostname.split('@')
            return hostname
        return hostname

    def _get_hostname_mountpoint(self, hostname):
        """Find OVS vsr mountpoint for self._vp and hostname
        :return mountpoint: string, mountpoint
        """
        hostname = self._get_real_hostname(hostname)
        LOG.debug('[_GET HOSTNAME MOUNTPOINT] Hostname %s' % hostname)
        storagedrivers = [vsr for vsr in self._vp.storagedrivers
                          if str(vsr.storagerouter.name) == str(hostname)]
        if len(storagedrivers) == 1:
            LOG.debug('[_GET HOSTNAME MOUNTPOINT] Mountpoint %s'
                      % storagedrivers[0].mountpoint)
            return str(storagedrivers[0].mountpoint)
        elif not storagedrivers:
            msg = 'No vsr mountpoint found for Vpool %s and hostname %s'
            raise RuntimeError(msg % (self._vpool_name, hostname))

    def _find_ovs_model_disk_by_location(self, location, hostname, retry=3,
                                         timeout=3):
        """Find OVS disk object based on location and hostname
        :return VDisk: OVS DAL model object
        """
        hostname = self._get_real_hostname(hostname)
        LOG.debug('[_FIND OVS DISK] Location %s, hostname %s'
                  % (location, hostname))
        attempt = 0
        while attempt <= retry:
            for vd in VDiskList.get_vdisks():
                if vd.vpool:
                    for vsr in vd.vpool.storagedrivers:
                        if vsr.storagerouter.name == hostname:
                            _location = "{0}/{1}".format(vsr.mountpoint,
                                                         vd.devicename)
                            if _location == location:
                                LOG.info('Location %s Disk found %s'
                                         % (location, vd.guid))
                                disk = VDisk(vd.guid)
                                return disk
            msg = ' NO RESULT Attempt %s timeout %s max attempts %s'
            LOG.debug(msg % (attempt, timeout, retry))
            if timeout:
                time.sleep(timeout)
            attempt += 1
        raise RuntimeError('No disk found for location %s' % location)

    def _find_ovs_model_pmachine_guid_by_hostname(self, hostname):
        """Find OVS pmachine guid based on storagerouter name
        :return guid: GUID
        """
        hostname = self._get_real_hostname(hostname)
        LOG.debug('[_FIND OVS PMACHINE] Hostname %s' % (hostname))
        mapping = [(pm.guid, str(sr.name))
                   for pm in PMachineList.get_pmachines()
                   for sr in pm.storagerouters]
        for item in mapping:
            if item[1] == str(hostname):
                msg = 'Found pmachineguid %s for Hostname %s'
                LOG.info(msg % (item[0], hostname))
                return item[0]
        raise RuntimeError('No PMachine guid found for Hostname %s' % hostname)

    def _find_ovs_model_disk_by_snapshot_id(self, snapshotid):
        """Find OVS disk object based on snapshot id
        :return VDisk: OVS DAL model object
        """
        LOG.debug('[_FIND OVS DISK] Snapshotid %s' % snapshotid)
        for disk in VDiskList.get_vdisks():
            snaps_guid = [s['guid'] for s in disk.snapshots]
            if str(snapshotid) in snaps_guid:
                LOG.info('[_FIND OVS DISK] Snapshot id %s Disk found %s'
                         % (snapshotid, disk))
                return disk
        raise RuntimeError('No disk found for snapshotid %s' % snapshotid)

    def _snapshot_has_children(self, snapshotid):
        """Find if snapshot has children, in OVS Model
        :return True/False
        """
        LOG.debug('[_FIND CHILDREN OF SNAPSHOT] Snapshotid %s' % snapshotid)
        for vdisk in VDiskList.get_vdisks():
            if vdisk.parentsnapshot == snapshotid:
                return True
        return False