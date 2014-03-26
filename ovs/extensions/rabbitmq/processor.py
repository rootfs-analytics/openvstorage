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
Contains the process method for processing rabbitmq messages
"""

from celery.task.control import revoke
from ovs.dal.lists.volumestoragerouterlist import VolumeStorageRouterList
from ovs.lib.vdisk import VDiskController
from ovs.lib.vmachine import VMachineController
from ovs.lib.vpool import VPoolController
from ovs.extensions.storage.volatilefactory import VolatileFactory
from ovs.plugin.provider.configuration import Configuration


def process(queue, body):
    """
    Processes the actual received body
    """
    if queue == Configuration.get('ovs.core.broker.volumerouter.queue'):
        import json
        import volumedriver.storagerouter.EventMessages_pb2 as EventMessages
        cache = VolatileFactory.get_client()

        data = EventMessages.EventMessage().FromString(body)

        # Possible special tags used as `arguments` key:
        # - [NODE_ID]: Replaced by the vsrid as reported by the event
        # - [CLUSTER_ID]: Replaced by the clusterid as reported by the event
        # Possible deduping key tags:
        # - [EVENT_NAME]: The name of the eventmessage type
        # - [TASK_NAME]: Task method name
        # - [<argument value>]: Any value of the `arguments` dictionary.

        mapping = {EventMessages.EventMessage.VolumeDelete:
                   {'property': 'volume_delete',
                    'task': VDiskController.delete_from_voldrv,
                    'arguments': {'name': 'volumename'}},
                   EventMessages.EventMessage.VolumeResize:
                   {'property': 'volume_resize',
                    'task': VDiskController.resize_from_voldrv,
                    'arguments': {'name': 'volumename',
                                  'size': 'volumesize',
                                  'path': 'volumepath',
                                  '[NODE_ID]': 'vsrid'}},
                   EventMessages.EventMessage.VolumeRename:
                   {'property': 'volume_rename',
                    'task': VDiskController.rename_from_voldrv,
                    'arguments': {'name': 'volumename',
                                  'old_path': 'volume_old_path',
                                  'new_path': 'volume_new_path',
                                  '[NODE_ID]': 'vsrid'}},
                   EventMessages.EventMessage.FileCreate:
                   {'property': 'file_create',
                    'task': VMachineController.update_from_voldrv,
                    'arguments': {'path': 'name',
                                  '[NODE_ID]': 'vsrid'},
                    'options': {'delay': 3,
                                'dedupe': True,
                                'dedupe_key': '[TASK_NAME]_[name]_[vsrid]'}},
                   EventMessages.EventMessage.FileWrite:
                   {'property': 'file_write',
                    'task': VMachineController.update_from_voldrv,
                    'arguments': {'path': 'name',
                                  '[NODE_ID]': 'vsrid'},
                    'options': {'delay': 3,
                                'dedupe': True,
                                'dedupe_key': '[TASK_NAME]_[name]_[vsrid]'}},
                   EventMessages.EventMessage.FileDelete:
                   {'property': 'file_delete',
                    'task': VMachineController.delete_from_voldrv,
                    'arguments': {'path': 'name',
                                  '[NODE_ID]': 'vsrid'}},
                   EventMessages.EventMessage.FileRename:
                   {'property': 'file_rename',
                    'task': VMachineController.rename_from_voldrv,
                    'arguments': {'old_path': 'old_name',
                                  'new_path': 'new_name',
                                  '[NODE_ID]': 'vsrid'},
                    'options': {'delay': 3,
                                'dedupe': True,
                                'dedupe_key': '[TASK_NAME]_[new_name]_[vsrid]',
                                'execonvsa': True}},
                   EventMessages.EventMessage.UpAndRunning:
                   {'property': 'up_and_running',
                    'task': VPoolController.mountpoint_available_from_voldrv,
                    'arguments': {'mountpoint': 'mountpoint',
                                  '[NODE_ID]': 'vsrid'},
                    'options': {'execonvsa': True}}}

        if data.type in mapping:
            task = mapping[data.type]['task']
            data_container = getattr(data, mapping[data.type]['property'])
            kwargs = {}
            delay = 0
            routing_key = 'generic'
            for field, target in mapping[data.type]['arguments'].iteritems():
                if field == '[NODE_ID]':
                    kwargs[target] = data.node_id
                elif field == '[CLUSTER_ID]':
                    kwargs[target] = data.cluster_id
                else:
                    kwargs[target] = getattr(data_container, field)
            if 'options' in mapping[data.type]:
                options = mapping[data.type]['options']
                if options.get('execonvsa', False):
                    vsr = VolumeStorageRouterList.get_by_vsrid(data.node_id)
                    if vsr is not None:
                        routing_key = 'vsa.{0}'.format(
                            vsr.serving_vmachine.machineid)
                delay = options.get('delay', 0)
                dedupe = options.get('dedupe', False)
                dedupe_key = options.get('dedupe_key', None)
                if dedupe is True and dedupe_key is not None:  # We can't dedupe without a key
                    key = dedupe_key
                    key = key.replace('[EVENT_NAME]', data.type.__class__.__name__)
                    key = key.replace('[TASK_NAME]', task.__class__.__name__)
                    for kwarg_key in kwargs:
                        key = key.replace('[{0}]'.format(kwarg_key), kwargs[kwarg_key])
                    key = key.replace(' ', '_')
                    task_id = cache.get(key)
                    if task_id:
                        # Key exists, task was already scheduled
                        # If task is already running, the revoke message will
                        # be ignored
                        revoke(task_id)
                    async_result = task.s(**kwargs).apply_async(
                        countdown=delay,
                        routing_key=routing_key
                    )
                    cache.set(key, async_result.id, 600)  # Store the task id
                    new_task_id = async_result.id
                else:
                    async_result = task.s(**kwargs).apply_async(
                        countdown=delay,
                        routing_key=routing_key
                    )
                    new_task_id = async_result.id
            else:
                async_result = task.delay(**kwargs)
                new_task_id = async_result.id
            print '[{0}] {1}({2}) started on {3} with taskid {4}. Delay: {5}s'.format(
                queue,
                task.__name__,
                json.dumps(kwargs),
                routing_key,
                new_task_id,
                delay
            )
        else:
            raise RuntimeError('Type %s is not yet supported' % str(data.type))
    else:
        raise NotImplementedError(
            'Queue {} is not yet implemented'.format(queue))
