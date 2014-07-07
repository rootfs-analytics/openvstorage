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
This package contains the openstack cinder driver

Tested on devstack
/opt/devstack# cinder --version
1.0.9.11
/opt/devstack# nova --version
2.17.0.177
/opt/devstack# glance --version
0.12.0.115

Copy the ovs_volume_driver.py to /opt/stack/cinder/cinder/volume/drivers/ovs_volume_driver.py

See also: http://confluence.cloudfounders.com/display/RES/POC+-+OVS+Cinder+driver+%28part+1%29            
"""
