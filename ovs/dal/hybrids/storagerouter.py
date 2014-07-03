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
StorageRouter module
"""
import time
from ovs.extensions.storageserver.volumestoragerouter import VolumeStorageRouterClient
from ovs.dal.dataobject import DataObject
from ovs.dal.hybrids.pmachine import PMachine


class StorageRouter(DataObject):
    """
    A StorageRouter represents the Open vStorage software stack, any (v)machine on which it is installed
    """
    # pylint: disable=line-too-long
    __blueprint = {'name':        (None,  str,  'Name of the vMachine.'),
                   'description': (None,  str,  'Description of the vMachine.'),
                   'machineid':   (None,  str,  'The hardware identifier of the vMachine'),
                   'ip':          (None,  str,  'IP Address of the vMachine, if available'),
                   'status':      ('OK',  ['OK', 'NOK'], 'Internal status of the software stack')}
    __relations = {'pmachine': (PMachine, 'storagerouters')}
    __expiry = {'statistics':       (5, dict),
                'stored_data':     (60, int),
                'failover_mode':   (60, str),
                'vmachines_guids': (15, list),
                'vpools_guids':    (15, list),
                'vdisks_guids':     (15, list)}
    # pylint: enable=line-too-long

    def _statistics(self):
        """
        Aggregates the Statistics (IOPS, Bandwidth, ...) of each vDisk of the vMachine.
        """
        client = VolumeStorageRouterClient()
        vdiskstatsdict = {}
        for key in client.stat_keys:
            vdiskstatsdict[key] = 0
            vdiskstatsdict['{0}_ps'.format(key)] = 0
        for vsr in self.vsrs:
            for vdisk in vsr.vpool.vdisks:
                if vdisk.vsrid == vsr.vsrid:
                    statistics = vdisk._statistics()  # Prevent double caching
                    for key, value in statistics.iteritems():
                        if key != 'timestamp':
                            vdiskstatsdict[key] += value
        vdiskstatsdict['timestamp'] = time.time()
        return vdiskstatsdict

    def _stored_data(self):
        """
        Aggregates the Stored Data of each vDisk of the vMachine.
        """
        data = 0
        for vsr in self.vsrs:
            for vdisk in vsr.vpool.vdisks:
                if vdisk.vsrid == vsr.vsrid:
                    data += vdisk.info['stored']
        return data

    def _failover_mode(self):
        """
        Gets the aggregated failover mode
        """
        status = 'UNKNOWN'
        status_code = 0
        for vsr in self.vsrs:
            for vdisk in vsr.vpool.vdisks:
                if vdisk.vsrid == vsr.vsrid:
                    mode = vdisk.info['failover_mode']
                    current_status_code = VolumeStorageRouterClient.FOC_STATUS[mode.lower()]
                    if current_status_code > status_code:
                        status = mode
                        status_code = current_status_code
        return status

    def _vmachines_guids(self):
        """
        Gets the vMachine guids served by this StorageRouter.
        Definition of "served by": vMachine whose disks are served by a given StorageRouter
        """
        vmachine_guids = set()
        for vsr in self.vsrs:
            for vdisk in vsr.vpool.vdisks:
                if vdisk.vsrid == vsr.vsrid:
                    if vdisk.vmachine_guid is not None:
                        vmachine_guids.add(vdisk.vmachine_guid)
        return list(vmachine_guids)

    def _vdisks_guids(self):
        """
        Gets the vDisk guids served by this StorageRouter.
        """
        vdisk_guids = []
        for vsr in self.vsrs:
            for vdisk in vsr.vpool.vdisks:
                if vdisk.vsrid == vsr.vsrid:
                    vdisk_guids.append(vdisk.guid)
        return vdisk_guids

    def _vpools_guids(self):
        """
        Gets the vPool guids linked to this StorageRouter (trough VolumeStorageRouter)
        """
        vpool_guids = set()
        for vsr in self.vsrs:
            vpool_guids.add(vsr.vpool_guid)
        return list(vpool_guids)
