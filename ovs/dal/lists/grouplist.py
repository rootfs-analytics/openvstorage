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
GroupList module
"""
from ovs.dal.datalist import DataList
from ovs.dal.dataobject import DataObjectList
from ovs.dal.hybrids.group import Group


class GroupList(object):
    """
    This GroupList class contains various lists regarding to the Group class
    """

    @staticmethod
    def get_groups():
        """
        Returns a list of all Groups
        """
        groups = DataList({'object': Group,
                           'data': DataList.select.GUIDS,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': []}}).data
        return DataObjectList(groups, Group)
