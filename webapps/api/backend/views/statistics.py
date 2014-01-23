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
Statistics module
"""
import re
import datetime
from backend.serializers.memcached import MemcacheSerializer
from backend.decorators import required_roles, expose
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ovs.extensions.storage.volatilefactory import VolatileFactory
from ovs.plugin.provider.configuration import Configuration


class MemcacheViewSet(viewsets.ViewSet):
    """
    Information about memcache instances
    """
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _get_memcachelocation():
        """
        Get the memcache location from hrd
        """
        return '{}:{}'.format(Configuration.get('ovs.grid.ip'),
                              Configuration.get('ovs.core.memcache.localnode.port'))

    @staticmethod
    def _get_instance(host):
        """
        Returns a class with more information about a given memcache instance
        """
        class Stats:
            """
            Placeholder class for statistics
            """
            pass

        import memcache
        host = memcache._Host(host)
        host.connect()
        host.send_cmd("stats")
        stats = Stats()
        while 1:
            line = host.readline().split(None, 2)
            if line[0] == "END":
                break
            stat, key, value = line
            try:
                # Convert to native type, if possible
                value = int(value)
                if key == "uptime":
                    value = datetime.timedelta(seconds=value)
                elif key == "time":
                    value = datetime.datetime.fromtimestamp(value)
            except ValueError:
                pass
            setattr(stats, key, value)
        host.close_socket()
        return stats

    @staticmethod
    def _add_dal_stats(stats):
        """
        Adds ovs dal statistics to the stats object
        """
        volatile = VolatileFactory.get_client()
        setattr(stats, 'ovs_dal', {})
        keys = ['datalist', 'object_load', 'descriptor', 'relations']
        for key in keys:
            for hittype in ['hit', 'miss']:
                cachekey = 'ovs_stats_cache_%s_%s' % (key, hittype)
                stats.ovs_dal['%s_%s' % (key, hittype)] = volatile.get(cachekey) or 0
    @expose(internal=True)
    @required_roles(['view'])
    def list(self, request, format=None):
        """
        Returns statistics information
        """
        _ = request, format
        match = re.match("([.\w]+:\d+)", MemcacheViewSet._get_memcachelocation())
        if not match:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        stats = MemcacheViewSet._get_instance(match.group(1))
        MemcacheViewSet._add_dal_stats(stats)
        serializer = MemcacheSerializer(stats)
        return Response(serializer.data)

    @expose(internal=True)
    @required_roles(['view'])
    def retrieve(self, request, pk=None, format=None):
        """
        Returns statistics information
        """
        _ = request, format, pk
        match = re.match("([.\w]+:\d+)", MemcacheViewSet._get_memcachelocation())
        if not match:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        stats = MemcacheViewSet._get_instance(match.group(1))
        MemcacheViewSet._add_dal_stats(stats)
        serializer = MemcacheSerializer(stats)
        return Response(serializer.data)
