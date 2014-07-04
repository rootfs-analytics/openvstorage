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
Wrapper class for the storagerouterclient of the voldrv team
"""

from volumedriver.storagerouter.storagerouterclient import StorageRouterClient as SRClient
from volumedriver.storagerouter.storagerouterclient import ClusterContact, Statistics, VolumeInfo
from ovs.plugin.provider.configuration import Configuration
from ovs.extensions.generic.system import Ovs
import json
import os

client_vpool_cache = {}
client_storagerouter_cache = {}


class StorageRouterClient(object):
    """
    Client to access storagerouterclient
    """

    FOC_STATUS = {'': 0,
                  'ok_standalone': 10,
                  'ok_sync': 10,
                  'catch_up': 20,
                  'degraded': 30}

    def __init__(self):
        """
        Init method
        """
        self.empty_statistics = lambda: Statistics()
        self.empty_info = lambda: VolumeInfo()
        self.stat_counters = ['backend_data_read', 'backend_data_written',
                              'backend_read_operations', 'backend_write_operations',
                              'cluster_cache_hits', 'cluster_cache_misses', 'data_read',
                              'data_written', 'metadata_store_hits', 'metadata_store_misses',
                              'read_operations', 'sco_cache_hits', 'sco_cache_misses',
                              'write_operations']
        self.stat_sums = {'operations': ['write_operations', 'read_operations'],
                          'cache_hits': ['sco_cache_hits', 'cluster_cache_hits'],
                          'data_transferred': ['data_written', 'data_read']}
        self.stat_keys = self.stat_counters + self.stat_sums.keys()

    def load(self, vpool):
        """
        Initializes the wrapper given a vpool name for which it finds the corresponding Storage Router
        Loads and returns the client
        """

        key = vpool.guid
        if key not in client_vpool_cache:
            cluster_contacts = []
            for storagerouter in vpool.storagerouters[:3]:
                cluster_contacts.append(ClusterContact(str(storagerouter.cluster_ip), storagerouter.port))
            client = SRClient(str(vpool.name), cluster_contacts)
            client_vpool_cache[key] = client
        return client_vpool_cache[key]


class StorageRouterConfiguration(object):
    """
    StorageRouter configuration class
    """
    def __init__(self, vpool_name):
        self._vpool = vpool_name
        self._config_specfile = os.path.join(Configuration.get('ovs.core.cfgdir'), 'templates', 'volumedriverfs.json')
        if not os.path.exists(os.path.join(Configuration.get('ovs.core.cfgdir'), 'voldrv_vpools')):
            os.makedirs(os.path.join(Configuration.get('ovs.core.cfgdir'), 'voldrv_vpools'))
        self._config_file = os.path.join(Configuration.get('ovs.core.cfgdir'), 'voldrv_vpools', '{}.json'.format(vpool_name))
        self._config_tmpfile = os.path.join(Configuration.get('ovs.core.cfgdir'), 'voldrv_vpools', '{}.json.tmp'.format(vpool_name))
        self._config_readfile_handler = None
        self._config_file_handler = None
        self._config_specfile_handler = None
        self._config_file_content = None

    def load_config(self):
        if os.path.exists(self._config_file) and not os.path.getsize(self._config_file) == 0:
            self._config_readfile_handler = open(self._config_file, 'r')
            self._config_file_handler = open(self._config_tmpfile, 'w')
            self._config_file_content = json.load(self._config_readfile_handler)
            self._config_readfile_handler.close()
        else:
            self._config_file_handler = open(self._config_file, 'w')
            self._config_specfile_handler = open(self._config_specfile, 'r')
            self._config_file_content = json.load(self._config_specfile_handler)
            self._config_specfile_handler.close()

    def write_config(self):
        json.dump(self._config_file_content, self._config_file_handler, indent=2)
        self._config_file_handler.close()
        if os.path.exists(self._config_tmpfile):
            os.rename(self._config_tmpfile, self._config_file)

    def add_cache(self):
        pass

    def configure_backend(self, backend_config):
        self.load_config()
        if not backend_config:
            raise ValueError('No backend config specified, unable to configure storagerouter')
        for key, value in backend_config.iteritems():
            self._config_file_content['backend_connection_manager'][key] = value
        self.write_config()

    def configure_readcache(self, readcaches, rspath):
        """
        Configures storage router content address cache
        @param readcaches: list of readcache configuration dictionaries
        """
        self.load_config()
        self._config_file_content['content_addressed_cache']['clustercache_mount_points'] = readcaches
        self._config_file_content['content_addressed_cache']['read_cache_serialization_path'] = rspath
        self.write_config()

    def configure_volumemanager(self, volumemanager_config):
        """
        Configures storage router volume manager
        @param volumemanager_config: dictionary with key/value pairs
        """
        self.load_config()
        for key, value in volumemanager_config.iteritems():
            self._config_file_content['volume_manager'][key] = value
        self.write_config()

    def configure_scocache(self, scocaches, trigger_gap, backoff_gap):
        """
        Configures storage router scocaches
        @param scocaches: list of scocache dictionaries
        @param trigger_gap: string to be set as trigger_gap value
        @param backoff_gap: string to be set as backoff gap value
        """
        self.load_config()
        self._config_file_content['scocache']['scocache_mount_points'] = scocaches
        self._config_file_content['scocache']['trigger_gap'] = trigger_gap
        self._config_file_content['scocache']['backoff_gap'] = backoff_gap
        self.write_config()

    def configure_hypervisor(self, hypervisor_type):
        """
        Configures the storage router to handle hypervisor specific behavior
        """
        self.load_config()
        if hypervisor_type == 'VMWARE':
            self._config_file_content['filesystem']['fs_virtual_disk_format'] = 'vmdk'
            self._config_file_content['filesystem']['fs_file_event_rules'] = [
                {'fs_file_event_rule_calls': ['Mknod', 'Unlink', 'Rename'],
                 'fs_file_event_rule_path_regex': '.*.vmx'},
                {'fs_file_event_rule_calls': ['Rename'],
                 'fs_file_event_rule_path_regex': '.*.vmx~'}
            ]
        elif hypervisor_type == 'KVM':
            self._config_file_content['filesystem']['fs_virtual_disk_format'] = 'raw'
            self._config_file_content['filesystem']['fs_raw_disk_suffix'] = '.raw'
            self._config_file_content['filesystem']['fs_file_event_rules'] = [
                {'fs_file_event_rule_calls': ['Mknod', 'Unlink', 'Rename', 'Write'],
                 'fs_file_event_rule_path_regex': '(?!vmcasts)(.*.xml)'}
            ]
        self.write_config()

    def configure_failovercache(self, failovercache):
        """
        Configures storage router failover cache path
        @param failovercache: path to the failover cache directory
        """
        self.load_config()
        self._config_file_content.update({'failovercache': {'failovercache_path': failovercache}})
        self.write_config()

    def configure_filesystem(self, filesystem_config):
        """
        Configures storage router filesystem properties
        @param filesystem_config: dictionary with key/value pairs
        """
        self.load_config()
        for key, value in filesystem_config.iteritems():
            self._config_file_content['filesystem'][key] = value
        self.write_config()

    def configure_volumerouter(self, vrouter_cluster, vrouter_config):
        """
        Configures storage router
        @param vrouter_config: dictionary of key/value pairs
        """
        unique_machine_id = Ovs.get_my_machine_id()
        self.load_config()
        if vrouter_config['vrouter_id'] == '{}{}'.format(self._vpool, unique_machine_id):
            for key, value in vrouter_config.iteritems():
                self._config_file_content['volume_router'][key] = value
        # Configure the vrouter arakoon with empty values in order to use tokyo cabinet
        self._config_file_content['volume_router']['vrouter_arakoon_cluster_id'] = ''
        self._config_file_content['volume_router']['vrouter_arakoon_cluster_nodes'] = []
        if not 'volume_router_cluster' in self._config_file_content:
            self._config_file_content['volume_router_cluster'] = {}
        self._config_file_content['volume_router_cluster'].update({'vrouter_cluster_id': vrouter_cluster})
        self.write_config()

    def configure_arakoon_cluster(self, arakoon_cluster_id, arakoon_nodes):
        """
        Configures storage router arakoon cluster
        @param arakoon_cluster_id: name of the arakoon cluster
        @param arakoon_nodes: dictionary of arakoon nodes in this cluster
        """
        self.load_config()
        if not 'volume_registry' in self._config_file_content:
            self._config_file_content['volume_registry'] = {}
        self._config_file_content['volume_registry']['vregistry_arakoon_cluster_id'] = arakoon_cluster_id
        self._config_file_content['volume_registry']['vregistry_arakoon_cluster_nodes'] = []
        for node_id, node_config in arakoon_nodes.iteritems():
            node_dict = {'node_id': node_id, 'host': node_config[0][0], 'port': node_config[1]}
            self._config_file_content['volume_registry']['vregistry_arakoon_cluster_nodes'].append(node_dict)
        self.write_config()

    def configure_event_publisher(self, queue_config):
        """
        Configures storage router event publisher
        @param queue_config: dictionary of with queue configuration key/value
        """
        self.load_config()
        if not "event_publisher" in self._config_file_content:
            self._config_file_content["event_publisher"] = {}
        for key, value in queue_config.iteritems():
            self._config_file_content["event_publisher"][key] = value
        self.write_config()

    def configure_filedriver(self, fd_config):
        """
        Configures cf filedriver component
        @param queue_config: dictionary of with filedriver configuration key/value
        """
        # @todo: http://jira.cloudfounders.com/browse/OVS-987

        self.load_config()
        if not "file_driver" in self._config_file_content:
            self._config_file_content["file_driver"] = {}

        for key, value in fd_config.iteritems():
            self._config_file_content["file_driver"][key] = value

        # remove obsolete entry
        if "filesystem" in self._config_file_content and "fs_backend_path" in self._config_file_content:
            self._config_file_content["filesystem"].pop("fs_backend_path")

        self.write_config()


class GaneshaConfiguration:

    def __init__(self):
        self._config_corefile = os.path.join(Configuration.get('ovs.core.cfgdir'), 'templates', 'ganesha-core.conf')
        self._config_exportfile = os.path.join(Configuration.get('ovs.core.cfgdir'), 'templates', 'ganesha-export.conf')

    def generate_config(self, target_file, params):
        with open(self._config_corefile, 'r') as core_config_file:
            config = core_config_file.read()
        with open(self._config_exportfile, 'r') as export_section_file:
            config += export_section_file.read()

        for key, value in params.iteritems():
            print 'replacing {0} by {1}'.format(key, value)
            config = config.replace(key, value)

        with open(target_file, 'wb') as config_out:
            config_out.write(config)
