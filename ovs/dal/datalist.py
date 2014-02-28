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
DataList module
"""

import hashlib
import json
import copy
from random import randint
from ovs.dal.helpers import Descriptor, Toolbox
from ovs.dal.exceptions import ObjectNotFoundException
from ovs.extensions.storage.volatilefactory import VolatileFactory
from ovs.extensions.storage.persistentfactory import PersistentFactory
from ovs.extensions.generic.volatilemutex import VolatileMutex


class DataList(object):
    """
    The DataList is a class that provide query functionality for the hybrid DAL
    """

    class Select(object):
        """
        The Select class provides enum-alike properties for what to select
        """
        DESCRIPTOR = 'DESCRIPTOR'
        COUNT = 'COUNT'

    class WhereOperator(object):
        """
        The WhereOperator class provides enum-alike properties for the Where-operators
        """
        AND = 'AND'
        OR = 'OR'

    class Operator(object):
        """
        The Operator class provides enum-alike properties for equalitation-operators
        """
        # In case more operators are required, add them here, and implement them in
        # the _evaluate method below
        EQUALS = 'EQUALS'
        NOT_EQUALS = 'NOT_EQUALS'
        LT = 'LT'
        GT = 'GT'
        IN = 'IN'

    select = Select()
    where_operator = WhereOperator()
    operator = Operator()
    namespace = 'ovs_list'
    cachelink = 'ovs_listcache'

    def __init__(self, query, key=None, load=True):
        """
        Initializes a DataList class with a given key (used for optional caching) and a given query
        """
        # Initialize super class
        super(DataList, self).__init__()

        if key is not None:
            self._key = key
        else:
            identifier = copy.deepcopy(query)
            identifier['object'] = identifier['object'].__name__
            self._key = hashlib.sha256(json.dumps(identifier)).hexdigest()
        self._key = '%s_%s' % (DataList.namespace, self._key)
        self._volatile = VolatileFactory.get_client()
        self._persistent = PersistentFactory.get_client()
        self._query = query
        self._invalidation = {}
        self.data = None
        self.from_cache = False
        self._can_cache = True
        if load is True:
            self._load()

    def _exec_and(self, instance, items):
        """
        Executes a given set of query items against the instance in an "AND" scope
        This means the first False will cause the scope to return False
        """
        for item in items:
            if isinstance(item, dict):
                # Recursive
                if item['type'] == DataList.where_operator.AND:
                    result = self._exec_and(instance, item['items'])
                else:
                    result = self._exec_or(instance, item['items'])
                if result is False:
                    return False
            else:
                if self._evaluate(instance, item) is False:
                    return False
        return True

    def _exec_or(self, instance, items):
        """
        Executes a given set of query items against the instance in an "OR" scope
        This means the first True will cause the scope to return True
        """
        for item in items:
            if isinstance(item, dict):
                # Recursive
                if item['type'] == DataList.where_operator.AND:
                    result = self._exec_and(instance, item['items'])
                else:
                    result = self._exec_or(instance, item['items'])
                if result is True:
                    return True
            else:
                if self._evaluate(instance, item) is True:
                    return True
        return False

    def _evaluate(self, instance, item):
        """
        Evaluates a single query item comparing a given value with a given instance property
        It will keep track of which properties are used, making sure the query result
        will get invalidated when such property is updated
        """
        path = item[0].split('.')
        value = instance
        if value is None:
            return False
        itemcounter = 0
        for pitem in path:
            itemcounter += 1
            if pitem in value.__class__._expiry:
                self._can_cache = False
            self._add_invalidation(value.__class__.__name__.lower(), pitem)
            target_class = value._relations.get(pitem, None)
            value = getattr(value, pitem)
            if value is None and itemcounter != len(path):
                # We loaded a None in the middle of our path
                if target_class is not None:
                    if target_class[0] is None:
                        classname = value.__class__.__name__.lower()
                    else:
                        classname = target_class[0].__name__.lower()
                    self._add_invalidation(classname, path[itemcounter])
                return False  # Fail the filter

        # Apply operators
        if item[1] == DataList.operator.NOT_EQUALS:
            return value != item[2]
        if item[1] == DataList.operator.EQUALS:
            return value == item[2]
        if item[1] == DataList.operator.GT:
            return value > item[2]
        if item[1] == DataList.operator.LT:
            return value < item[2]
        if item[1] == DataList.operator.IN:
            return value in item[2]
        raise NotImplementedError('The given operator {} is not yet implemented.'.format(item[1]))

    def _load(self):
        """
        Tries to load the result for the given key from the volatile cache, or executes the query
        if not yet available. Afterwards (if a key is given), the result will be (re)cached
        """
        self.data = self._volatile.get(self._key) if self._key is not None else None
        if self.data is None:
            # The query should be a dictionary:
            #     {'object': Disk,  # Object on which the query should be executed
            #      'data'  : DataList.select.XYZ,  # The requested result
            #      'query' : <query>}  # The actual query
            # Where <query> is a query(group) dictionary:
            #     {'type' : DataList.where_operator.ABC,  # Whether the items should be AND/OR
            #      'items': <items>}  # The items in the group
            # Where the <items> is any combination of one or more <filter> or <query>
            # A <filter> tuple example:
            #     (<field>, DataList.operator.GHI, <value>)  # For example EQUALS
            # The field is any property you would also find on the given object. In case of
            # properties, you can dot as far as you like. This means you can combine AND and OR
            # in any possible combination

            Toolbox.log_cache_hit('datalist', False)

            items = self._query['query']['items']
            query_type = self._query['query']['type']
            query_data = self._query['data']
            query_object = self._query['object']

            self.from_cache = False
            namespace = query_object()._namespace
            name = query_object.__name__.lower()
            base_key = '%s_%s_' % (namespace, name)
            keys = DataList.get_pks(namespace, name)

            if query_data == DataList.select.COUNT:
                self.data = 0
            else:
                self.data = []

            self._add_invalidation(name, '__all')
            for key in keys:
                guid = key.replace(base_key, '')
                try:
                    instance = query_object(guid)
                    if query_type == DataList.where_operator.AND:
                        include = self._exec_and(instance, items)
                    elif query_type == DataList.where_operator.OR:
                        include = self._exec_or(instance, items)
                    else:
                        raise NotImplementedError('The given operator is not yet implemented.')
                    if include:
                        if query_data == DataList.select.COUNT:
                            self.data += 1
                        elif query_data == DataList.select.DESCRIPTOR:
                            self.data.append(Descriptor(query_object, guid).descriptor)
                        else:
                            raise NotImplementedError('The given selector type is not implemented')
                except ObjectNotFoundException:
                    pass

            if self._key is not None and len(keys) > 0 and self._can_cache:
                self._volatile.set(self._key, self.data, 300 + randint(0, 300))  # Cache between 5 and 10 minutes
                self._update_listinvalidation()
        else:
            Toolbox.log_cache_hit('datalist', True)
            self.from_cache = True
        return self

    def _add_invalidation(self, object_name, field):
        """
        This method adds an invalidation to an internal list that will be saved when the
        query is completed
        """
        field_list = self._invalidation.get(object_name, [])
        field_list.append(field)
        self._invalidation[object_name] = field_list

    def _update_listinvalidation(self):
        """
        This method will save the list invalidation mapping to volatile and persistent storage
        """
        if self._key is not None:
            for object_name, field_list in self._invalidation.iteritems():
                key = '%s_%s' % (DataList.cachelink, object_name)
                mutex = VolatileMutex('listcache_%s' % object_name)
                try:
                    mutex.acquire(60)
                    cache_list = Toolbox.try_get(key, {})
                    current_fields = cache_list.get(self._key, [])
                    current_fields = list(set(current_fields + field_list))
                    cache_list[self._key] = current_fields
                    self._volatile.set(key, cache_list)
                    self._persistent.set(key, cache_list)
                finally:
                        mutex.release()

    @staticmethod
    def get_relation_set(remote_class, remote_key, own_class, own_key, own_guid):
        """
        This method will get a DataList for a relation.
        On a cache miss, the relation DataList will be rebuild and due to the nature of the full table scan, it will
        update all relations in the mean time.
        """
        own_name = own_class.__name__.lower()
        datalist = DataList({}, '%s_%s_%s' % (own_name, own_guid, remote_key), load=False)
        base_key = '%s_%s_%%s_%s' % (DataList.namespace, own_name, own_key)  # <ns>_<oc>_%s_<rk>

        data = datalist._volatile.get(base_key % own_guid)
        if data is None:
            # Cache miss
            Toolbox.log_cache_hit('datalist', False)

            remote_namespace = remote_class()._namespace
            remote_name = remote_class.__name__.lower()
            remote_base_key = '%s_%s_' % (remote_namespace, remote_name)
            remote_keys = DataList.get_pks(remote_namespace, remote_name)

            own_namespace = own_class()._namespace
            own_base_key = '%s_%s_' % (own_namespace, own_name)
            own_keys = DataList.get_pks(own_namespace, own_name)

            lists = {}
            for key in own_keys:
                guid = key.replace(own_base_key, '')
                lists[guid] = []
            if own_guid not in lists:
                lists[own_guid] = []

            for key in remote_keys:
                guid = key.replace(remote_base_key, '')
                try:
                    instance = remote_class(guid)
                    foreign_key = getattr(instance, '%s_guid' % remote_key)
                    if foreign_key not in lists:
                        lists[foreign_key] = []
                    lists[foreign_key].append(Descriptor(remote_class, guid).descriptor)
                except ObjectNotFoundException:
                    pass

            list_keys = []
            for guid in lists:
                list_keys.append(base_key % guid)
                datalist._volatile.set(base_key % guid, lists[guid], 300 + randint(0, 300))  # Cache between 5 and 10 minutes

            key = '%s_%s' % (DataList.cachelink, remote_name)
            mutex = VolatileMutex('listcache_%s' % remote_name)
            try:
                mutex.acquire(60)
                cache_list = Toolbox.try_get(key, {})
                for list_key in list_keys:
                    current_fields = cache_list.get(list_key, [])
                    current_fields = list(set(current_fields + ['__all', remote_key]))
                    cache_list[list_key] = current_fields
                datalist._volatile.set(key, cache_list)
                datalist._persistent.set(key, cache_list)
            finally:
                mutex.release()

            datalist.data = lists.get(own_guid)
            datalist._update_listinvalidation()
        else:
            Toolbox.log_cache_hit('datalist', True)
            datalist.data = data
            datalist.from_cache = True
        return datalist

    @staticmethod
    def get_pks(namespace, name):
        """
        This method will load the primary keys for a given namespace and name
        (typically, for ovs_data_*)
        """
        return DataList._get_pks(namespace, name)

    @staticmethod
    def add_pk(namespace, name, key):
        """
        This adds the current primary key to the primary key index
        """
        mutex = VolatileMutex('primarykeys_%s' % name)
        try:
            mutex.acquire(10)
            keys = DataList._get_pks(namespace, name)
            keys.add(key)
            DataList._save_pks(name, keys)
        finally:
            mutex.release()

    @staticmethod
    def delete_pk(namespace, name, key):
        """
        This deletes the current primary key from the primary key index
        """
        mutex = VolatileMutex('primarykeys_%s' % name)
        try:
            mutex.acquire(10)
            keys = DataList._get_pks(namespace, name)
            try:
                keys.remove(key)
            except KeyError:
                pass
            DataList._save_pks(name, keys)
        finally:
            mutex.release()

    @staticmethod
    def _get_pks(namespace, name):
        """
        Loads the primary key set information and pages, merges them to a single set
        and returns it
        """
        internal_key = 'ovs_primarykeys_%s' % name
        volatile = VolatileFactory.get_client()
        persistent = PersistentFactory.get_client()
        keys = set()
        key_sets = volatile.get(internal_key)
        if key_sets is None:
            return set(persistent.prefix('%s_%s_' % (namespace, name)))
        for key_set in key_sets:
            subset = volatile.get('%s_%d' % (internal_key, key_set))
            if subset is None:
                return set(persistent.prefix('%s_%s_' % (namespace, name)))
            else:
                keys = keys.union(subset)
        return keys

    @staticmethod
    def _save_pks(name, keys):
        """
        Pages and saves a set
        """
        internal_key = 'ovs_primarykeys_%s' % name
        volatile = VolatileFactory.get_client()
        keys = list(keys)
        old_key_sets = volatile.get(internal_key) or []
        key_sets = []
        for i in range(0, len(keys), 5000):
            volatile.set('%s_%d' % (internal_key, i), keys[i:i + 5000])
            key_sets.append(i)
        for key_set in old_key_sets:
            if key_set not in key_sets:
                volatile.delete('%s_%d' % (internal_key, key_set))
        volatile.set(internal_key, key_sets)
