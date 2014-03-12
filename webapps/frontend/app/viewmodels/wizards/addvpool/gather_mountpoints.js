// Copyright 2014 CloudFounders NV
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
/*global define */
define([
    'jquery', 'knockout',
    '../../containers/vmachine', './data'
], function($, ko, VMachine, data) {
    "use strict";
    return function() {
        var self = this;

        // Variables
        self.data = data;

        // Computed
        self.canContinue = ko.computed(function() {
            var valid = true, reasons = [], fields = [];
            $.each(self.data.vsrs(), function(index, vsr) {
                if (self.data.mtptCache() === vsr.mountpointCache() && $.inArray('cache', fields) === -1) {
                    valid = false;
                    fields.push('cache');
                    reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.mtptinuse', { what: $.t('ovs:generic.cachefs') }));
                }
                if (self.data.mtptDFS() === vsr.mountpointDFS() && $.inArray('dfs', fields) === -1) {
                    valid = false;
                    fields.push('dfs');
                    reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.mtptinuse', { what: $.t('ovs:generic.dfs') }));
                }
                if (self.data.mtptMD() === vsr.mountpointMD() && $.inArray('md', fields) === -1) {
                    valid = false;
                    fields.push('md');
                    reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.mtptinuse', { what: $.t('ovs:generic.mdfs') }));
                }
                if (self.data.mtptTemp() === vsr.mountpointTemp() && $.inArray('temp', fields) === -1) {
                    valid = false;
                    fields.push('temp');
                    reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.mtptinuse', { what: $.t('ovs:generic.tempfs') }));
                }
                if ((self.data.mtptDFS() === vsr.mountpointCache() || self.data.mtptDFS() === vsr.mountpointMD() ||
                        self.data.mtptDFS() === vsr.mountpointTemp()) && $.inArray('dfs', fields) === -1) {
                    valid = false;
                    fields.push('dfs');
                    reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.dfsexclusive'));
                }
                if ($.inArray(self.data.vRouterPort(), [vsr.port() - 1, vsr.port(), vsr.port() + 1]) !== -1 && $.inArray('port', fields) === -1) {
                    valid = false;
                    fields.push('port');
                    reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.portinuse'));
                }
            });
            if ((self.data.mtptDFS() === self.data.mtptCache() || self.data.mtptDFS() === self.data.mtptMD() ||
                    self.data.mtptDFS() === self.data.mtptTemp()) && $.inArray('dfs', fields) === -1) {
                valid = false;
                fields.push('dfs');
                reasons.push($.t('ovs:wizards.addvpool.gathermountpoints.dfsnotshared'));
            }
            return { value: valid, reasons: reasons, fields: fields };
        });

        // Durandal
        self.activate = function() {

        };
    };
});
