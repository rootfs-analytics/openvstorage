import uuid
import time
from unittest import TestCase
from ovsdal.storedobject import StoredObject
from ovsdal.hybrids.disk import Disk
from ovsdal.hybrids.machine import Machine
from ovsdal.datalist import DataList
from ovsdal.storage.dummies import DummyPersistentStore, DummyVolatileStore
from ovsdal.exceptions import *
from ovsdal.helpers import HybridRunner, Descriptor


#noinspection PyUnresolvedReferences
class Basic(TestCase):
    @classmethod
    def setUpClass(cls):
        DummyVolatileStore.clean()
        DummyPersistentStore.clean()
        # Test to make sure the clean doesn't raise if there is nothing to clean
        DummyVolatileStore.clean()
        DummyPersistentStore.clean()

    @classmethod
    def setUp(cls):
        StoredObject.persistent = DummyPersistentStore()
        StoredObject.volatile = DummyVolatileStore()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_invalidobject(self):
        # Loading an non-existing object should raise
        self.assertRaises(ObjectNotFoundException, Disk, uuid.uuid4(), None)

    def test_newobjet_delete(self):
        disk = Disk()
        disk.save()
        # An object should always have a guid
        guid = disk.guid
        self.assertIsNotNone(guid, 'Guid should not be None')
        # After deleting, the object should not be retreivable
        disk.delete()
        self.assertRaises(Exception, Disk,  guid, None)

    def test_discard(self):
        disk = Disk()
        disk.name = 'one'
        disk.save()
        disk.name = 'two'
        # Discarding an object should rollback all changes
        disk.discard()
        self.assertEqual(disk.name, 'one', 'Data should be discarded')
        disk.delete()

    def test_updateproperty(self):
        disk = Disk()
        disk.name = 'test'
        disk.description = 'desc'
        # A property should be writable
        self.assertIs(disk.name, 'test', 'Property should be updated')
        self.assertIs(disk.description, 'desc', 'Property should be updated')
        disk.delete()

    def test_datapersistent(self):
        disk = Disk()
        guid = disk.guid
        disk.name = 'test'
        disk.save()
        # Retreiving an object should return the data as when it was saved
        disk2 = Disk(guid)
        self.assertEqual(disk.name, disk2.name, 'Data should be persistent')
        disk.delete()

    def test_readonlyproperty(self):
        disk = Disk()
        # Readonly properties should return data
        self.assertIsNotNone(disk.used_size, 'RO property should return data')
        disk.delete()

    def test_datastorewins(self):
        disk = Disk()
        disk.name = 'initial'
        disk.save()
        disk2 = Disk(disk.guid, datastore_wins=True)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        disk2.save()
        # With datastore_wins set to True, the datastore wins concurrency conflicts
        self.assertEqual(disk2.name, 'one', 'Data should be overwritten')
        disk.delete()

    def test_datastoreloses(self):
        disk = Disk()
        disk.name = 'initial'
        disk.save()
        disk2 = Disk(disk.guid, datastore_wins=False)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        disk2.save()
        # With datastore_wins set to False, the datastore loses concurrency conflicts
        self.assertEqual(disk2.name, 'two', 'Data should not be overwritten')
        disk.delete()

    def test_datastoreraises(self):
        disk = Disk()
        disk.name = 'initial'
        disk.save()
        disk2 = Disk(disk.guid, datastore_wins=None)
        disk.name = 'one'
        disk.save()
        disk2.name = 'two'
        # with datastore_wins set to None, concurrency conflicts are raised
        self.assertRaises(ConcurrencyException, disk2.save)
        disk.delete()

    def test_volatileproperty(self):
        disk = Disk()
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
        disk.delete()

    def test_persistency(self):
        disk = Disk()
        disk.name = 'test'
        disk.save()
        # Right after a save, the cache is invalidated
        disk2 = Disk(disk.guid)
        self.assertFalse(disk2._metadata['cache'], 'Object should be retreived from persistent backend')
        # Subsequent calls will retreive the object from cache
        disk3 = Disk(disk.guid)
        self.assertTrue(disk3._metadata['cache'], 'Object should be retreived from cache')
        # After the object expiry passed, it will be retreived from backend again
        DummyVolatileStore().delete(disk._key)  # We clear the entry
        disk4 = Disk(disk.guid)
        self.assertFalse(disk4._metadata['cache'], 'Object should be retreived from persistent backend')
        disk.delete()

    def test_objectproperties(self):
        # Some stuff here to dynamically test all hybrid properties
        for cls in HybridRunner.get_hybrids():
            # Make sure certain attributes are correctly set
            self.assertIsInstance(cls._blueprint, dict, '_blueprint is a required property on %s' % cls.__name__)
            self.assertIsInstance(cls._expiry, dict, '_expiry is a required property on %s' % cls.__name__)
            instance = cls()
            # Make sure the type can be instantiated
            self.assertIsNotNone(instance.guid)
            properties = []
            for item in dir(instance):
                if hasattr(cls, item) and isinstance(getattr(cls, item), property):
                    properties.append(item)
            # All expiries should be implemented
            for attribute in instance._expiry.keys():
                self.assertIn(attribute, properties, '%s should be a property' % attribute)
                # ... and should work
                data = getattr(instance, attribute)
            instance.delete()

    def test_queries(self):
        machine = Machine()
        machine.name = 'machine'
        machine.save()
        for i in xrange(0, 20):
            disk = Disk()
            disk.name = 'test_%d' % i
            disk.size = i
            if i < 10:
                disk.machine = machine
            else:
                disk.storage = machine
            disk.save()
        self.assertEqual(len(machine.disks), 10, 'query should find added machines')
        list_1 = DataList(key   = 'list_1',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('size', DataList.operator.EQUALS, 1)]}}).data
        self.assertEqual(list_1, 1, 'list should contain int 1')
        list_2 = DataList(key   = 'list_2',
                          query = {'object': Disk,
                                   'data'  : DataList.select.OBJECT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('size', DataList.operator.EQUALS, 1)]}}).data
        found_object = Descriptor().load(list_2[0]).get_object(True)
        self.assertEqual(found_object.name, 'test_1', 'list should contain corret machine')
        list_3 = DataList(key   = 'list_3',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('size', DataList.operator.GT, 3),
                                                        ('size', DataList.operator.LT, 6)]}}).data
        self.assertEqual(list_3, 2, 'list should contain int 2')  # disk 4 and 5
        list_4 = DataList(key   = 'list_4',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.OR,
                                              'items': [('size', DataList.operator.LT, 3),
                                                        ('size', DataList.operator.GT, 6)]}}).data
        self.assertGreaterEqual(list_4, 16, 'list should contain >= 16')  # at least disk 0, 1, 2, 7, 8, 9, 10-19
        list_5 = DataList(key   = 'list_5',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('machine.guid', DataList.operator.EQUALS, machine.guid),
                                                        {'type' : DataList.where_operator.OR,
                                                         'items': [('size', DataList.operator.LT, 3),
                                                                   ('size', DataList.operator.GT, 6)]}]}}).data
        self.assertEqual(list_5, 6, 'list should contain int 6')  # disk 0, 1, 2, 7, 8, 9
        list_6 = DataList(key   = 'list_6',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('size', DataList.operator.LT, 3),
                                                        ('size', DataList.operator.GT, 6)]}}).data
        self.assertEqual(list_6, 0, 'list should contain int 0')  # no disks
        list_7 = DataList(key   = 'list_7',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.OR,
                                              'items': [('machine.guid', DataList.operator.EQUALS, '123'),
                                                        ('used_size', DataList.operator.EQUALS, -1),
                                                        {'type' : DataList.where_operator.AND,
                                                         'items': [('size', DataList.operator.GT, 3),
                                                                   ('size', DataList.operator.LT, 6)]}]}}).data
        self.assertEqual(list_7, 2, 'list should contain int 2')  # disk 4 and 5
        list_8 = DataList(key   = 'list_8',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('machine.name', DataList.operator.EQUALS, 'machine'),
                                                        ('name', DataList.operator.EQUALS, 'test_3')]}}).data
        self.assertEqual(list_8, 1, 'list should contain int 1')  # disk 3
        list_9 = DataList(key   = 'list_9',
                          query = {'object': Disk,
                                   'data'  : DataList.select.COUNT,
                                   'query' : {'type': DataList.where_operator.AND,
                                              'items': [('size', DataList.operator.GT, 3),
                                                        {'type' : DataList.where_operator.AND,
                                                         'items': [('size', DataList.operator.LT, 6)]}]}}).data
        self.assertEqual(list_9, 2, 'list should contain int 2')  # disk 4 and 5
        list_10 = DataList(key   = 'list_10',
                           query = {'object': Disk,
                                    'data'  : DataList.select.COUNT,
                                    'query' : {'type': DataList.where_operator.OR,
                                               'items': [('size', DataList.operator.LT, 3),
                                                         {'type': DataList.where_operator.OR,
                                                          'items': [('size', DataList.operator.GT, 6)]}]}}).data
        self.assertGreaterEqual(list_10, 16, 'list should contain >= 16')  # at least disk 0, 1, 2, 7, 8, 9, 10-19
        list_11 = DataList(key   = 'list_11',
                           query = {'object': Disk,
                                    'data'  : DataList.select.COUNT,
                                    'query' : {'type': DataList.where_operator.AND,
                                               'items': [('storage.name', DataList.operator.EQUALS, 'machine')]}}).data
        self.assertEqual(list_11, 10, 'list should contain int 10')  # disk 10-19
        for disk in machine.stored_disks:
            disk.delete()
        for disk in machine.disks:
            disk.delete()
        machine.delete()

    def test_invalidpropertyassignment(self):
        disk = Disk()
        disk.size = 100
        with self.assertRaises(TypeError):
            disk.machine = Disk()
        disk.delete()

    def test_recursive(self):
        machine = Machine()
        machine.name = 'original'
        machine.save()
        machine2 = Machine()
        machine2.save()
        diskx = Disk()
        diskx.name = 'storage_test'
        diskx.storage = machine2
        diskx.save()
        machine2.delete()  # Creating an orphaned object
        for i in xrange(0, 10):
            disk = Disk()
            disk.name = 'test_%d' % i
            if i % 2:
                disk.machine = machine
            else:
                disk.machine = machine
                self.assertEqual(disk.machine.name, 'original', 'child should be set')
                disk.machine = None
                self.assertIsNone(disk.machine, 'child should be cleared')
            disk.save()
        counter = 1
        for disk in machine.disks:
            disk.size = counter
            counter += 1
        machine.save(recursive=True)
        disk = Disk(machine.disks[0].guid)
        self.assertEqual(disk.size, 1, 'lists should be saved recursively')
        disk.machine.name = 'mtest'
        disk.save(recursive=True)
        machine2 = Machine(machine.guid)
        self.assertEqual(machine2.disks[1].size, 2, 'lists should be saved recursively')
        self.assertEqual(machine2.name, 'mtest', 'properties should be saved recursively')
        for disk in machine.disks:
            disk.delete()
        machine.delete()
        diskx.delete()

    def test_descriptors(self):
        with self.assertRaises(RuntimeError):
            descriptor = Descriptor().descriptor
        with self.assertRaises(RuntimeError):
            value = Descriptor().get_object()

    def test_relationcache(self):
        machine = Machine()
        machine.name = 'machine'
        machine.save()
        disk1 = Disk()
        disk1.name = 'disk1'
        disk1.save()
        disk2 = Disk()
        disk2.name = 'disk2'
        disk2.save()
        disk3 = Disk()
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
        disk1.delete()
        disk2.delete()
        disk3.delete()
        machine.delete()

    def test_datalistactions(self):
        machine = Machine()
        machine.name = 'machine'
        machine.save()
        disk1 = Disk()
        disk1.name = 'disk1'
        disk1.machine = machine
        disk1.save()
        disk2 = Disk()
        disk2.name = 'disk2'
        disk2.machine = machine
        disk2.save()
        disk3 = Disk()
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
        for disk in machine.disks:
            disk.delete()
        machine.delete()