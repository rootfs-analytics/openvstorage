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
Mockups module
"""


class StorageRouterClient():
    """
    Mocks the StorageRouterClient
    """

    def __init__(self):
        """
        Dummy init method
        """
        pass

    @staticmethod
    def info(volume_id):
        """
        Return fake info
        """
        _ = volume_id
        return type('Info', (), {})()

    @staticmethod
    def list_snapshots(volume_id):
        """
        Return fake info
        """
        _ = volume_id
        return []


class VolumeStorageRouterClient():
    """
    Mocks the VolumeStorageRouterClient
    """

    def __init__(self):
        """
        Dummy init method
        """
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

    @staticmethod
    def empty_statistics():
        """
        Returns a fake empty object
        """
        vsr = VolumeStorageRouterClient()
        mocked_class = type('Statistics', (), dict((key, 0) for key in vsr.stat_counters))
        for key in vsr.stat_counters:
            setattr(mocked_class, key, property(lambda: 0))
        return mocked_class

    @staticmethod
    def empty_info():
        """
        Returns a fake empty object
        """
        return type('Info', (), {})()

    def load(self):
        """
        Returns the mocked StorageRouterClient
        """
        _ = self
        return StorageRouterClient()


class VolumeStorageRouter():
    """
    Mocks the VolumeStorageRouter
    """
    VolumeStorageRouterClient = VolumeStorageRouterClient

    def __init__(self):
        """
        Dummy init method
        """
        pass


class Loader():
    """
    Mocks loader class
    """

    def __init__(self):
        """
        Dummy init method
        """
        pass

    @staticmethod
    def load(module):
        """
        Always returns 'unittest'
        """
        _ = module
        return 'unittest'


class LoaderModule():
    """
    Mocks dependency loader module
    """

    Loader = Loader

    def __init__(self):
        """
        Dummy init method
        """
        pass


class Hypervisor():
    """
    Mocks a hypervisor client
    """

    def __init__(self):
        """
        Dummy init method
        """
        pass

    def get_state(self, vmid):
        """
        Always returns running
        """
        _ = self, vmid
        return 'RUNNING'


class Factory():
    """
    Mocks hypervisor factory
    """

    def __init__(self):
        """
        Dummy init method
        """
        pass

    @staticmethod
    def get(hypervisor):
        """
        Always returns 'unittest'
        """
        _ = hypervisor
        return


class FactoryModule():
    """
    Mocks hypervisor factory
    """

    Factory = Factory

    def __init__(self):
        """
        Dummy init method
        """
        pass
