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
RelationMapper module
"""
from ovs.dal.helpers import HybridRunner, Descriptor, Toolbox
from ovs.extensions.storage.volatilefactory import VolatileFactory


class RelationMapper(object):
    """
    The RelationMapper is responsible for loading the relational structure
    of the hybrid objects.
    """

    @staticmethod
    def load_foreign_relations(object_type):
        """
        This method will return a mapping of all relations towards a certain hybrid object type.
        The resulting mapping will be stored in volatile storage so it can be fetched faster
        """
        relation_key = 'ovs_relations_{0}'.format(object_type.__name__.lower())
        volatile = VolatileFactory.get_client()
        relation_info = volatile.get(relation_key)
        if relation_info is None:
            Toolbox.log_cache_hit('relations', False)
            relation_info = {}
            hybrid_structure = HybridRunner.get_hybrids()
            for class_descriptor in hybrid_structure.values():  # Extended objects
                cls = Descriptor().load(class_descriptor).get_object()
                for relation in cls._relations:
                    if relation.foreign_type is None:
                        remote_class = cls
                    else:
                        identifier = Descriptor(relation.foreign_type).descriptor['identifier']
                        if identifier in hybrid_structure and identifier != hybrid_structure[identifier]['identifier']:
                            remote_class = Descriptor().load(hybrid_structure[identifier]).get_object()
                        else:
                            remote_class = relation.foreign_type
                    itemname = remote_class.__name__
                    if itemname == object_type.__name__:
                        relation_info[relation.foreign_key] = {'class': Descriptor(cls).descriptor,
                                                               'key': relation.name,
                                                               'list': not relation.onetoone}
            volatile.set(relation_key, relation_info)
        else:
            Toolbox.log_cache_hit('relations', True)
        return relation_info
