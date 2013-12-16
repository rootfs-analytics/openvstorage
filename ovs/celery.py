# license see http://www.openvstorage.com/licenses/opensource/
"""
Celery entry point module
"""
from __future__ import absolute_import

import sys
sys.path.append('/opt/OpenvStorage')

from celery import Celery
from celery.schedules import crontab
from ovs.logging.logHandler import LogHandler
from JumpScale import j

memcache_ini = j.tools.inifile.open(j.system.fs.joinPaths(j.application.config.get('ovs.core.cfgdir'), 'memcacheclient.cfg'))
nodes = memcache_ini.getValue('main', 'nodes').split(',')
memcache_servers = map(lambda m: memcache_ini.getValue(m, 'location'), nodes)

celery = Celery('ovs',
                include=['ovs.lib.vdisk',
                         'ovs.lib.vmachine',
                         'ovs.lib.messaging',
                         'ovs.lib.scheduledtask',
                         'ovs.extensions.hypervisor.hypervisors.vmware'])

celery.conf.CELERY_RESULT_BACKEND = "cache"
celery.conf.CELERY_CACHE_BACKEND = 'memcached://{}/'.format(';'.join(memcache_servers))
celery.conf.BROKER_URL = '{}://{}:{}@{}:{}//'.format(j.application.config.get('ovs.core.broker.protocol'),
                                                     j.application.config.get('ovs.core.broker.login'), 
                                                     j.application.config.get('ovs.core.broker.password'),
                                                     j.application.config.get('ovs.grid.ip'),
                                                     j.application.config.get('ovs.core.broker.port'))
celery.conf.CELERYBEAT_SCHEDULE = {
    # Snapshot policy
    # > Executes every weekday between 2 and 22 hour, every 15 minutes
    'take-snapshots': {
        'task': 'ovs.scheduled.snapshotall',
        'schedule': crontab(minute='*/15',
                            hour='2-22',
                            day_of_week='mon,tue,wed,thu,fri'),
        'args': [],
    },
}

loghandler = LogHandler('celery.log')

if __name__ == '__main__':
    celery.start()
