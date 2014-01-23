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
Module for the VMware hypervisor client
"""

from ovs.extensions.hypervisor.hypervisor import Hypervisor
from ovs.extensions.hypervisor.apis.vmware.sdk import Sdk


class VMware(Hypervisor):

    """
    Represents the hypervisor client for VMware
    """

    def __init__(self, ip, username, password):
        """
        Initializes the object with credentials and connection information
        """
        super(VMware, self).__init__(ip, username, password)
        self.sdk = Sdk(self._ip, self._username, self._password)
        self.STATE_MAPPING = {'poweredOn' : 'RUNNING',
                              'poweredOff': 'HALTED',
                              'suspended' : 'PAUSED'}

    def _connect(self):
        """
        Dummy connect implementation, SDK handles connection internally
        """
        return True

    @Hypervisor.connected
    def get_state(self, vmid):
        """
        Get the current power state of a virtual machine
        @param vmid: hypervisor id of the virtual machine
        """
        return self.STATE_MAPPING[self.sdk.get_power_state(vmid)]

    @Hypervisor.connected
    def create_vm(self, *args, **kwargs):
        """
        Configure the vmachine on the hypervisor
        """
        pass

    @Hypervisor.connected
    def create_vm_from_template(self, name, source_vm, disks, esxhost=None, wait=True):
        """
        Create a new vmachine from an existing template
        @param name:
        @param template_vm: template object to create new vmachine from
        @param target_pm: hypervisor object to create new vmachine on
        @return: celery task
        """
        task = self.sdk.create_vm_from_template(name, source_vm, disks, esxhost, wait)
        if wait is True:
            if self.sdk.validate_result(task):
                task_info = self.sdk.get_task_info(task)
                return task_info.info.result.value
        return None

    @Hypervisor.connected
    def clone_vm(self, vmid, name, disks, esxhost=None, wait=False):
        """
        Clone a vmachine

        @param vmid: hypervisor id of the virtual machine
        @param name: name of the virtual machine
        @param disks: list of disk information
        @param esxhost: esx host identifier
        @param wait: wait for action to complete
        """
        task = self.sdk.clone_vm(vmid, name, disks, esxhost, wait)
        if wait is True:
            if self.sdk.validate_result(task):
                task_info = self.sdk.get_task_info(task)
                return task_info.info.result.value
        return None

    @Hypervisor.connected
    def delete_vm(self, vmid, esxhost=None, wait=False):
        """
        Remove the vmachine from the hypervisor

        @param vmid: hypervisor id of the virtual machine
        @param esxhost: esx host identifier
        @param wait: wait for action to complete
        """
        if vmid and self.sdk.exists(key=vmid):
            self.sdk.delete_vm(vmid, wait)

    @Hypervisor.connected
    def get_vm_object(self, vmid):
        """
        Gets the VMware virtual machine object from VMware by its identifier
        """

        return self.sdk.get_vm(vmid)

    @Hypervisor.connected
    def get_vm_agnostic_object(self, vmid):
        """
        Gets the VMware virtual machine object from VMware by its identifier
        """

        return self.sdk.make_agnostic_config(self.sdk.get_vm(vmid))

    @Hypervisor.connected
    def get_vm_object_by_devicename(self, devicename, ip, mountpoint):
        """
        Gets the VMware virtual machine object from VMware by devicename
        and datastore identifiers
        """
        return self.sdk.make_agnostic_config(self.sdk.get_nfs_datastore_object(ip, mountpoint, devicename)[0])

    @Hypervisor.connected
    def is_datastore_available(self, ip, mountpoint, esxhost=None):
        """
        @param ip : hypervisor ip to query for datastore presence
        @param mountpoint: nfs mountpoint on hypervisor
        @rtype: boolean
        @return: True | False
        """
        return self.sdk.is_datastore_available(ip, mountpoint, esxhost)

    @Hypervisor.connected
    def set_as_template(self, vmid, disks, esxhost=None, wait=False):
        """
        Configure a vm as template
        This lets the machine exist on the hypervisor but configures
        all disks as "Independent Non-persistent"

        @param vmid: hypervisor id of the virtual machine
        """
        return self.sdk.set_disk_mode(vmid, disks, 'independent_nonpersistent', esxhost, wait)

    @Hypervisor.connected
    def mount_nfs_datastore(self, name, remote_host, remote_path):
        """
        Mounts a given NFS export as a datastore
        """
        return self.sdk.mount_nfs_datastore(name, remote_host, remote_path)

