import time
from unittest import TestCase
from ovs.dal.hybrids.vdisk import vDisk
from ovs.dal.hybrids.vmachine import vMachine
from ovs.dal.datalist import DataList


class LotsOfObjects(TestCase):
    def test_lotsofobjects(self):
        print 'start test'
        print 'start loading data'
        start = time.time()
        mguids = []
        for i in xrange(0, 100):
            machine = vMachine()
            machine.name = 'machine_%d' % i
            machine.save()
            mguids.append(machine.guid)
            for ii in xrange(0, 100):
                disk = vDisk()
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
            machine = vMachine(mguids[i])
            self.assertEqual(len(machine.disks), 100, 'Not all disks were retreived')
            seconds_passed = (time.time() - start)
            itemspersec = ((i + 1) * 10000.0) / seconds_passed
            print '* machine %d/100 (filtering %s disks per second)' % (i, str(itemspersec))
        print 'completed'

        print 'start cached queries'
        start = time.time()
        for i in xrange(0, 100):
            machine = vMachine(mguids[i])
            self.assertEqual(len(machine.disks), 100, 'Not all disks were retreived')
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds' % seconds_passed

        print 'start full query on disk property'
        start = time.time()
        amount = DataList(key   = 'size_between_4k_7k',
                          query = {'object': vDisk,
                                   'data': DataList.select.COUNT,
                                   'query': {'type': DataList.where_operator.AND,
                                             'items': [('size', DataList.operator.GT, 4000),
                                                       ('size', DataList.operator.LT, 7000)]}}).data
        self.assertEqual(amount, 2900, 'Correct number of disks should be found. Found: %s' % str(amount))
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds (filtering %d disks per second)' % (seconds_passed, (10000.0 / seconds_passed))

        print 'cleaning up'
        start = time.time()
        for i in xrange(0, 100):
            machine = vMachine(mguids[i])
            for disk in machine.disks:
                disk.delete()
            machine.delete()
        seconds_passed = (time.time() - start)
        print 'completed in %d seconds' % seconds_passed