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
ScheduledTaskController module
"""

from celery.schedules import crontab
import copy
import time
import os
import traceback
from time import mktime
from datetime import datetime
from ovs.plugin.provider.configuration import Configuration
from ovs.celery_run import celery
from ovs.lib.vmachine import VMachineController
from ovs.lib.vdisk import VDiskController
from ovs.lib.helpers.decorators import ensure_single
from ovs.dal.lists.vmachinelist import VMachineList
from ovs.dal.lists.vdisklist import VDiskList
from ovs.dal.lists.loglist import LogList
from ovs.extensions.db.arakoon.ArakoonManagement import ArakoonManagementEx
from volumedriver.scrubber.scrubber import Scrubber
from ovs.log.logHandler import LogHandler

_storagedriver_scrubber = Scrubber()
logger = LogHandler('lib', name='scheduled tasks')


class ScheduledTaskController(object):
    """
    This controller contains all scheduled task code. These tasks can be
    executed at certain intervals and should be self-containing
    """

    @staticmethod
    @celery.task(name='ovs.scheduled.snapshotall', bind=True, schedule=crontab(minute='0', hour='2-22'))
    @ensure_single(['ovs.scheduled.snapshotall', 'ovs.scheduled.deletescrubsnapshots'])
    def snapshot_all_vms():
        """
        Snapshots all VMachines
        """
        logger.info('[SSA] started')
        success = []
        fail = []
        machines = VMachineList.get_customer_vmachines()
        for machine in machines:
            try:
                VMachineController.snapshot(machineguid=machine.guid,
                                            label='',
                                            is_consistent=False,
                                            is_automatic=True)
                success.append(machine.guid)
            except:
                fail.append(machine.guid)
        logger.info('[SSA] {0} vMachines were snapshotted, {1} failed.'.format(
            len(success), len(fail)
        ))

    @staticmethod
    @celery.task(name='ovs.scheduled.deletescrubsnapshots', bind=True, schedule=crontab(minute='30', hour='0'))
    @ensure_single(['ovs.scheduled.deletescrubsnapshots'])
    def deletescrubsnapshots(timestamp=None):
        """
        Delete snapshots & scrubbing policy

        Implemented delete snapshot policy:
        < 1d | 1d bucket | 1 | best of bucket   | 1d
        < 1w | 1d bucket | 6 | oldest of bucket | 7d = 1w
        < 1m | 1w bucket | 3 | oldest of bucket | 4w = 1m
        > 1m | delete
        """

        logger.info('Delete snapshots started')

        day = 60 * 60 * 24
        week = day * 7

        # Calculate bucket structure
        if timestamp is None:
            timestamp = time.time()
        offset = int(mktime(datetime.fromtimestamp(timestamp).date().timetuple())) - day
        buckets = []
        # Buckets first 7 days: [0-1[, [1-2[, [2-3[, [3-4[, [4-5[, [5-6[, [6-7[
        for i in xrange(0, 7):
            buckets.append({'start': offset - (day * i),
                            'end': offset - (day * (i + 1)),
                            'type': '1d',
                            'snapshots': []})
        # Week buckets next 3 weeks: [7-14[, [14-21[, [21-28[
        for i in xrange(1, 4):
            buckets.append({'start': offset - (week * i),
                            'end': offset - (week * (i + 1)),
                            'type': '1w',
                            'snapshots': []})
        buckets.append({'start': offset - (week * 4),
                        'end': 0,
                        'type': 'rest',
                        'snapshots': []})

        # Place all snapshots in bucket_chains
        bucket_chains = []
        for vmachine in VMachineList.get_customer_vmachines():
            if any(vd.info['object_type'] in ['BASE'] for vd in vmachine.vdisks):
                bucket_chain = copy.deepcopy(buckets)
                for snapshot in vmachine.snapshots:
                    timestamp = int(snapshot['timestamp'])
                    for bucket in bucket_chain:
                        if bucket['start'] >= timestamp > bucket['end']:
                            for diskguid, snapshotguid in snapshot['snapshots'].iteritems():
                                bucket['snapshots'].append({'timestamp': timestamp,
                                                            'snapshotid': snapshotguid,
                                                            'diskguid': diskguid,
                                                            'is_consistent': snapshot['is_consistent']})
                bucket_chains.append(bucket_chain)

        for vdisk in VDiskList.get_without_vmachine():
            if vdisk.info['object_type'] in ['BASE']:
                bucket_chain = copy.deepcopy(buckets)
                for snapshot in vdisk.snapshots:
                    timestamp = int(snapshot['timestamp'])
                    for bucket in bucket_chain:
                        if bucket['start'] >= timestamp > bucket['end']:
                            bucket['snapshots'].append({'timestamp': timestamp,
                                                        'snapshotid': snapshot['guid'],
                                                        'diskguid': vdisk.guid,
                                                        'is_consistent': snapshot['is_consistent']})
                bucket_chains.append(bucket_chain)

        # Clean out the snapshot bucket_chains, we delete the snapshots we want to keep
        # And we'll remove all snapshots that remain in the buckets
        for bucket_chain in bucket_chains:
            first = True
            for bucket in bucket_chain:
                if first is True:
                    best = None
                    for snapshot in bucket['snapshots']:
                        if best is None:
                            best = snapshot
                        # Consistent is better than inconsistent
                        elif snapshot['is_consistent'] and not best['is_consistent']:
                            best = snapshot
                        # Newer (larger timestamp) is better than older snapshots
                        elif snapshot['is_consistent'] == best['is_consistent'] and \
                                snapshot['timestamp'] > best['timestamp']:
                            best = snapshot
                    bucket['snapshots'] = [s for s in bucket['snapshots'] if
                                           s['timestamp'] != best['timestamp']]
                    first = False
                elif bucket['end'] > 0:
                    oldest = None
                    for snapshot in bucket['snapshots']:
                        if oldest is None:
                            oldest = snapshot
                        # Older (smaller timestamp) is the one we want to keep
                        elif snapshot['timestamp'] < oldest['timestamp']:
                            oldest = snapshot
                    bucket['snapshots'] = [s for s in bucket['snapshots'] if
                                           s['timestamp'] != oldest['timestamp']]

        # Delete obsolete snapshots
        for bucket_chain in bucket_chains:
            for bucket in bucket_chain:
                for snapshot in bucket['snapshots']:
                    VDiskController.delete_snapshot(diskguid=snapshot['diskguid'],
                                                    snapshotid=snapshot['snapshotid'])

        logger.info('Delete snapshots finished')
        logger.info('Scrubbing started')

        vdisks = []
        for vmachine in VMachineList.get_customer_vmachines():
            for vdisk in vmachine.vdisks:
                if vdisk.info['object_type'] in ['BASE']:
                    vdisks.append(vdisk)
        for vdisk in VDiskList.get_without_vmachine():
            if vdisk.info['object_type'] in ['BASE']:
                vdisks.append(vdisk)

        total = 0
        failed = 0
        for vdisk in vdisks:
            work_units = vdisk.storagedriver_client.get_scrubbing_workunits(str(vdisk.volume_id))
            for work_unit in work_units:
                try:
                    total += 1
                    scrubbing_result = _storagedriver_scrubber.scrub(work_unit, vdisk.vpool.mountpoint_temp)
                    vdisk.storagedriver_client.apply_scrubbing_result(scrubbing_result)
                except:
                    failed += 1
                    logger.info('Failed scrubbing work unit for volume {}'.format(
                        vdisk.volume_id
                    ))

        logger.info('Scrubbing finished. {} out of {} items failed.'.format(
            failed, total
        ))

    @staticmethod
    @celery.task(name='ovs.scheduled.collapse_arakoon', bind=True, schedule=crontab(minute='30', hour='0'))
    @ensure_single(['ovs.scheduled.collapse_arakoon'])
    def collapse_arakoon():
        logger.info('Starting arakoon collapse')
        arakoon_dir = os.path.join(Configuration.get('ovs.core.cfgdir'), 'arakoon')
        arakoon_clusters = map(lambda directory: os.path.basename(directory.rstrip(os.path.sep)),
                               os.walk(arakoon_dir).next()[1])
        for cluster in arakoon_clusters:
            logger.info('  Collapsing cluster: {}'.format(cluster))
            cluster_instance = ArakoonManagementEx().getCluster(cluster)
            for node in cluster_instance.listNodes():
                logger.info('    Collapsing node: {}'.format(node))
                try:
                    cluster_instance.remoteCollapse(node, 2)  # Keep 2 tlogs
                except Exception as e:
                    logger.info(
                        'Error during collapsing cluster {} node {}: {}\n{}'.format(
                            cluster, node, str(e), traceback.format_exc()
                        )
                    )
        logger.info('Arakoon collapse finished')

    @staticmethod
    @celery.task(name='ovs.scheduled.clean_logs', bind=True, schedule=crontab(minute='30', hour='0'))
    @ensure_single(['ovs.scheduled.clean_logs'])
    def clean_logs():
        """
        Cleans audit trail logs
        """
        days = int(Configuration.get('ovs.core.audittrails.keep'))
        mark = time.time() - days * 24 * 60 * 60
        for log in LogList.get_logs():
            if log.time < mark:
                log.delete()
