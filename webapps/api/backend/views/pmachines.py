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
PMachine module
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ovs.dal.lists.pmachinelist import PMachineList
from ovs.dal.hybrids.pmachine import PMachine
from backend.decorators import required_roles, expose, validate, get_object, get_list


class PMachineViewSet(viewsets.ViewSet):
    """
    Information about pMachines
    """
    permission_classes = (IsAuthenticated,)

    @expose(internal=True)
    @required_roles(['view'])
    @get_list(PMachine)
    def list(self, request, format=None, hints=None):
        """
        Overview of all pMachines
        """
        _ = request, format, hints
        return PMachineList.get_pmachines()

    @expose(internal=True)
    @required_roles(['view'])
    @validate(PMachine)
    @get_object(PMachine)
    def retrieve(self, request, obj):
        """
        Load information about a given pMachine
        """
        _ = request
        return obj
