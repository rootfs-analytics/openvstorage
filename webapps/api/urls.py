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
Django URL module for main API
"""
from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView

from views import ObtainAuthToken
from backend.views.statistics import MemcacheViewSet
from backend.views.vmachines import VMachineViewSet
from backend.views.pmachines import PMachineViewSet
from backend.views.vpools import VPoolViewSet
from backend.views.vdisks import VDiskViewSet
from backend.views.users import UserViewSet
from backend.views.tasks import TaskViewSet
from backend.views.messaging import MessagingViewSet
from backend.views.branding import BrandingViewSet
from backend.router import OVSRouter


def build_router_urls(api_mode, docs):
    """
    Creates a router instance to generate API urls for Customer and Internal API
    """
    routes = [
        {'prefix': r'users',               'viewset': UserViewSet,      'base_name': 'users'},
        {'prefix': r'tasks',               'viewset': TaskViewSet,      'base_name': 'tasks'},
        {'prefix': r'vpools',              'viewset': VPoolViewSet,     'base_name': 'vpools'},
        {'prefix': r'vmachines',           'viewset': VMachineViewSet,  'base_name': 'vmachines'},
        {'prefix': r'pmachines',           'viewset': PMachineViewSet,  'base_name': 'pmachines'},
        {'prefix': r'vdisks',              'viewset': VDiskViewSet,     'base_name': 'vdisks'},
        {'prefix': r'messages',            'viewset': MessagingViewSet, 'base_name': 'messages'},
        {'prefix': r'branding',            'viewset': BrandingViewSet,  'base_name': 'branding'},
        {'prefix': r'statistics/memcache', 'viewset': MemcacheViewSet,  'base_name': 'memcache'}
    ]
    router = OVSRouter(api_mode, docs)
    for route in routes:
        router.register(**route)
    return router.urls

customer_docs = """
The Customer API can be used for integration or automatisation with 3rd party applications.
"""
internal_docs = """
The Internal API is for **internal use only** (used by the Open vStorage framework) and is subject
to continuous changes without warning. It should not be used by 3rd party applications.
*Unauthorized usage of this API can lead to unexpected results, issues or even data loss*. See
the [Customer API](%(customerapi)s).
"""

urlpatterns = patterns('',
    url(r'^auth/',      ObtainAuthToken.as_view()),
    url(r'^api-auth/',  include('rest_framework.urls', namespace='rest_framework')),
    url(r'^customer/',  include(build_router_urls('customer', customer_docs))),
    url(r'^internal/',  include(build_router_urls('internal', internal_docs))),
    url(r'^$',          RedirectView.as_view(url='customer/')),
)
