﻿// Copyright 2014 CloudFounders NV
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
/*global define, window */
define([
    'jquery', 'durandal/app', 'plugins/dialog', 'knockout',
    'ovs/shared', 'ovs/generic', 'ovs/refresher', 'ovs/api',
    '../containers/vdisk', '../containers/vmachine', '../containers/vpool', '../wizards/rollback/index'
], function($, app, dialog, ko, shared, generic, Refresher, api, VDisk, VMachine, VPool, RollbackWizard) {
    "use strict";
    return function() {
        var self = this;

        // System
        self.shared      = shared;
        self.guard       = { authenticated: true };
        self.refresher   = new Refresher();
        self.widgets     = [];
        self.updateSort  = false;
        self.sortTimeout = undefined;

        // Data
        self.vDiskHeaders = [
            { key: 'name',         value: $.t('ovs:generic.name'),         width: 150       },
            { key: 'vmachine',     value: $.t('ovs:generic.vmachine'),     width: 110       },
            { key: 'vpool',        value: $.t('ovs:generic.vpool'),        width: 110       },
            { key: 'vsa',          value: $.t('ovs:generic.vsa'),          width: 110       },
            { key: 'size',         value: $.t('ovs:generic.size'),         width: 100       },
            { key: 'storedData',   value: $.t('ovs:generic.storeddata'),   width: 110       },
            { key: 'cacheRatio',   value: $.t('ovs:generic.cache'),        width: 100       },
            { key: 'iops',         value: $.t('ovs:generic.iops'),         width: 55        },
            { key: 'readSpeed',    value: $.t('ovs:generic.read'),         width: 100       },
            { key: 'writeSpeed',   value: $.t('ovs:generic.write'),        width: 100       },
            { key: 'failoverMode', value: $.t('ovs:generic.focstatus'),    width: undefined },
            { key: undefined,      value: $.t('ovs:generic.actions'),      width: 80        }
        ];
        self.vDisks = ko.observableArray([]);
        self.vMachineCache = {};
        self.vPoolCache = {};
        self.vSACache = {};
        self.vDisksInitialLoad = ko.observable(true);

        // Variables
        self.loadVDisksHandle = undefined;

        // Functions
        self.load = function(full) {
            full = full || false;
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.loadVDisksHandle)) {
                    var filter = {};
                    if (full) {
                        filter.full = true;
                    }
                    self.loadVDisksHandle = api.get('vdisks', {}, filter)
                        .done(function(data) {
                            var i, guids = [], vddata = {};
                            for (i = 0; i < data.length; i += 1) {
                                guids.push(data[i].guid);
                                vddata[data[i].guid] = data[i];
                            }
                            generic.crossFiller(
                                guids, self.vDisks,
                                function(guid) {
                                    var vd = new VDisk(guid);
                                    if (full) {
                                        vd.fillData(vddata[guid]);
                                    }
                                    return vd;
                                }, 'guid'
                            );
                            self.vDisksInitialLoad(false);
                            deferred.resolve();
                        })
                        .fail(deferred.reject);
                } else {
                    deferred.reject();
                }
            }).promise();
        };
        self.loadVDisk = function(vdisk, reduced) {
            reduced = reduced || false;
            return $.Deferred(function(deferred) {
                var calls = [vdisk.load()];
                if (!reduced) {
                    calls.push(vdisk.fetchVSAGuid());
                }
                $.when.apply($, calls)
                    .done(function() {
                        var vm, pool,
                            vsaGuid = vdisk.vsaGuid(),
                            vMachineGuid = vdisk.vMachineGuid(),
                            vPoolGuid = vdisk.vpoolGuid();
                        if (vsaGuid && (vdisk.vsa() === undefined || vdisk.vsa().guid() !== vsaGuid)) {
                            if (!self.vSACache.hasOwnProperty(vsaGuid)) {
                                vm = new VMachine(vsaGuid);
                                vm.load();
                                self.vSACache[vsaGuid] = vm;
                            }
                            vdisk.vsa(self.vSACache[vsaGuid]);
                        }
                        if (vMachineGuid && (vdisk.vMachine() === undefined || vdisk.vMachine().guid() !== vMachineGuid)) {
                            if (!self.vMachineCache.hasOwnProperty(vMachineGuid)) {
                                vm = new VMachine(vMachineGuid);
                                vm.load();
                                self.vMachineCache[vMachineGuid] = vm;
                            }
                            vdisk.vMachine(self.vMachineCache[vMachineGuid]);
                        }
                        if (vPoolGuid && (vdisk.vpool() === undefined || vdisk.vpool().guid() !== vPoolGuid)) {
                            if (!self.vPoolCache.hasOwnProperty(vPoolGuid)) {
                                pool = new VPool(vPoolGuid);
                                pool.load();
                                self.vPoolCache[vPoolGuid] = pool;
                            }
                            vdisk.vpool(self.vPoolCache[vPoolGuid]);
                        }
                        // (Re)sort vDisks
                        if (self.updateSort) {
                            self.sort();
                        }
                    })
                    .always(deferred.resolve);
            }).promise();
        };
        self.sort = function() {
            if (self.sortTimeout) {
                window.clearTimeout(self.sortTimeout);
            }
            self.sortTimeout = window.setTimeout(function() { generic.advancedSort(self.vDisks, ['name', 'guid']); }, 250);
        };

        self.rollback = function(guid) {
            var i, vds = self.vDisks(), vd;
            for (i = 0; i < vds.length; i += 1) {
                if (vds[i].guid() === guid) {
                    vd = vds[i];
                }
            }
            if (vd.vMachine() === undefined || !vd.vMachine().isRunning()) {
                dialog.show(new RollbackWizard({
                    modal: true,
                    type: 'vdisk',
                    guid: guid
                }));
            }
        };

        // Durandal
        self.activate = function() {
            self.refresher.init(self.load, 5000);
            self.shared.footerData(self.vDisks);

            self.load(true)
                .always(function() {
                    self.sort();
                    self.updateSort = true;
                    self.refresher.start();
                });
        };
        self.deactivate = function() {
            var i;
            for (i = 0; i < self.widgets.length; i += 2) {
                self.widgets[i].deactivate();
            }
            self.refresher.stop();
            self.shared.footerData(ko.observable());
        };
    };
});
