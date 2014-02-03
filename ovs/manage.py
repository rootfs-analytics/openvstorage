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
OVS management module
"""

import subprocess
import uuid
import os
import re
import platform
import time
from ovs.plugin.provider.configuration import Configuration
from ovs.plugin.provider.console import Console
from ovs.plugin.provider.service import Service
from ovs.plugin.provider.package import Package
from ovs.plugin.provider.net import Net
from ovs.dal.hybrids.vmachine import VMachine
from ovs.dal.hybrids.pmachine import PMachine
from ovs.dal.hybrids.vpool import VPool
from ovs.dal.hybrids.volumestoragerouter import VolumeStorageRouter
from ovs.dal.lists.vmachinelist import VMachineList
from ovs.dal.lists.pmachinelist import PMachineList
from ovs.dal.lists.vpoollist import VPoolList
from ovs.extensions.hypervisor.factory import Factory
from ovs.extensions.db.arakoon.ArakoonManagement import ArakoonManagement
from ovs.extensions.storageserver.volumestoragerouter import VolumeStorageRouterConfiguration
from ovs.extensions.fs.fstab import Fstab


def boxed_message(lines, character='+', maxlength=80):
    """
    Embeds a set of lines into a box
    """
    character = str(character)  # This must be a string
    corrected_lines = []
    for line in lines:
        if len(line) > maxlength:
            linepart = ''
            for word in line.split(' '):
                if len(linepart + ' ' + word) <= maxlength:
                    linepart += word + ' '
                elif len(word) >= maxlength:
                    if len(linepart) > 0:
                        corrected_lines.append(linepart.strip())
                        linepart = ''
                    corrected_lines.append(word.strip())
                else:
                    if len(linepart) > 0:
                        corrected_lines.append(linepart.strip())
                    linepart = word + ' '
            if len(linepart) > 0:
                corrected_lines.append(linepart.strip())
        else:
            corrected_lines.append(line)
    maxlen = len(max(corrected_lines, key=len))
    newlines = [character * (maxlen + 10)]
    for line in corrected_lines:
        newlines.append('{0}  {1}{2}  {3}'.format(character * 3, line, ' ' * (maxlen - len(line)),
                                                  character * 3))
    newlines.append(character * (maxlen + 10))
    return '\n'.join(newlines)


class Configure():
    """
    Configuration class
    """

    def __init__(self):
        """
        Class constructor
        """
        pass

    @staticmethod
    def init_exportfs(vpool_name):
        """
        Configure nfs
        """
        from ovs.extensions.fs.exportfs import Nfsexports
        vpool_mountpoint = os.path.join(os.sep, 'mnt', vpool_name)
        if not os.path.exists(vpool_mountpoint):
            os.makedirs(vpool_mountpoint)
        Nfsexports().add(vpool_mountpoint, '*', 'rw,fsid={0},sync,no_root_squash,no_subtree_check'.format(uuid.uuid4()))
        subprocess.call(['service', 'nfs-kernel-server', 'start'])

    @staticmethod
    def load_data(master):
        """
        Load default data set
        """
        # Select/Create system vmachine
        hostname = platform.node()
        vmachine_list = VMachineList.get_vmachine_by_name(hostname)
        if vmachine_list and len(vmachine_list) == 1:
            print 'System vMachine already created, updating ...'
            vmachine = vmachine_list[0]
        elif not vmachine_list or len(vmachine_list) == 0:
            print 'Creating System vMachine'
            vmachine = VMachine()
        else:
            raise ValueError('Multiple System vMachines with name {} found, check your model'.format(hostname))

        # Select/Create host hypervisor node
        pmachine = PMachineList.get_by_ip(Configuration.get('ovs.host.ip'))
        if pmachine is None:
            pmachine = PMachine()

        # Model system VMachine and Hypervisor node
        pmachine.ip = Configuration.get('ovs.host.ip')
        pmachine.username = Configuration.get('ovs.host.login')
        pmachine.password = Configuration.get('ovs.host.password')
        pmachine.hvtype = Configuration.get('ovs.host.hypervisor')
        pmachine.name = Configuration.get('ovs.host.name')
        pmachine.save()
        vmachine.name = hostname
        vmachine.machineid = Configuration.get('ovs.core.uniqueid')
        vmachine.is_vtemplate = False
        vmachine.is_internal = True
        vmachine.ip = Configuration.get('ovs.grid.ip')
        vmachine.pmachine = pmachine
        vmachine.save()

        # @todo sync version number from master node
        if master is None:
            from ovs.extensions.migration.migration import Migration
            Migration.migrate()

        return vmachine.guid

    @staticmethod
    def init_rabbitmq(cluster_to_join=None):
        """
        Reconfigure rabbitmq to work with ovs user.
        """
        if cluster_to_join:
            os.system('rabbitmq-server -detached; rabbitmqctl stop_app; rabbitmqctl reset; rabbitmqctl join_cluster rabbit@{}; rabbitmqctl stop;'.format(cluster_to_join))
        else:
            os.system('rabbitmq-server -detached; rabbitmqctl stop_app; rabbitmqctl reset; rabbitmqctl stop;')

    @staticmethod
    def init_nginx():
        """
        Init nginx
        """
        import re
        # Update nginx configuration to not run in daemon mode
        nginx_file_handle = open('/etc/nginx/nginx.conf', 'r+a')
        nginx_content = nginx_file_handle.readlines()
        daemon_off = False
        for line in nginx_content:
            if re.match('^daemon off.*', line):
                daemon_off = True
                break
        if not daemon_off:
            nginx_file_handle.write('daemon off;')
        nginx_file_handle.close()
        # Remove nginx default config
        if os.path.exists('/etc/nginx/sites-enabled/default'):
            os.remove('/etc/nginx/sites-enabled/default')

    @staticmethod
    def _check_ceph():
        ceph_config_dir = os.path.join(os.sep, 'etc', 'ceph')
        if not os.path.exists(ceph_config_dir) or \
           not os.path.exists(os.path.join(ceph_config_dir, 'ceph.conf')) or \
           not os.path.exists(os.path.join(ceph_config_dir, 'ceph.keyring')):
            return False
        os.chmod(os.path.join(ceph_config_dir, 'ceph.keyring'), 0644)
        return True

    @staticmethod
    def init_storagerouter(vmachineguid, vpool_name):
        """
        Initializes the volume storage router.
        This requires the OVS model to be configured and reachable
        @param vmachineguid: guid of the internal VSA machine hosting this volume storage router
        """
        mountpoints = [Configuration.get('volumedriver.metadata'), ]
        for path in mountpoints:
            if not os.path.exists(path) or not os.path.ismount(path):
                raise ValueError('Path to {} does not exist or is not a mountpoint'.format(path))
        try:
            output = subprocess.check_output(['mount', '-v']).splitlines()
        except subprocess.CalledProcessError:
            output = []
        all_mounts = map(lambda m: m.split()[2], output)
        mount_regex = re.compile('^/$|/dev|/sys|/run|/proc|{}|{}'.format(
            Configuration.get('ovs.core.db.mountpoint'),
            Configuration.get('volumedriver.metadata')
        ))
        filesystems = filter(lambda d: not mount_regex.match(d), all_mounts)
        volumedriver_cache_mountpoint = Configuration.get('volumedriver.cache.mountpoint', checkExists=True)
        if not volumedriver_cache_mountpoint:
            volumedriver_cache_mountpoint = Console.askChoice(filesystems, 'Select cache mountpoint')
        filesystems.remove(volumedriver_cache_mountpoint)
        cache_fs = os.statvfs(volumedriver_cache_mountpoint)
        scocache = "{}/sco_{}".format(volumedriver_cache_mountpoint, vpool_name)
        readcache = "{}/read_{}".format(volumedriver_cache_mountpoint, vpool_name)
        failovercache = "{}/foc_{}".format(volumedriver_cache_mountpoint, vpool_name)
        metadatapath = "{}/metadata_{}".format(Configuration.get('volumedriver.metadata'), vpool_name)
        tlogpath = "{}/tlogs_{}".format(Configuration.get('volumedriver.metadata'), vpool_name)
        dirs2create = [scocache,
                       failovercache,
                       Configuration.get('volumedriver.readcache.serialization.path'),
                       metadatapath,
                       tlogpath]
        files2create = [readcache]
        # Cache sizes
        # 20% = scocache
        # 20% = failovercache (@todo: check if this can possibly consume more then 20%)
        # 60% = readcache
        scocache_size = "{0}KiB".format((int(cache_fs.f_bavail * 0.2 / 4096) * 4096) * 4)
        readcache_size = "{0}KiB".format((int(cache_fs.f_bavail * 0.6 / 4096) * 4096) * 4)
        supported_backends = Configuration.get('volumedriver.supported.backends').split(',')
        if 'REST' in supported_backends:
            supported_backends.remove('REST')  # REST is not supported for now
        volumedriver_backend_type = Configuration.get('volumedriver.backend.type', checkExists=True)
        if not volumedriver_backend_type:
            volumedriver_backend_type = Console.askChoice(supported_backends, 'Select type of storage backend')
        machine_id = sorted(subprocess.check_output("ip a | grep link/ether | sed 's/\s\s*/ /g' | cut -d ' ' -f 3 | sed 's/://g'", shell=True).strip().split('\n'))[0]
        vrouter_id = '{}{}'.format(vpool_name, machine_id)
        connection_host = Configuration.get('volumedriver.connection.host', checkExists=True)
        connection_port = Configuration.get('volumedriver.connection.port', checkExists=True)
        connection_username = Configuration.get('volumedriver.connection.username', checkExists=True)
        connection_password = Configuration.get('volumedriver.connection.password', checkExists=True)
        rest_connection_timeout_secs = Configuration.get('volumedriver.rest.timeout', checkExists=True)
        volumedriver_local_filesystem = Configuration.get('volumedriver.backend.mountpoint', checkExists=True)
        distributed_filesystem_mountpoint = Configuration.get('volumedriver.filesystem.distributed', checkExists=True)
        volumedriver_storageip = Configuration.get('volumedriver.ip.storage', checkExists=True)
        if not volumedriver_storageip:
            ipaddresses = Net.getIpAddresses()
            grid_ip = Configuration.get('ovs.grid.ip')
            if grid_ip in ipaddresses:
                ipaddresses.remove(grid_ip)
            if '127.0.0.1' in ipaddresses:
                ipaddresses.remove('127.0.0.1')
            if not ipaddresses:
                raise RuntimeError('No available ip addresses found suitable for volumerouter storage ip')
            volumedriver_storageip = Console.askChoice(ipaddresses, 'Select storage ip address for this vpool')
            openvstorage_core_hrd = Configuration.getHRD(os.path.join(Configuration.get('jumpscale.paths.base'), 'cfg', 'hrd', 'openvstorage-core.hrd'))
            openvstorage_core_hrd.set('volumedriver.ip.storage', volumedriver_storageip)
        backend_config = {}
        if volumedriver_backend_type == 'LOCAL':
            if not volumedriver_local_filesystem:
                volumedriver_local_filesystem = Console.askChoice(filesystems, 'Select mountpoint for local backend')
            backend_config = {'local_connection_path': volumedriver_local_filesystem}
        elif volumedriver_backend_type == 'REST':
            if not connection_host:
                connection_host = Console.askString('Provide REST ip address')
            if not connection_port:
                connection_port = Console.askInteger('Provide REST connection port')
            if not rest_connection_timeout_secs:
                rest_connection_timeout_secs = Console.askInteger('Provide desired REST connection timeout(secs)')
            backend_config = {'rest_connection_host': connection_host,
                              'rest_connection_port': connection_port,
                              'buchla_connection_log_level': "0",
                              'rest_connection_verbose_logging': rest_connection_timeout_secs,
                              'rest_connection_metadata_format': "JSON"}
        elif volumedriver_backend_type == 'S3':
            if not connection_host:
                connection_host = Console.askString('Specify fqdn or ip address for your S3 compatible host')
            if not connection_port:
                connection_port = Console.askInteger('Specify port for your S3 compatible host')
            if not connection_username:
                connection_username = Console.askString('Specify S3 access key')
            if not connection_password:
                connection_password = Console.askString('Specify S3 secret key')
            backend_config = {'s3_connection_host': connection_host,
                              's3_connection_port': connection_port,
                              's3_connection_username': connection_username,
                              's3_connection_password': connection_password,
                              's3_connection_verbose_logging': 1}
            #Create local backend filesystem
            if distributed_filesystem_mountpoint in filesystems:
                subprocess.call(['umount', distributed_filesystem_mountpoint])
            ceph_ok = Configure()._check_ceph()
            if not ceph_ok:
                print boxed_message(['No or incomplete configuration files found for your Ceph S3 compatible storage backend',
                                     'Now is the time to copy following files',
                                     ' CEPH_SERVER:/etc/ceph/ceph.conf -> /etc/ceph/ceph.conf',
                                     ' CEPH_SERVER:/etc/ceph/ceph.client.admin.keyring -> /etc/ceph/ceph.keyring',
                                     'to make sure we can connect our ceph filesystem',
                                     'When done continue the initialization here'])
                ceph_continue = Console.askYesNo('Continue initialization')
                if not ceph_continue:
                    raise RuntimeError("Exiting initialization")
                ceph_ok = Configure()._check_ceph()
                if not ceph_ok:
                    raise RuntimeError("Ceph config still not ok, exiting initialization")
            #subprocess.call(['ceph-fuse', '-m', '{}:6789'.format(connection_host), distributed_filesystem_mountpoint])
            fstab = Fstab()
            fstab.removeConfigByDirectory(distributed_filesystem_mountpoint)
            fstab.addConfig('id=admin,conf=/etc/ceph/ceph.conf', distributed_filesystem_mountpoint, 'fuse.ceph', 'defaults,noatime', '0', '2')
            subprocess.call(['mount', distributed_filesystem_mountpoint])
        backend_config.update({'backend_type': volumedriver_backend_type})
        vsr_configuration = VolumeStorageRouterConfiguration(vpool_name)
        vsr_configuration.configure_backend(backend_config)

        readcaches = [{'path': readcache, 'size': readcache_size}, ]
        vsr_configuration.configure_readcache(readcaches, Configuration.get('volumedriver.readcache.serialization.path'))

        scocaches = [{'path': scocache, 'size': scocache_size}, ]
        vsr_configuration.configure_scocache(scocaches, "1GB", "2GB")

        vsr_configuration.configure_failovercache(failovercache)

        filesystem_config = {'fs_backend_path': Configuration.get('volumedriver.filesystem.distributed')}
        vsr_configuration.configure_filesystem(filesystem_config)

        volumemanager_config = {'metadata_path': metadatapath, 'tlog_path': tlogpath}
        vsr_configuration.configure_volumemanager(volumemanager_config)

        vpools = VPoolList.get_vpool_by_name(vpool_name)
        this_vpool = VPool()
        if vpools and len(vpools) == 1:
            this_vpool = vpools[0]
        this_vpool.name = vpool_name
        this_vpool.description = "{} {}".format(volumedriver_backend_type, vpool_name)
        this_vpool.backend_type = volumedriver_backend_type
        if not connection_host:
            this_vpool.backend_connection = None
            this_vpool.backend_login = None
            this_vpool.backend_password = None
        else:
            this_vpool.backend_connection = '{}:{}'.format(connection_host, connection_port)
            this_vpool.backend_login = connection_username
            this_vpool.backend_password = connection_password
        this_vpool.save()
        vrouters = filter(lambda v: v.vsrid == vrouter_id, this_vpool.vsrs)

        if vrouters:
            vrouter = vrouters[0]
        else:
            vrouter = VolumeStorageRouter()
        # Make sure port is not already used
        from ovs.dal.lists.volumestoragerouterlist import VolumeStorageRouterList
        ports_used_in_model = [vsr.port for vsr in VolumeStorageRouterList.get_volumestoragerouters_by_vsa(vmachineguid)]
        vrouter_port_in_hrd = int(Configuration.get('volumedriver.filesystem.xmlrpc.port'))
        if vrouter_port_in_hrd in ports_used_in_model:
            vrouter_port = Console.askInteger('Provide Volumedriver connection port (make sure port is not in use)', max(ports_used_in_model) + 3)
        else:
            vrouter_port = vrouter_port_in_hrd  # Default
        this_vmachine = VMachine(vmachineguid)
        vrouter.name = vrouter_id.replace('_', ' ')
        vrouter.description = vrouter.name
        vrouter.vsrid = vrouter_id
        vrouter.storage_ip = volumedriver_storageip
        vrouter.cluster_ip = Configuration.get('ovs.grid.ip')
        vrouter.port = vrouter_port
        vrouter.mountpoint = os.path.join(os.sep, 'mnt', vpool_name)
        vrouter.serving_vmachine = this_vmachine
        vrouter.vpool = this_vpool
        vrouter.save()
        dirs2create.append(vrouter.mountpoint)

        vrouter_config = {"vrouter_id": vrouter_id,
                          "vrouter_redirect_timeout_ms": "5000",
                          "vrouter_migrate_timeout_ms" : "5000",
                          "vrouter_write_threshold" : 1024,
                          "host": vrouter.cluster_ip,
                          "xmlrpc_port": vrouter.port}
        vsr_configuration.configure_volumerouter(vpool_name, vrouter_config)

        voldrv_arakoon_cluster_id = Configuration.get('volumedriver.arakoon.clusterid')
        voldrv_arakoon_cluster = ArakoonManagement().getCluster(voldrv_arakoon_cluster_id)
        voldrv_arakoon_client_config = voldrv_arakoon_cluster.getClientConfig()
        vsr_configuration.configure_arakoon_cluster(voldrv_arakoon_cluster_id, voldrv_arakoon_client_config)

        queue_config = {"events_amqp_routing_key": Configuration.get('ovs.core.broker.volumerouter.queue'),
                        "events_amqp_uri": "{}://{}:{}@{}:{}".format(Configuration.get('ovs.core.broker.protocol'),
                                                                     Configuration.get('ovs.core.broker.login'),
                                                                     Configuration.get('ovs.core.broker.password'),
                                                                     Configuration.get('ovs.grid.ip'),
                                                                     Configuration.get('ovs.core.broker.port'))}
        vsr_configuration.configure_event_publisher(queue_config)

        for directory in dirs2create:
            if not os.path.exists(directory):
                os.makedirs(directory)
        for filename in files2create:
            if not os.path.exists(filename):
                open(filename, 'a').close()

        config_file = os.path.join(Configuration.get('ovs.core.cfgdir'), '{}.json'.format(vpool_name))
        log_file = os.path.join(os.sep, 'var', 'log', '{}.log'.format(vpool_name))
        cmd = '/usr/bin/volumedriver_fs -f --config-file={} --mountpoint {} --logfile {} -o big_writes -o uid=0 -o gid=0 -o sync_read'.format(config_file, vrouter.mountpoint, log_file)
        stopcmd = 'exportfs -u *:{0}; umount {0}'.format(vrouter.mountpoint)
        name = 'volumedriver_{}'.format(vpool_name)
        Service.add_service(package=('openvstorage', 'volumedriver'), name=name, command=cmd, stop_command=stopcmd)
        #add corresponding failovercache, for each volumedriver
        log_file = os.path.join(os.sep, 'var', 'log', 'foc_{}.log'.format(vpool_name))
        cmd = '/usr/bin/failovercachehelper --config-file={} --logfile={}'.format(config_file, log_file)
        name = 'failovercache_{}'.format(vpool_name)
        Service.add_service(package=('openvstorage', 'volumedriver'), name=name, command=cmd, stop_command=None)

class Control():
    """
    OVS Control class enabling you to
    * init
    * start
    * stop
    all components at once
    """

    def __init__(self):
        """
        Init class
        """
        pass

    def init(self, vpool_name, services=['openvstorage-core', 'openvstorage-webapps', 'volumedriver'], master=None):
        """
        Configure & Start the OVS components in the correct order to get your environment initialized after install
        * Reset rabbitmq
        * Remove nginx file /etc/nginx/sites-enabled/default configuration
        * Load default data into model
        * Configure volume storage router
        """
        while not re.match('^[0-9a-zA-Z]+([\-_]+[0-9a-zA-Z]+)*$', vpool_name):
            print 'Invalid vPool name given. Only 0-9, a-z, A-Z, _ and - are allowed.'
            suggestion = re.sub(
                '^([\-_]*)(?P<correct>[0-9a-zA-Z]+([\-_]+[0-9a-zA-Z]+)*)([\-_]*)$',
                '\g<correct>',
                re.sub('[^0-9a-zA-Z\-_]', '_', vpool_name)
            )
            vpool_name = Console.askString('Provide new vPool name', defaultparam=suggestion)

        def _init_core():
            if not self._package_is_running('openvstorage-core'):
                arakoon_dir = os.path.join(Configuration.get('ovs.core.cfgdir'), 'arakoon')
                arakoon_clusters = map(lambda d: os.path.basename(d), os.walk(arakoon_dir).next()[1])
                for cluster in arakoon_clusters:
                    cluster_instance = ArakoonManagement().getCluster(cluster)
                    cluster_instance.createDirs(cluster_instance.listLocalNodes()[0])
                Configure.init_rabbitmq(master)
                time.sleep(5)
                self._start_package('openvstorage-core')

        def _init_webapps():
            if not self._package_is_running('openvstorage-webapps'):
                Configure.init_nginx()
                self._start_package('openvstorage-webapps')

        def _init_volumedriver():
            vmachineguid = Configure.load_data(master)
            Configure.init_storagerouter(vmachineguid, vpool_name)
            if not self._package_is_running('volumedriver'):
                self._start_package('volumedriver')
            vfs_info = os.statvfs('/mnt/{}'.format(vpool_name))
            vpool_size_bytes = vfs_info.f_blocks * vfs_info.f_bsize
            vpools = VPoolList.get_vpool_by_name(vpool_name)
            if len(vpools) != 1:
                raise ValueError('No or multiple vpools found with name {}, should not happen at this stage, please check your configuration'.format(vpool_name))
            this_vpool = vpools[0]
            this_vpool.size = vpool_size_bytes
            this_vpool.save()
            Configure.init_exportfs(vpool_name)

            mount_vpool = Configuration.get('volumedriver.vpool.mount', checkExists=True)
            if not mount_vpool:
                mount_vpool = Console.askYesNo('Do you want to mount the vPool?')
            if mount_vpool is True:
                print '  Please wait while the vPool is mounted...'
                vmachine = VMachine(vmachineguid)
                vrouter = [vsr for vsr in this_vpool.vsrs if vsr.serving_vmachine_guid == vmachineguid][0]
                hypervisor = Factory.get(vmachine.pmachine)
                try:
                    hypervisor.mount_nfs_datastore(vpool_name, vrouter.storage_ip, vrouter.mountpoint)
                    print '  Success'
                except Exception as ex:
                    print '  Error, please mount the vPool manually. {0}'.format(str(ex))

        if 'openvstorage-core' in services:
            _init_core()
        if 'openvstorage-webapps' in services:
            _init_webapps()
        if 'volumedriver' in services:
            _init_volumedriver()
            subprocess.call(['service', 'processmanager', 'start'])
            # Now that the vsa has been modelled restart ovs workers for correct queues to get defined
            subprocess.call(['jsprocess', 'restart', '-n', 'ovs_workers'])

    def _package_is_running(self, package):
        """
        Checks whether a package is running
        """
        _ = self
        return Package.is_running(namespace='openvstorage', name=package)

    def _start_package(self, package):
        """
        Starts a package
        """
        _ = self
        return Package.start(namespace='openvstorage', name=package)

    def _stop_package(self, package):
        """
        Stops a package
        """
        _ = self
        return Package.stop(namespace='openvstorage', name=package)

    def start(self):
        """
        Starts all packages
        """
        self._start_package('volumedriver')
        self._start_package('openvstorage-core')
        self._start_package('openvstorage-webapps')
        subprocess.call(['service', 'nfs-kernel-server', 'start'])

    def stop(self):
        """
        Stops all packages
        """
        subprocess.call(['service', 'nfs-kernel-server', 'stop'])
        self._stop_package('openvstorage-webapps')
        self._stop_package('openvstorage-core')
        self._stop_package('volumedriver')

    def status(self):
        """
        Gets the status from all packages
        """
        _ = self
        subprocess.call(['service', 'nfs-kernel-server', 'status'])
        Package.get_status(namespace='openvstorage', name='openvstorage-core')
        Package.get_status(namespace='openvstorage', name='openvstorage-webapps')
