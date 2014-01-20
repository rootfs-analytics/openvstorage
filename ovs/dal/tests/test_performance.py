# license see http://www.openvstorage.com/licenses/opensource/
"""
Performance unittest module
"""
import time
from unittest import TestCase
from ovs.dal.hybrids.t_testdisk import TestDisk
from ovs.dal.hybrids.t_testmachine import TestMachine
from ovs.dal.datalist import DataList


class LotsOfObjects(TestCase):
    """
    Executes a performance test by working with a large set of objects
    """

    def test_lotsofobjects(self):
        """
        A test creating, linking and querying a lot of objects
        """
        print 'start test'
        print 'start loading data'
        start = time.time()
        mguids = []
        for i in xrange(0, 100):
            machine = TestMachine()
            machine.name = 'machine_%d' % i
            machine.save()
            mguids.append(machine.guid)
            for ii in xrange(0, 100):
                disk = TestDisk()
                disk.name = 'disk_%d_%d' % (i, ii)
                disk.size = ii * 100
                disk.machine = machine
                disk.save()
            seconds_passed = (time.time() - start)
            itemspersec = ((i + 1) * 100.0) / seconds_passed
            print '* machine %d/100 (creating %s disks per second)' % (i, str(itemspersec))
        print 'loading done'

        print 'start queries'
        start = time.time()
        for i in xrange(0, 100):
            machine = TestMachine(mguids[i])
            self.assertEqual(len(machine.disks), 100, 'Not all disks were retreived')
            seconds_passed = (time.time() - start)
            itemspersec = ((i + 1) * 10000.0) / seconds_passed
            print '* machine %d/100 (filtering %s disks per second)' % (i, str(itemspersec))
        print 'completed'

        print 'start cached queries'
        start = time.time()
        for i in xrange(0, 100):
            machine = TestMachine(mguids[i])
            self.assertEqual(len(machine.disks), 100, 'Not all disks were retreived')
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds' % seconds_passed

        print 'start full query on disk property'
        start = time.time()
        amount = DataList({'object': TestDisk,
                           'data': DataList.select.COUNT,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('size', DataList.operator.GT, 4000),
                                               ('size', DataList.operator.LT, 7000)]}}).data
        self.assertEqual(amount, 2900,
                         'Correct number of disks should be found. Found: %s' % str(amount))
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds (filtering %d disks per second)' \
              % (seconds_passed, (10000.0 / seconds_passed))

        print 'cleaning up'
        start = time.time()
        for i in xrange(0, 100):
            machine = TestMachine(mguids[i])
            for disk in machine.disks:
                disk.delete()
            machine.delete()
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds' % seconds_passed

    def test_pkstretching(self):
        """
        Creating lots of object of a single type, testing the primary key list limits
        """
        print 'start test'
        start = time.time()
        machine_guids = []
        for i in xrange(0, 50000):
            machine = TestMachine()
            machine.name = 'Machine {0}'.format(i)
            machine.save()
            machine_guids.append(machine.guid)
            keys = DataList._get_pks(machine._namespace, machine._name)
            self.assertEqual(len(machine_guids), len(list(keys)), 'The primary key list should be correct')
            if i % 100 == 0:
                print '  progress: {0}'.format(i)
        for guid in machine_guids:
            machine = TestMachine(guid)
            machine.delete()
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds' % seconds_passed
