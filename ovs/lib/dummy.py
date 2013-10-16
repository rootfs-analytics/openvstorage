#from __future__ import absolute_import

import time
import logging

from ovs.celery import celery

class dummy(object):
    #celery = Celery('tasks')
    #celery.config_from_object('celeryconfig')
    
    @celery.task(name='ovs.dummy.echo')
    def echo(msg):
        logging.debug('echo(%s,%s)' % msg)
        return msg
    
    @celery.task(name='ovs.dummy.sleep')
    def sleep(seconds=None):
        if not seconds:
            seconds = random.randrange(1,60)
        time.sleep(seconds)
        return True