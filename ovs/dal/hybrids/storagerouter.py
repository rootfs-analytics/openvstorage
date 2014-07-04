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
from ovs.dal.dataobject import DataObject
from ovs.dal.hybrids.vpool import VPool
from ovs.dal.hybrids.storageappliance import StorageAppliance
from ovs.extensions.storageserver.storagerouter import StorageRouterClient
import time


class StorageRouter(DataObject):
    """
    The StorageRouter class represents a Storage Router. A Storage Router is an application
    on a Storage Appliance to which the vDisks connect. The Storage Router is the gateway to the Storage Backend.
    """
    # pylint: disable=line-too-long
    __blueprint = {'name':             (None, str, 'Name of the Storage Router.'),
                   'description':      (None, str, 'Description of the Storage Router.'),
                   'port':             (None, int, 'Port on which the Storage Router is listening.'),
                   'cluster_ip':       (None, str, 'IP address on which the Storage Router is listening.'),
                   'storage_ip':       (None, str, 'IP address on which the vpool is shared to hypervisor'),
                   'storagerouter_id': (None, str, 'ID of the Storage Router as known by the Storage Router Drivers.'),
                   'mountpoint':       (None, str, 'Mountpoint from which the Storage Router serves data'),
                   'mountpoint_temp':  (None, str, 'Mountpoint for temporary workload (scrubbing etc)'),
                   'mountpoint_bfs':   (None, str, 'Mountpoint for the backend filesystem (used for local and distributed fs)'),
                   'mountpoint_md':    (None, str, 'Mountpoint for metadata'),
                   'mountpoint_cache': (None, str, 'Mountpoint for caching')}
    __relations = {'vpool':            (VPool, 'storagerouters'),
                   'storageappliance': (StorageAppliance, 'storagerouters')}
    __expiry = {'status':        (30, str),
                'statistics':     (4, dict),
                'stored_data':   (60, int)}
    # pylint: enable=line-too-long

    def _status(self):
        """
        Fetches the Status of the Storage Router.
        """
        _ = self
        return None

    def _statistics(self):
        """
        Aggregates the Statistics (IOPS, Bandwidth, ...) of the vDisks connected to the Storage Router.
        """
        client = StorageRouterClient()
        vdiskstatsdict = {}
        for key in client.stat_keys:
            vdiskstatsdict[key] = 0
            vdiskstatsdict['{0}_ps'.format(key)] = 0
        if self.vpool is not None:
            for disk in self.vpool.vdisks:
                if disk.storagerouter_id == self.storagerouter_id:
                    statistics = disk._statistics()  # Prevent double caching
                    for key, value in statistics.iteritems():
                        if key != 'timestamp':
                            vdiskstatsdict[key] += value
        vdiskstatsdict['timestamp'] = time.time()
        return vdiskstatsdict

    def _stored_data(self):
        """
        Aggregates the Stored Data in Bytes of the vDisks connected to the Storage Router.
        """
        if self.vpool is not None:
            return sum([disk.info['stored'] for disk in self.vpool.vdisks])
        return 0
