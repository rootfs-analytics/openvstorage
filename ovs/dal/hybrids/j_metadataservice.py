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
MetadataService module
"""
from ovs.dal.dataobject import DataObject
from ovs.dal.structures import Property, Relation
from ovs.dal.hybrids.vdisk import VDisk
from ovs.dal.hybrids.service import Service


class MetadataService(DataObject):
    """
    The MetadataService class represents the junction table between the (metadata)Service and VDisk.
    Examples:
    * my_vdisk.metadata_services[0].service
    * my_metadata_service.vdisks[0].vdisk
    """
    __properties = [Property('is_master', bool, default=False, doc='Is this the master MetadataService for this VDisk.')]
    __relations = [Relation('vdisk', VDisk, 'metadata_services'),
                   Relation('service', Service, 'vdisks')]
    __dynamics = []
