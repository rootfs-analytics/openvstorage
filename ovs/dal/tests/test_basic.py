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
Basic test module
"""
import uuid
import time
from unittest import TestCase
from ovs.dal.exceptions import *
from ovs.dal.dataobjectlist import DataObjectList
from ovs.extensions.storage.persistent.dummystore import DummyPersistentStore
from ovs.extensions.storage.volatile.dummystore import DummyVolatileStore
from ovs.extensions.storage.persistentfactory import PersistentFactory
from ovs.extensions.storage.volatilefactory import VolatileFactory
from ovs.dal.hybrids.t_testmachine import TestMachine
from ovs.dal.hybrids.t_testdisk import TestDisk
from ovs.dal.hybrids.t_testemachine import TestEMachine
from ovs.dal.datalist import DataList
from ovs.dal.helpers import Descriptor
from ovs.extensions.generic.volatilemutex import VolatileMutex


class Basic(TestCase):
    """
    The basic unittestsuite will test all basic functionality of the DAL framework
    It will also try accessing all dynamic properties of all hybrids making sure
    that code actually works. This however means that all loaded 3rd party libs
    need to be mocked
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up the unittest, mocking a certain set of 3rd party libraries and extensions.
        This makes sure the unittests can be executed without those libraries installed
        """
        PersistentFactory.store = DummyPersistentStore()
        PersistentFactory.store.clean()
        PersistentFactory.store.clean()
        VolatileFactory.store = DummyVolatileStore()
        VolatileFactory.store.clean()
        VolatileFactory.store.clean()

    @classmethod
    def setUp(cls):
        """
        (Re)Sets the stores on every test
        """
        PersistentFactory.store = DummyPersistentStore()
        PersistentFactory.store.clean()
        VolatileFactory.store = DummyVolatileStore()
        VolatileFactory.store.clean()

    @classmethod
    def tearDownClass(cls):
        """
        Clean up the unittest
        """
        pass

    def test_invalidobject(self):
        """
        Validates the behavior when a non-existing object is loaded
        """
        # Loading an non-existing object should raise
        self.assertRaises(ObjectNotFoundException, TestDisk, uuid.uuid4(), None)

    def test_newobject_delete(self):
        """
        Validates the behavior on object deletions
        """
        disk = TestDisk()
        disk.name = 'disk'
        disk.save()
        # An object should always have a guid
        guid = disk.guid
        self.assertIsNotNone(guid, 'Guid should not be None')
        # After deleting, the object should not be retreivable
        disk.delete()
        self.assertRaises(Exception, TestDisk, guid, None)

    def test_discard(self):
        """
        Validates the behavior regarding pending changes discard
        """
        disk = TestDisk()
        disk.name = 'one'
        disk.save()
        disk.name = 'two'
        # Discarding an object should rollback all changes
        disk.discard()
        self.assertEqual(disk.name, 'one', 'Data should be discarded')

    def test_updateproperty(self):
        """
        Validates the behavior regarding updating properties
        """
        disk = TestDisk()
        disk.name = 'test'
        disk.description = 'desc'
        # A property should be writable
        self.assertIs(disk.name, 'test', 'Property should be updated')
        self.assertIs(disk.description, 'desc', 'Property should be updated')

    def test_preinit(self):
        """
        Validates whether initial data is loaded on object creation
        """
        disk = TestDisk(data={'name': 'diskx'})
        disk.save()
        self.assertEqual(disk.name, 'diskx', 'Disk name should be preloaded')

    def test_datapersistent(self):
        """
        Validates whether data is persisted correctly
        """
        disk = TestDisk()
        guid = disk.guid
        disk.name = 'test'
        disk.save()
        # Retreiving an object should return the data as when it was saved
        disk2 = TestDisk(guid)
        self.assertEqual(disk.name, disk2.name, 'Data should be persistent')

    def test_readonlyproperty(self):
        """
        Validates whether all dynamic properties are actually read-only
        """
        disk = TestDisk()
        # Readonly properties should return data
        self.assertIsNotNone(disk.used_size, 'RO property should return data')

    def test_datastorewins(self):
        """
        Validates the "datastore_wins" behavior in the usecase where it wins
        """
        disk = TestDisk()
        disk.name = 'initial'
        disk.save()
        disk2 = TestDisk(disk.guid, datastore_wins=True)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        disk2.save()
        # With datastore_wins set to True, the datastore wins concurrency conflicts
        self.assertEqual(disk2.name, 'one', 'Data should be overwritten')

    def test_datastoreloses(self):
        """
        Validates the "datastore_wins" behavior in the usecase where it loses
        """
        disk = TestDisk()
        disk.name = 'initial'
        disk.save()
        disk2 = TestDisk(disk.guid, datastore_wins=False)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        disk2.save()
        # With datastore_wins set to False, the datastore loses concurrency conflicts
        self.assertEqual(disk2.name, 'two', 'Data should not be overwritten')

    def test_silentdatarefresh(self):
        """
        Validates whether the default scenario (datastore_wins=False) will execute silent
        data refresh
        """
        disk = TestDisk()
        disk.name = 'initial'
        disk.save()
        disk2 = TestDisk(disk.guid, datastore_wins=False)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        disk2.save()
        disk.save()  # This should not overwrite anything but instead refresh data
        # With datastore_wins set to False, the datastore loses concurrency conflicts
        self.assertEqual(disk2.name, 'two', 'Data should not be overwritten')
        self.assertEqual(disk.name, 'two', 'Data should be refreshed')

    def test_datastoreraises(self):
        """
        Validates the "datastore_wins" behavior in the usecase where it's supposed to raise
        """
        disk = TestDisk()
        disk.name = 'initial'
        disk.save()
        disk2 = TestDisk(disk.guid, datastore_wins=None)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        # with datastore_wins set to None, concurrency conflicts are raised
        self.assertRaises(ConcurrencyException, disk2.save)

    def test_volatileproperty(self):
        """
        Validates the volatile behavior of dynamic properties
        """
        disk = TestDisk()
        disk.size = 1000000
        value = disk.used_size
        # Volatile properties should be stored for the correct amount of time
        time.sleep(2)
        self.assertEqual(disk.used_size, value, 'Value should still be from cache')
        time.sleep(2)
        self.assertEqual(disk.used_size, value, 'Value should still be from cache')
        time.sleep(2)
        # ... after which they should be reloaded from the backend
        self.assertNotEqual(disk.used_size, value, 'Value should be different')

    def test_primarykeyvalidation(self):
        """
        Validates whether the passed in key (guid) of an object is validated
        """
        self.assertRaises(ValueError, TestDisk, 'foo', None)
        disk = TestDisk()  # Should not raise
        disk.name = 'disk'
        disk.save()
        _ = TestDisk(disk.guid)  # Should not raise

    def test_persistency(self):
        """
        Validates whether the object is fetches from the correct storage backend
        """
        disk = TestDisk()
        disk.name = 'test'
        disk.save()
        # Right after a save, the cache is invalidated
        disk2 = TestDisk(disk.guid)
        self.assertFalse(disk2._metadata['cache'], 'Object should be retreived from persistent backend')
        # Subsequent calls will retreive the object from cache
        disk3 = TestDisk(disk.guid)
        self.assertTrue(disk3._metadata['cache'], 'Object should be retreived from cache')
        # After the object expiry passed, it will be retreived from backend again
        DummyVolatileStore().delete(disk._key)  # We clear the entry
        disk4 = TestDisk(disk.guid)
        self.assertFalse(disk4._metadata['cache'], 'Object should be retreived from persistent backend')

    def test_queries(self):
        """
        Validates whether executing queries returns the expected results
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        for i in xrange(0, 20):
            disk = TestDisk()
            disk.name = 'test_{0}'.format(i)
            disk.size = i
            if i < 10:
                disk.machine = machine
            else:
                disk.storage = machine
            disk.save()
        self.assertEqual(len(machine.disks), 10, 'query should find added machines')
        # pylint: disable=line-too-long
        list_1 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('size', DataList.operator.EQUALS, 1)]}}).data  # noqa
        self.assertEqual(list_1, 1, 'list should contain int 1')
        list_2 = DataList({'object': TestDisk,
                           'data': DataList.select.DESCRIPTOR,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('size', DataList.operator.EQUALS, 1)]}}).data  # noqa
        found_object = Descriptor().load(list_2[0]).get_object(True)
        self.assertEqual(found_object.name, 'test_1', 'list should contain corret machine')
        list_3 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('size', DataList.operator.GT, 3),
                                               ('size', DataList.operator.LT, 6)]}}).data  # noqa
        self.assertEqual(list_3, 2, 'list should contain int 2')  # disk 4 and 5
        list_4 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.OR,
                                     'items': [('size', DataList.operator.LT, 3),
                                               ('size', DataList.operator.GT, 6)]}}).data  # noqa
        # at least disk 0, 1, 2, 7, 8, 9, 10-19
        self.assertGreaterEqual(list_4, 16, 'list should contain >= 16')
        list_5 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('machine.guid', DataList.operator.EQUALS, machine.guid),  # noqa
                                               {'type': DataList.where_operator.OR,
                                                'items': [('size', DataList.operator.LT, 3),
                                                          ('size', DataList.operator.GT, 6)]}]}}).data  # noqa
        self.assertEqual(list_5, 6, 'list should contain int 6')  # disk 0, 1, 2, 7, 8, 9
        list_6 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('size', DataList.operator.LT, 3),
                                               ('size', DataList.operator.GT, 6)]}}).data  # noqa
        self.assertEqual(list_6, 0, 'list should contain int 0')  # no disks
        list_7 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.OR,
                                     'items': [('machine.guid', DataList.operator.EQUALS, '123'),  # noqa
                                               ('used_size', DataList.operator.EQUALS, -1),
                                               {'type': DataList.where_operator.AND,
                                                'items': [('size', DataList.operator.GT, 3),
                                                          ('size', DataList.operator.LT, 6)]}]}}).data  # noqa
        self.assertEqual(list_7, 2, 'list should contain int 2')  # disk 4 and 5
        list_8 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('machine.name', DataList.operator.EQUALS, 'machine'),  # noqa
                                               ('name', DataList.operator.EQUALS, 'test_3')]}}).data  # noqa
        self.assertEqual(list_8, 1, 'list should contain int 1')  # disk 3
        list_9 = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('size', DataList.operator.GT, 3),
                                               {'type': DataList.where_operator.AND,
                                                'items': [('size', DataList.operator.LT, 6)]}]}}).data  # noqa
        self.assertEqual(list_9, 2, 'list should contain int 2')  # disk 4 and 5
        list_10 = DataList({'object': TestDisk,
                            'data': DataList.select.COUNT,
                            'query': {'type': DataList.where_operator.OR,
                                      'items': [('size', DataList.operator.LT, 3),
                                                {'type': DataList.where_operator.OR,
                                                 'items': [('size', DataList.operator.GT, 6)]}]}}).data  # noqa
        # at least disk 0, 1, 2, 7, 8, 9, 10-19
        self.assertGreaterEqual(list_10, 16, 'list should contain >= 16')
        list_11 = DataList({'object': TestDisk,
                            'data': DataList.select.COUNT,
                            'query': {'type': DataList.where_operator.AND,
                                      'items': [('storage.name', DataList.operator.EQUALS, 'machine')]}}).data  # noqa
        self.assertEqual(list_11, 10, 'list should contain int 10')  # disk 10-19
        # pylint: enable=line-too-long

    def test_invalidpropertyassignment(self):
        """
        Validates whether the correct exception is raised when properties are assigned with a wrong
        type
        """
        disk = TestDisk()
        disk.size = 100
        with self.assertRaises(TypeError):
            disk.machine = TestDisk()

    def test_recursive(self):
        """
        Validates the recursive save
        """
        machine = TestMachine()
        machine.name = 'original'
        machine.save()
        disks = []
        for i in xrange(0, 10):
            disk = TestDisk()
            disk.name = 'test_{0}'.format(i)
            if i % 2:
                disk.machine = machine
            else:
                disk.machine = machine
                self.assertEqual(disk.machine.name, 'original', 'child should be set')
                disk.machine = None
                self.assertIsNone(disk.machine, 'child should be cleared')
                disks.append(disk)
            disk.save()
        counter = 1
        for disk in machine.disks:
            disk.size = counter
            counter += 1
        machine.save(recursive=True)
        disk = TestDisk(machine.disks[0].guid)
        self.assertEqual(disk.size, 1, 'lists should be saved recursively')
        disk.machine.name = 'mtest'
        disk.save(recursive=True)
        machine2 = TestMachine(machine.guid)
        self.assertEqual(machine2.disks[1].size, 2, 'lists should be saved recursively')
        self.assertEqual(machine2.name, 'mtest', 'properties should be saved recursively')

    def test_descriptors(self):
        """
        Validates the correct behavior of the Descriptor
        """
        with self.assertRaises(RuntimeError):
            _ = Descriptor().descriptor
        with self.assertRaises(RuntimeError):
            _ = Descriptor().get_object()

    def test_relationcache(self):
        """
        Validates whether the relational properties are cached correctly, and whether
        they are invalidated when required
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk1 = TestDisk()
        disk1.name = 'disk1'
        disk1.save()
        disk2 = TestDisk()
        disk2.name = 'disk2'
        disk2.save()
        disk3 = TestDisk()
        disk3.name = 'disk3'
        disk3.save()
        self.assertEqual(len(machine.disks), 0, 'There should be no disks on the machine')
        disk1.machine = machine
        disk1.save()
        self.assertEqual(len(machine.disks), 1, 'There should be 1 disks on the machine')
        disk2.machine = machine
        disk2.save()
        self.assertEqual(len(machine.disks), 2, 'There should be 2 disks on the machine')
        disk3.machine = machine
        disk3.save()
        self.assertEqual(len(machine.disks), 3, 'There should be 3 disks on the machine')
        machine.disks[0].name = 'disk1_'
        machine.disks[1].name = 'disk2_'
        machine.disks[2].name = 'disk3_'
        disk1.machine = None
        disk1.save()
        disk2.machine = None
        disk2.save()
        self.assertEqual(len(machine.disks), 1, 'There should be 1 disks on the machine')

    def test_datalistactions(self):
        """
        Validates all actions that can be executed agains DataLists
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk1 = TestDisk()
        disk1.name = 'disk1'
        disk1.machine = machine
        disk1.save()
        disk2 = TestDisk()
        disk2.name = 'disk2'
        disk2.machine = machine
        disk2.save()
        disk3 = TestDisk()
        disk3.name = 'disk3'
        disk3.machine = machine
        disk3.save()
        self.assertEqual(machine.disks.count(disk1), 1, 'Disk should be available only once')
        self.assertGreaterEqual(machine.disks.index(disk1), 0, 'We should retreive an index')
        machine.disks.sort()
        guid = machine.disks[0].guid
        machine.disks.reverse()
        self.assertEqual(machine.disks[-1].guid, guid, 'Reverse and sort should work')
        machine.disks.sort()
        self.assertEqual(machine.disks[0].guid, guid, 'And the guid should be first again')

    def test_listcache(self):
        """
        Validates whether lists are cached and invalidated correctly
        """
        keys = ['list_cache', None]
        for key in keys:
            disk0 = TestDisk()
            disk0.name = 'disk 0'
            disk0.save()
            list_cache = DataList(key=key,
                                  query={'object': TestDisk,
                                         'data': DataList.select.COUNT,
                                         'query': {'type': DataList.where_operator.AND,
                                                   'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
            self.assertFalse(list_cache.from_cache, 'List should not be loaded from cache (mode: {0})'.format(key))
            self.assertEqual(list_cache.data, 0, 'List should find no entries (mode: {0})'.format(key))
            machine = TestMachine()
            machine.name = 'machine'
            machine.save()
            disk1 = TestDisk()
            disk1.name = 'disk 1'
            disk1.machine = machine
            disk1.save()
            list_cache = DataList(key=key,
                                  query={'object': TestDisk,
                                         'data': DataList.select.COUNT,
                                         'query': {'type': DataList.where_operator.AND,
                                                   'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
            self.assertFalse(list_cache.from_cache, 'List should not be loaded from cache (mode: {0})'.format(key))
            self.assertEqual(list_cache.data, 1, 'List should find one entry (mode: {0})'.format(key))
            list_cache = DataList(key=key,
                                  query={'object': TestDisk,
                                         'data': DataList.select.COUNT,
                                         'query': {'type': DataList.where_operator.AND,
                                                   'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
            self.assertTrue(list_cache.from_cache, 'List should be loaded from cache (mode: {0})'.format(key))
            disk2 = TestDisk()
            disk2.machine = machine
            disk2.name = 'disk 2'
            disk2.save()
            list_cache = DataList(key=key,
                                  query={'object': TestDisk,
                                         'data': DataList.select.COUNT,
                                         'query': {'type': DataList.where_operator.AND,
                                                   'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
            self.assertFalse(list_cache.from_cache, 'List should not be loaded from cache (mode: {0})'.format(key))
            self.assertEqual(list_cache.data, 2, 'List should find two entries (mode: {0})'.format(key))
            machine.name = 'x'
            machine.save()
            list_cache = DataList(key=key,
                                  query={'object': TestDisk,
                                         'data': DataList.select.COUNT,
                                         'query': {'type': DataList.where_operator.AND,
                                                   'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
            self.assertFalse(list_cache.from_cache, 'List should not be loaded from cache (mode: {0})'.format(key))
            self.assertEqual(list_cache.data, 0, 'List should have no matches (mode: {0})'.format(key))

    def test_emptyquery(self):
        """
        Validates whether an certain query returns an empty set
        """
        amount = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}}).data  # noqa
        self.assertEqual(amount, 0, 'There should be no data')

    def test_nofilterquery(self):
        """
        Validates whether empty queries return the full resultset
        """
        disk1 = TestDisk()
        disk1.name = 'disk 1'
        disk1.save()
        disk2 = TestDisk()
        disk2.name = 'disk 2'
        disk2.save()
        amount = DataList(key='some_list',
                          query={'object': TestDisk,
                                 'data': DataList.select.COUNT,
                                 'query': {'type': DataList.where_operator.AND,
                                           'items': []}}).data
        self.assertEqual(amount, 2, 'There should be two disks ({0})'.format(amount))
        disk3 = TestDisk()
        disk3.name = 'disk 3'
        disk3.save()
        amount = DataList(key='some_list',
                          query={'object': TestDisk,
                                 'data': DataList.select.COUNT,
                                 'query': {'type': DataList.where_operator.AND,
                                           'items': []}}).data
        self.assertEqual(amount, 3, 'There should be three disks ({0})'.format(amount))

    def test_invalidqueries(self):
        """
        Validates invalid queries
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk = TestDisk()
        disk.name = 'disk'
        disk.machine = machine
        disk.save()
        setattr(DataList.select, 'SOMETHING', 'SOMETHING')
        with self.assertRaises(NotImplementedError):
            DataList({'object': TestDisk,
                      'data': DataList.select.SOMETHING,
                      'query': {'type': DataList.where_operator.AND,
                                'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
        setattr(DataList.where_operator, 'SOMETHING', 'SOMETHING')
        with self.assertRaises(NotImplementedError):
            DataList({'object': TestDisk,
                      'data': DataList.select.COUNT,
                      'query': {'type': DataList.where_operator.SOMETHING,
                                'items': [('machine.name', DataList.operator.EQUALS, 'machine')]}})  # noqa
        setattr(DataList.operator, 'SOMETHING', 'SOMETHING')
        with self.assertRaises(NotImplementedError):
            DataList({'object': TestDisk,
                      'data': DataList.select.COUNT,
                      'query': {'type': DataList.where_operator.AND,
                                'items': [('machine.name', DataList.operator.SOMETHING, 'machine')]}})  # noqa

    def test_clearedcache(self):
        """
        Validates the correct behavior when the volatile cache is cleared
        """
        disk = TestDisk()
        disk.name = 'somedisk'
        disk.save()
        VolatileFactory.store.delete(disk._key)
        disk2 = TestDisk(disk.guid)
        self.assertEqual(disk2.name, 'somedisk', 'Disk should be fetched from persistent store')

    def test_serialization(self):
        """
        Validates whether serialization works as expected
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk = TestDisk()
        disk.name = 'disk'
        disk.machine = machine
        disk.save()
        dictionary = disk.serialize()
        self.assertIn('name', dictionary, 'Serialized object should have correct properties')
        self.assertEqual(dictionary['name'], 'disk', 'Serialized object should have correct name')
        self.assertIn('machine_guid', dictionary, 'Serialized object should have correct depth')
        self.assertEqual(dictionary['machine_guid'], machine.guid,
                         'Serialized object should have correct properties')
        dictionary = disk.serialize(depth=1)
        self.assertIn('machine', dictionary, 'Serialized object should have correct depth')
        self.assertEqual(dictionary['machine']['name'], 'machine',
                         'Serialized object should have correct properties at all depths')

    def test_primarykeys(self):
        """
        Validates whether the primary keys are kept in sync
        """
        disk = TestDisk()
        disk.name = 'disk'
        VolatileFactory.store.delete('ovs_primarykeys_{0}'.format(disk._name))
        keys = DataList.get_pks(disk._namespace, disk._name)
        self.assertEqual(len(keys), 0, 'There should be no primary keys ({0})'.format(len(keys)))
        disk.save()
        keys = DataList.get_pks(disk._namespace, disk._name)
        self.assertEqual(len(keys), 1, 'There should be one primary key ({0})'.format(len(keys)))

    def test_reduceddatalist(self):
        """
        Validates the reduced list
        """
        disk = TestDisk()
        disk.name = 'test'
        disk.save()
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': []}}).data
        datalist = DataObjectList(data, TestDisk)
        self.assertEqual(len(datalist), 1, 'There should be only one item ({0})'.format(len(datalist)))
        item = datalist.reduced[0]
        with self.assertRaises(AttributeError):
            print item.name
        self.assertEqual(item.guid, disk.guid, 'The guid should be available')

    def test_volatiemutex(self):
        """
        Validates the volatile mutex
        """
        mutex = VolatileMutex('test')
        mutex.acquire()
        mutex.acquire()  # Should not raise errors
        mutex.release()
        mutex.release()  # Should not raise errors
        mutex._volatile.add(mutex.key(), 1, 10)
        with self.assertRaises(RuntimeError):
            mutex.acquire(wait=1)
        mutex._volatile.delete(mutex.key())
        mutex.acquire()
        time.sleep(0.5)
        mutex.release()

    def test_typesafety(self):
        """
        Validates typesafety checking on object properties
        """
        disk = TestDisk()
        disk.name = 'test'
        disk.name = u'test'
        disk.name = None
        disk.size = 100
        disk.size = 100.5
        disk.order = 100
        with self.assertRaises(TypeError):
            disk.order = 100.5
        with self.assertRaises(TypeError):
            disk.__dict__['wrong_type_data'] = None
            disk.wrong_type_data = 'string'
            _ = disk.wrong_type
        with self.assertRaises(TypeError):
            disk.type = 'THREE'
        disk.type = 'ONE'

    def test_ownrelations(self):
        """
        Validates whether relations to the object itself are working
        """
        pdisk = TestDisk()
        pdisk.name = 'parent'
        pdisk.save()
        cdisk1 = TestDisk()
        cdisk1.name = 'child 1'
        cdisk1.size = 100
        cdisk1.parent = pdisk
        cdisk1.save()
        cdisk2 = TestDisk()
        cdisk2.name = 'child 2'
        cdisk2.size = 100
        cdisk2.parent = pdisk
        cdisk2.save()
        self.assertEqual(len(pdisk.children), 2, 'There should be 2 children.')
        self.assertEqual(cdisk1.parent.name, 'parent', 'Parent should be loaded correctly')
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('parent.name', DataList.operator.EQUALS, 'parent')]}}).data
        datalist = DataObjectList(data, TestDisk)
        self.assertEqual(len(datalist), 2, 'There should be two items ({0})'.format(len(datalist)))
        cdisk2.parent = None
        cdisk2.save()
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('parent.name', DataList.operator.EQUALS, 'parent')]}}).data
        datalist = DataObjectList(data, TestDisk)
        self.assertEqual(len(datalist), 1, 'There should be one item ({0})'.format(len(datalist)))

    def test_copy(self):
        """
        Validates whether the copy function works correct
        """
        machine = TestMachine()
        machine.name = 'testmachine1'
        machine.save()
        disk1 = TestDisk()
        disk1.name = 'test1'
        disk1.size = 100
        disk1.order = 1
        disk1.type = 'ONE'
        disk1.machine = machine
        disk1.save()
        disk2 = TestDisk()
        disk2.copy(disk1)
        self.assertEqual(disk2.name, 'test1', 'Properties should be copied')
        self.assertEqual(disk2.size, 100, 'Properties should be copied')
        self.assertEqual(disk2.order, 1, 'Properties should be copied')
        self.assertEqual(disk2.type, 'ONE', 'Properties should be copied')
        self.assertEqual(disk2.machine, None, 'Relations should not be copied')
        disk3 = TestDisk()
        disk3.copy(disk1, include_relations=True)
        self.assertEqual(disk3.machine.name, 'testmachine1', 'Relations should be copied')
        disk4 = TestDisk()
        disk4.copy(disk1, include=['name'])
        self.assertEqual(disk4.name, 'test1', 'Name should be copied')
        self.assertEqual(disk4.size, 0, 'Size should not be copied')
        self.assertEqual(disk4.machine, None, 'Relations should not be copied')
        disk5 = TestDisk()
        disk5.copy(disk1, exclude=['name'])
        self.assertEqual(disk5.name, None, 'Name should not be copied')
        self.assertEqual(disk5.size, 100, 'Size should be copied')
        self.assertEqual(disk5.machine, None, 'Relations should not be copied')

    def test_querydynamic(self):
        """
        Validates whether a query that queried dynamic properties is never cached
        """
        def get_disks():
            return DataList({'object': TestDisk,
                             'data': DataList.select.DESCRIPTOR,
                             'query': {'type': DataList.where_operator.AND,
                                       'items': [('used_size', DataList.operator.NOT_EQUALS, -1)]}})
        disk1 = TestDisk()
        disk1.name = 'disk 1'
        disk1.size = 100
        disk1.save()
        disk2 = TestDisk()
        disk2.name = 'disk 2'
        disk2.size = 100
        disk2.save()
        query_result = get_disks()
        self.assertEqual(len(query_result.data), 2, 'There should be 2 disks ({0})'.format(len(query_result.data)))
        self.assertFalse(query_result.from_cache, 'Disk should not be loaded from cache')
        query_result = get_disks()
        self.assertFalse(query_result.from_cache, 'Disk should not be loaded from cache')

    def test_delete_abandoning(self):
        """
        Validates the abandoning behavior of the delete method
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk_1 = TestDisk()
        disk_1.name = 'disk 1'
        disk_1.machine = machine
        disk_1.save()
        disk_2 = TestDisk()
        disk_2.name = 'disk 2'
        disk_2.machine = machine
        disk_2.save()
        self.assertRaises(LinkedObjectException, machine.delete)
        disk_3 = TestDisk(disk_1.guid)
        self.assertIsNotNone(disk_3.machine, 'The machine should still be linked')
        _ = machine.disks  # Make sure we loaded the list
        disk_2.delete()
        machine.delete(abandon=True)  # Should not raise due to disk_2 being deleted
        disk_4 = TestDisk(disk_1.guid)
        self.assertIsNone(disk_4.machine, 'The machine should be unlinked')

    def test_save_deleted(self):
        """
        Validates whether saving a previously deleted object raises
        """
        disk = TestDisk()
        disk.name = 'disk'
        disk.save()
        disk.delete()
        self.assertRaises(ObjectNotFoundException, disk.save, 'Cannot resave a deleted object')

    def test_dol_advanced(self):
        """
        Validates the DataObjectList advanced functions (indexer, sort)
        """
        sizes = [7, 2, 0, 4, 6, 1, 5, 9, 3, 8]
        guids = []
        for i in xrange(0, 10):
            disk = TestDisk()
            disk.name = 'disk_{0}'.format(i)
            disk.size = sizes[i]
            disk.save()
            guids.append(disk.guid)
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': []}}).data
        disks = DataObjectList(data, TestDisk)
        disks.sort()
        guids.sort()
        self.assertEqual(disks[0].guid, guids[0], 'Disks should be sorted on guid')
        self.assertEqual(disks[4].guid, guids[4], 'Disks should be sorted on guid')
        disks.sort(cmp=lambda a, b: a.size - b.size)
        self.assertEqual(disks[0].size, 0, 'Disks should be sorted on size')
        self.assertEqual(disks[4].size, 4, 'Disks should be sorted on size')
        disks.sort(key=lambda a: a.name)
        self.assertEqual(disks[0].name, 'disk_0', 'Disks should be sorted on name')
        self.assertEqual(disks[4].name, 'disk_4', 'Disks should be sorted on name')
        filtered = disks[1:4]
        self.assertEqual(filtered[0].name, 'disk_1', 'Disks should be properly sliced')
        self.assertEqual(filtered[2].name, 'disk_3', 'Disks should be properly sliced')

    def test_fullrelation_load(self):
        """
        Validates whether a single relation load will preload all other related relations
        """
        machine_1 = TestMachine()
        machine_1.name = 'machine 1'
        machine_1.save()
        disk_1_1 = TestDisk()
        disk_1_1.name = 'disk 1.1'
        disk_1_1.machine = machine_1
        disk_1_1.save()
        disk_1_2 = TestDisk()
        disk_1_2.name = 'disk 1.2'
        disk_1_2.machine = machine_1
        disk_1_2.save()
        machine_2 = TestMachine()
        machine_2.name = 'machine 2'
        machine_2.save()
        disk_2_1 = TestDisk()
        disk_2_1.name = 'disk 2.1'
        disk_2_1.machine = machine_2
        disk_2_1.save()
        disk_2_2 = TestDisk()
        disk_2_2.name = 'disk 2.2'
        disk_2_2.machine = machine_2
        disk_2_2.save()
        # Load relations
        disks_1 = DataList.get_relation_set(TestDisk, 'machine', TestEMachine, 'disks', machine_1.guid)
        self.assertEqual(len(disks_1.data), 2, 'There should be 2 child disks')
        self.assertFalse(disks_1.from_cache, 'The relation should not be loaded from cache')
        disks_2 = DataList.get_relation_set(TestDisk, 'machine', TestEMachine, 'disks', machine_2.guid)
        self.assertEqual(len(disks_2.data), 2, 'There should be 2 child disks')
        self.assertTrue(disks_2.from_cache, 'The relation should be loaded from cache')

    def test_itemchange_during_list_build(self):
        """
        Validates whether changing, creating or deleting objects while running a depending list will cause the list to
        be invalidated
        """
        def inject_new(datalist_object):
            """
            Creates a new object
            """
            _ = datalist_object
            disk_x = TestDisk()
            disk_x.name = 'test'
            disk_x.save()

        def inject_delete(datalist_object):
            """
            Deletes an object
            """
            _ = datalist_object
            disk_1.delete()

        def inject_update(datalist_object):
            """
            Updates an object
            """
            _ = datalist_object
            disk_2.name = 'x'
            disk_2.save()

        disk_z = None
        disk_1 = TestDisk()
        disk_1.name = 'test'
        disk_1.save()
        disk_2 = TestDisk()
        disk_2.name = 'test'
        disk_2.save()

        # Validates new object creation
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('name', DataList.operator.EQUALS, 'test')]}},
                        post_query_hook=inject_new).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 2, 'Two disks should be found ({0})'.format(len(disks)))
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('name', DataList.operator.EQUALS, 'test')]}}).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 3, 'Three disks should be found ({0})'.format(len(disks)))

        # Clear the list cache for the next test
        VolatileFactory.store.delete('ovs_list_28a00ef0990e0afbbefa129290eecd6b7820534c4a10c6728380320720006c33')

        # Validates object change
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('name', DataList.operator.EQUALS, 'test')]}},
                        post_query_hook=inject_update).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 3, 'Three disks should be found ({0})'.format(len(disks)))
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('name', DataList.operator.EQUALS, 'test')]}}).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 2, 'Two disk should be found ({0})'.format(len(disks)))

        # Clear the list cache for the next test
        VolatileFactory.store.delete('ovs_list_28a00ef0990e0afbbefa129290eecd6b7820534c4a10c6728380320720006c33')

        # Validates object deletion
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('name', DataList.operator.EQUALS, 'test')]}},
                        post_query_hook=inject_delete).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 2, 'Two disks should be found ({0})'.format(len(disks)))
        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('name', DataList.operator.EQUALS, 'test')]}}).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 1, 'One disks should be found ({0})'.format(len(disks)))
        _ = disk_z  # Ignore this object not being used

    def test_guid_query(self):
        """
        Validates whether queries can use the _guid fields
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk = TestDisk()
        disk.name = 'test'
        disk.machine = machine
        disk.save()

        data = DataList({'object': TestDisk,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': [('machine_guid', DataList.operator.EQUALS, machine.guid)]}}).data
        disks = DataObjectList(data, TestDisk)
        self.assertEqual(len(disks), 1, 'There should be one disk ({0})'.format(len(disks)))

    def test_1_to_1(self):
        """
        Validates whether 1-to-1 relations work correct
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()

        self.assertIsNone(machine.one, 'The machine should not have a reverse disk relation')
        self.assertIsNone(machine.one_guid, 'The machine should have an empty disk _guid property')

        disk = TestDisk()
        disk.name = 'test'
        disk.one = machine
        disk.save()

        self.assertIsNotNone(machine.one, 'The machine should have a reverse disk relation')
        self.assertEqual(machine.one.name, 'test', 'The reverse 1-to-1 relation should work')
        self.assertEqual(disk.one.name, 'machine', 'The normal 1-to-1 relation should work')
        self.assertEqual(machine.one_guid, disk.guid, 'The reverse disk should be the correct one')

        with self.assertRaises(RuntimeError):
            machine.one = disk

    def test_auto_inheritance(self):
        """
        Validates whether fetching a base hybrid will result in the extended object
        """
        machine = TestMachine()
        self.assertEqual(Descriptor(machine.__class__), Descriptor(TestEMachine), 'The fetched TestMachine should be a TestEMachine')

    def test_relation_inheritance(self):
        """
        Validates whether relations on inherited hybrids behave OK
        """
        machine = TestMachine()
        machine.name = 'machine'
        machine.save()
        disk = TestDisk()
        disk.name = 'disk'
        disk.machine = machine  # Validates relation acceptance (accepts TestEMachine)
        disk.save()
        machine.the_disk = disk  # Validates whether _relations is build correctly
        machine.save()

        disk2 = TestDisk(disk.guid)
        self.assertEqual(Descriptor(disk2.machine.__class__), Descriptor(TestEMachine), 'The machine should be a TestEMachine')

    def test_extended_property(self):
        """
        Validates whether an inherited object has all properties
        """
        machine = TestEMachine()
        machine.name = 'emachine'
        machine.extended = 'ext'
        machine.save()

        machine2 = TestEMachine(machine.guid)
        self.assertEqual(machine2.name, 'emachine', 'The name of the extended machine should be correct')
        self.assertEqual(machine2.extended, 'ext', 'The extended property of the extended machine should be correct')

    def test_extended_filter(self):
        """
        Validates whether base and extended hybrids behave the same in lists
        """
        machine1 = TestMachine()
        machine1.name = 'basic'
        machine1.save()
        machine2 = TestEMachine()
        machine2.name = 'extended'
        machine2.save()
        data = DataList({'object': TestMachine,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': []}}).data
        datalist = DataObjectList(data, TestMachine)
        self.assertEqual(len(datalist), 2, 'There should be two machines if searched for TestMachine ({0})'.format(len(datalist)))
        data = DataList({'object': TestEMachine,
                         'data': DataList.select.DESCRIPTOR,
                         'query': {'type': DataList.where_operator.AND,
                                   'items': []}}).data
        datalist = DataObjectList(data, TestMachine)
        self.assertEqual(len(datalist), 2, 'There should be two machines if searched for TestEMachine ({0})'.format(len(datalist)))

    def test_mandatory_fields(self):
        """
        Validates whether mandatory properties and relations work
        """
        machine = TestMachine()
        machine.extended = 'extended'
        machine.name = 'machine'
        machine.save()
        disk = TestDisk()
        # Modify relation to mandatory
        [_ for _ in disk._relations if _.name == 'machine'][0].mandatory = True
        # Continue test
        disk.name = None
        with self.assertRaises(MissingMandatoryFieldsException) as exception:
            disk.save()
        self.assertIn('name', exception.exception.message, 'Field name should be in exception message: {0}'.format(exception.exception.message))
        self.assertIn('machine', exception.exception.message, 'Field machine should be in exception message: {0}'.format(exception.exception.message))
        disk.name = 'disk'
        disk.machine = machine
        disk.save()
        disk.description = 'test'
        disk.storage = machine
        disk.save()
        # Restore relation
        [_ for _ in disk._relations if _.name == 'machine'][0].mandatory = False

