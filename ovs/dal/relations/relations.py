"""
RelationMapper module
"""
from ovs.dal.storedobject import StoredObject
from ovs.dal.helpers import HybridRunner, Descriptor


class RelationMapper(StoredObject):
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
        relation_key = 'ovs_relations_%s' % object_type.__name__.lower()
        relation_info = StoredObject.volatile.get(relation_key)
        if relation_info is None:
            relation_info = {}
            for cls in HybridRunner.get_hybrids():
                for key, item in cls._relations.iteritems():
                    if item[0].__name__ == object_type.__name__:
                        relation_info[item[1]] = {'class': Descriptor(cls).descriptor,
                                                  'key': key}
            StoredObject.volatile.set(relation_key, relation_info)
        return relation_info
