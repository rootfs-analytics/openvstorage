from storedobject import StoredObject
from helpers import Descriptor, Toolbox
from exceptions import ObjectNotFoundException


class DataList(StoredObject):
    class Select(object):
        DESCRIPTOR = 'DESCRIPTOR'
        COUNT      = 'COUNT'

    class WhereOperator(object):
        AND = 'AND'
        OR  = 'OR'

    class Operator(object):
        # In case more operators are required, add them here, and implement them in
        # the _evaluate method below
        EQUALS    = 'EQUALS'
        LT        = 'LT'
        GT        = 'GT'

    select = Select()
    where_operator = WhereOperator()
    operator = Operator()
    namespace = 'ovs_list'
    cachelink = 'ovs_listcache'

    def __init__(self, key, query):
        # Initialize super class
        super(DataList, self).__init__()

        self._key = None if key is None else ('%s_%s' % (DataList.namespace, key))
        self._query = query
        self._invalidation = {}
        self.data = None
        self.from_cache = False
        self._load()

    @staticmethod
    def get_pks(namespace, name):
        key = 'ovs_primarykeys_%s' % name
        keys = StoredObject.volatile.get(key)
        if keys is None:
            keys = StoredObject.persistent.prefix('%s_%s_' % (namespace, name))
        return keys

    def _exec_and(self, instance, items):
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
        path = item[0].split('.')
        value = instance
        if value is None:
            return False
        itemcounter = 0
        for pitem in path:
            itemcounter += 1
            self._add_invalidation(value.__class__.__name__.lower(), pitem)
            target_class = value._relations.get(pitem, None)
            value = getattr(value, pitem)
            if value is None and itemcounter != len(path):
                # We loaded a None in the middle of our path
                if target_class is not None:
                    self._add_invalidation(target_class[0].__name__.lower(), path[itemcounter])
                return False  # Fail the filter

        # Apply operators
        if item[1] == DataList.operator.EQUALS:
            return value == item[2]
        if item[1] == DataList.operator.GT:
            return value > item[2]
        if item[1] == DataList.operator.LT:
            return value < item[2]
        raise NotImplementedError('The given where_operator is not yet implemented.')

    def _load(self):
        self.data = StoredObject.volatile.get(self._key) if self._key is not None else None
        if self.data is None:
            # The query should be a dictionary:
            #     {'object': Disk,                           # Object on which the query should be executed
            #      'data'  : DataList.select.XYZ,            # The requested result; a list of object descriptors, or a count
            #      'query' : <query>}                        # The actual query
            # Where <query> is a query(group) dictionary:
            #     {'type' : DataList.where_operator.ABC,     # Defines whether the given items should be considered in an AND or OR group
            #      'items': <items>}                         # The items in the group
            # Where the <items> is any combination of one or more <filter> or <query>
            # A <filter> tuple example:
            #     (<field>, DataList.operator.GHI, <value>)  # The operator can be for example EQUALS
            # The field is any property you would also find on the given object. In case of properties, you can dot as far as you like
            # This means you can combine AND and OR in any possible combination

            self.from_cache = False
            namespace = self._query['object']()._namespace
            name = self._query['object'].__name__.lower()
            base_key = '%s_%s_' % (namespace, name)
            keys = DataList.get_pks(namespace, name)
            if self._query['data'] == DataList.select.COUNT:
                self.data = 0
            else:
                self.data = []

            for key in keys:
                guid = key.replace(base_key, '')
                try:
                    instance = self._query['object'](guid)
                    if self._query['query']['type'] == DataList.where_operator.AND:
                        include = self._exec_and(instance, self._query['query']['items'])
                    elif self._query['query']['type'] == DataList.where_operator.OR:
                        include = self._exec_or(instance, self._query['query']['items'])
                    else:
                        raise NotImplementedError('The given operator is not yet implemented.')
                    if include:
                        if self._query['data'] == DataList.select.COUNT:
                            self.data += 1
                        elif self._query['data'] == DataList.select.DESCRIPTOR:
                            self.data.append(Descriptor(self._query['object'], guid).descriptor)
                        else:
                            raise NotImplementedError('The given selector type is not yet implemented.')
                except ObjectNotFoundException:
                    pass

            if self._key is not None and len(keys) > 0:
                StoredObject.volatile.set(self._key, self.data)
            self._update_listinvalidation()
        else:
            self.from_cache = True
        return self

    def _add_invalidation(self, object_name, field):
        field_list = self._invalidation.get(object_name, [])
        field_list.append(field)
        self._invalidation[object_name] = field_list
        pass

    def _update_listinvalidation(self):
        for object_name, field_list in self._invalidation.iteritems():
            key = '%s_%s' % (DataList.cachelink, object_name)
            cache_list = Toolbox.try_get(key, {})
            for field in field_list:
                list_list = cache_list.get(field, [])
                list_list.append(self._key)
                cache_list[field] = list_list
            StoredObject.volatile.set(key, cache_list)
            StoredObject.persistent.set(key, cache_list)