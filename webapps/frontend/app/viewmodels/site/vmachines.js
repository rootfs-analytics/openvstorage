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
    '../containers/vmachine', '../containers/vpool', '../wizards/rollback/index', '../wizards/snapshot/index'
], function($, app, dialog, ko, shared, generic, Refresher, api, VMachine, VPool, RollbackWizard, SnapshotWizard) {
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
        self.vMachineHeaders = [
            { key: 'name',         value: $.t('ovs:generic.name'),       width: 150       },
            { key: 'vpool',        value: $.t('ovs:generic.vpool'),      width: 150       },
            { key: 'vsa',          value: $.t('ovs:generic.vsa'),        width: 150       },
            { key: undefined,      value: $.t('ovs:generic.vdisks'),     width: 60        },
            { key: 'storedData',   value: $.t('ovs:generic.storeddata'), width: 110       },
            { key: 'cacheRatio',   value: $.t('ovs:generic.cache'),      width: 100       },
            { key: 'iops',         value: $.t('ovs:generic.iops'),       width: 55        },
            { key: 'readSpeed',    value: $.t('ovs:generic.read'),       width: 100       },
            { key: 'writeSpeed',   value: $.t('ovs:generic.write'),      width: 100       },
            { key: 'failoverMode', value: $.t('ovs:generic.focstatus'),  width: undefined },
            { key: undefined,      value: $.t('ovs:generic.actions'),    width: 100       }
        ];
        self.vMachines = ko.observableArray([]);
        self.vPoolCache = {};
        self.vsaCache = {};
        self.vMachinesInitialLoad = ko.observable(true);

        // Variables
        self.loadVMachinesHandle = undefined;

        // Functions
        self.fetchVMachines = function(full) {
            full = full || false;
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.loadVMachinesHandle)) {
                    var query = {
                            query: {
                                type: 'AND',
                                items: [['is_internal', 'EQUALS', false],
                                        ['is_vtemplate', 'EQUALS', false],
                                        ['status', 'NOT_EQUALS', 'CREATED']]
                            }
                        }, filter = {};
                    if (full) {
                        filter.full = true;
                    }
                    self.loadVMachinesHandle = api.post('vmachines/filter', query, filter)
                        .done(function(data) {
                            var i, guids = [], vmdata = {};
                            for (i = 0; i < data.length; i += 1) {
                                guids.push(data[i].guid);
                                vmdata[data[i].guid] = data[i];
                            }
                            generic.crossFiller(
                                guids, self.vMachines,
                                function(guid) {
                                    var vm = new VMachine(guid);
                                    if (full) {
                                        vm.fillData(vmdata[guid]);
                                    }
                                    return vm;
                                }, 'guid'
                            );
                            self.vMachinesInitialLoad(false);
                            deferred.resolve();
                        })
                        .fail(deferred.reject);
                } else {
                    deferred.reject();
                }
            }).promise();
        };
        self.loadVMachine = function(vm, reduced) {
            reduced = reduced || false;
            return $.Deferred(function(deferred) {
                var calls = [vm.load(reduced)];
                if (!reduced) {
                    calls.push(vm.fetchVSAGuids());
                    calls.push(vm.fetchVPoolGuids());
                }
                $.when.apply($, calls)
                    .done(function() {
                        // Merge in the VSAs
                        generic.crossFiller(
                            vm.vSAGuids, vm.vsas,
                            function(guid) {
                                if (!self.vsaCache.hasOwnProperty(guid)) {
                                    var vm = new VMachine(guid);
                                    vm.load();
                                    self.vsaCache[guid] = vm;
                                }
                                return self.vsaCache[guid];
                            }, 'guid'
                        );
                        // Merge in the vPools
                        generic.crossFiller(
                            vm.vPoolGuids, vm.vpools,
                            function(guid) {
                                if (!self.vPoolCache.hasOwnProperty(guid)) {
                                    var vp = new VPool(guid);
                                    vp.load();
                                    self.vPoolCache[guid] = vp;
                                }
                                return self.vPoolCache[guid];
                            }, 'guid'
                        );
                        // (Re)sort vMachines
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
            self.sortTimeout = window.setTimeout(function() { generic.advancedSort(self.vMachines, ['name', 'guid']); }, 250);
        };
        self.rollback = function(guid) {
            var i, vms = self.vMachines(), vm;
            for (i = 0; i < vms.length; i += 1) {
                if (vms[i].guid() === guid) {
                    vm = vms[i];
                }
            }
            if (vm !== undefined && !vm.isRunning()) {
                dialog.show(new RollbackWizard({
                    modal: true,
                    type: 'vmachine',
                    guid: guid
                }));
            }
        };
        self.snapshot = function(guid) {
            dialog.show(new SnapshotWizard({
                modal: true,
                machineguid: guid
            }));
        };
        self.setAsTemplate = function(guid) {
            var i, vms = self.vMachines(), vm;
            for (i = 0; i < vms.length; i += 1) {
                if (vms[i].guid() === guid) {
                    vm = vms[i];
                }
            }
            if (vm !== undefined && !vm.isRunning()) {
                app.showMessage(
                        $.t('ovs:vmachines.setastemplate.warning'),
                        $.t('ovs:vmachines.setastemplate.title', { what: vm.name() }),
                        [$.t('ovs:vmachines.setastemplate.no'), $.t('ovs:vmachines.setastemplate.yes')]
                    )
                    .done(function(answer) {
                        if (answer === $.t('ovs:vmachines.setastemplate.yes')) {
                            generic.alertInfo(
                                $.t('ovs:vmachines.setastemplate.marked'),
                                $.t('ovs:vmachines.setastemplate.markedmsg', { what: vm.name() })
                            );
                            api.post('vmachines/' + vm.guid() + '/set_as_template')
                                .then(self.shared.tasks.wait)
                                .done(function() {
                                    self.vMachines.destroy(vm);
                                    generic.alertSuccess(
                                        $.t('ovs:vmachines.setastemplate.done'),
                                        $.t('ovs:vmachines.setastemplate.donemsg', { what: vm.name() })
                                    );
                                })
                                .fail(function(error) {
                                    generic.alertError(
                                        $.t('ovs:generic.error'),
                                        $.t('ovs:generic.messages.errorwhile', {
                                            context: 'error',
                                            what: $.t('ovs:vmachines.setastemplate.errormsg', { what: vm.name() }),
                                            error: error
                                        })
                                    );
                                });
                        }
                    });
            }
        };

        // Durandal
        self.activate = function() {
            self.refresher.init(self.fetchVMachines, 5000);
            self.shared.footerData(self.vMachines);

            self.fetchVMachines(true)
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
