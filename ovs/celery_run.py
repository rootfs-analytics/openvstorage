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
Celery entry point module
"""
from __future__ import absolute_import

import sys
sys.path.append('/opt/OpenvStorage')

import os
from ConfigParser import RawConfigParser
from kombu import Queue
from celery import Celery
from celery.signals import task_postrun, worker_process_init
from ovs.lib.messaging import MessageController
from ovs.log.logHandler import LogHandler
from ovs.extensions.storage.volatilefactory import VolatileFactory
from ovs.extensions.storage.persistentfactory import PersistentFactory
from ovs.extensions.generic.system import System
from ovs.plugin.provider.configuration import Configuration

memcache_ini = RawConfigParser()
memcache_ini.read(os.path.join(Configuration.get('ovs.core.cfgdir'), 'memcacheclient.cfg'))
memcache_nodes = [node.strip() for node in memcache_ini.get('main', 'nodes').split(',')]
memcache_servers = map(lambda n: memcache_ini.get(n, 'location'), memcache_nodes)

rmq_ini = RawConfigParser()
rmq_ini.read(os.path.join(Configuration.get('ovs.core.cfgdir'), 'rabbitmqclient.cfg'))
rmq_nodes = [node.strip() for node in rmq_ini.get('main', 'nodes').split(',')]
rmq_servers = map(lambda n: rmq_ini.get(n, 'location'), rmq_nodes)

unique_id = System.get_my_machine_id()

include = []
path = os.path.join(os.path.dirname(__file__), 'lib')
for filename in os.listdir(path):
    if os.path.isfile(os.path.join(path, filename)) and filename.endswith('.py') and filename != '__init__.py':
        name = filename.replace('.py', '')
        include.append('ovs.lib.{0}'.format(name))

celery = Celery('ovs', include=include)

celery.conf.CELERY_RESULT_BACKEND = "cache"
celery.conf.CELERY_CACHE_BACKEND = 'memcached://{0}/'.format(';'.join(memcache_servers))
celery.conf.BROKER_URL = ';'.join(['{0}://{1}:{2}@{3}//'.format(Configuration.get('ovs.core.broker.protocol'),
                                                                Configuration.get('ovs.core.broker.login'),
                                                                Configuration.get('ovs.core.broker.password'),
                                                                server)
                                   for server in rmq_servers])
celery.conf.CELERY_DEFAULT_QUEUE = 'ovs_generic'
celery.conf.CELERY_QUEUES = tuple([Queue('ovs_generic', routing_key='generic.#'),
                                   Queue('ovs_masters', routing_key='masters.#'),
                                   Queue('ovs_{0}'.format(unique_id), routing_key='sr.{0}.#'.format(unique_id))])
celery.conf.CELERY_DEFAULT_EXCHANGE = 'generic'
celery.conf.CELERY_DEFAULT_EXCHANGE_TYPE = 'topic'
celery.conf.CELERY_DEFAULT_ROUTING_KEY = 'generic.default'
celery.conf.CELERY_ACKS_LATE = True          # This, together with the below PREFETCH_MULTIPLIER, makes sure that the
celery.conf.CELERYD_PREFETCH_MULTIPLIER = 1  # workers basically won't be prefetching tasks, to prevent deadlocks
celery.conf.CELERYBEAT_SCHEDULE = {}

loghandler = LogHandler('celery', name='celery')


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """
    Hook for celery postrun event
    """
    _ = sender, task, args, kwargs, kwds
    MessageController.fire(MessageController.Type.TASK_COMPLETE, task_id)


@worker_process_init.connect
def worker_process_init_handler(args=None, kwargs=None, **kwds):
    """
    Hook for process init
    """
    _ = args, kwargs, kwds
    VolatileFactory.store = None
    PersistentFactory.store = None


if __name__ == '__main__':
    celery.start()
