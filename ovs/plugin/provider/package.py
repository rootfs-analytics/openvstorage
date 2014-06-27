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
This module contains package logic
"""


class Package(object):
    """
    Package class
    """

    def __init__(self):
        """
        Package should be a complete static class
        """
        raise RuntimeError('This class should not be instantiated.')

    is_running = None
    start = None
    stop = None
    get_status = None
    get_versions = None

from ovs.plugin.injection.injector import Injector
Package = Injector.inject(Package)
