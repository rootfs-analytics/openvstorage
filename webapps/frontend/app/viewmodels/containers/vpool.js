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
    'ovs/generic', 'ovs/api',
    'viewmodels/containers/backendtype', 'viewmodels/containers/vdisk', 'viewmodels/containers/vmachine'
], function($, ko, generic, api, BackendType, VDisk, VMachine) {
    "use strict";
    return function(guid) {
        var self = this;

        // Handles
        self.loadHandle          = undefined;
        self.diskHandle          = undefined;
        self.machineHandle       = undefined;
        self.storageRouterHandle = undefined;

        // Observables
        self.loading            = ko.observable(false);
        self.loaded             = ko.observable(false);
        self.guid               = ko.observable(guid);
        self.name               = ko.observable();
        self.size               = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.iops               = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.storedData         = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.cacheHits          = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.cacheMisses        = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatNumber });
        self.readSpeed          = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.writeSpeed         = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.backendWriteSpeed  = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.backendReadSpeed   = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatSpeed });
        self.backendWritten     = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.backendRead        = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.bandwidthSaved     = ko.observable().extend({ smooth: {} }).extend({ format: generic.formatBytes });
        self.backendTypeGuid    = ko.observable();
        self.backendType        = ko.observable();
        self.backendConnection  = ko.observable();
        self.backendLogin       = ko.observable();
        self.vDisks             = ko.observableArray([]);
        self.vMachines          = ko.observableArray([]);
        self.storageRouterGuids = ko.observableArray([]);
        self.storageDriverGuids = ko.observableArray([]);

        // Computed
        self.cacheRatio = ko.computed(function() {
            var total = (self.cacheHits.raw() || 0) + (self.cacheMisses.raw() || 0);
            if (total === 0) {
                total = 1;
            }
            return generic.formatRatio((self.cacheHits.raw() || 0) / total * 100);
        });
        self.bandwidth = ko.computed(function() {
            var total = (self.readSpeed.raw() || 0) + (self.writeSpeed.raw() || 0);
            return generic.formatSpeed(total);
        });

        // Functions
        self.fillData = function(data, options) {
            options = options || {};
            generic.trySet(self.name, data, 'name');
            generic.trySet(self.storedData, data, 'stored_data');
            generic.trySet(self.size, data, 'size');
            generic.trySet(self.backendConnection, data, 'connection');
            generic.trySet(self.backendLogin, data, 'login');
            if (data.hasOwnProperty('backend_type_guid')) {
                self.backendTypeGuid(data.backend_type_guid);
            } else {
                self.backendTypeGuid(undefined);
            }
            if (data.hasOwnProperty('vdisks_guids') && !generic.tryGet(options, 'skipDisks', false)) {
                generic.crossFiller(
                    data.vdisks_guids, self.vDisks,
                    function(guid) {
                        return new VDisk(guid);
                    }, 'guid'
                );
            }
            if (data.hasOwnProperty('storagedrivers_guids')) {
                self.storageDriverGuids(data.storagedrivers_guids);
            }
            if (data.hasOwnProperty('statistics')) {
                var stats = data.statistics;
                self.iops(stats.operations_ps);
                self.cacheHits(stats.cache_hits_ps);
                self.cacheMisses(stats.cache_misses_ps);
                self.readSpeed(stats.data_read_ps);
                self.writeSpeed(stats.data_written_ps);
                self.backendWritten(stats.backend_data_written);
                self.backendRead(stats.backend_data_read);
                self.bandwidthSaved(Math.max(0, stats.data_read - stats.backend_data_read));
                self.backendReadSpeed(stats.backend_data_read_ps);
                self.backendWriteSpeed(stats.backend_data_written_ps);
            }

            self.loaded(true);
            self.loading(false);
        };
        self.load = function(contents, options) {
            options = options || {};
            self.loading(true);
            return $.Deferred(function(deferred) {
                var calls = [
                    $.Deferred(function(mainDeferred) {
                        if (generic.xhrCompleted(self.loadHandle)) {
                            var listOptions = {};
                            if (contents !== undefined) {
                                listOptions.contents = contents;
                            }
                            self.loadHandle = api.get('vpools/' + self.guid(), { queryparams: listOptions })
                                .done(function(data) {
                                    self.fillData(data, options);
                                    mainDeferred.resolve();
                                })
                                .fail(mainDeferred.reject);
                        } else {
                            mainDeferred.resolve();
                        }
                    }).promise(),
                    $.Deferred(function(machineDeferred) {
                        if (generic.xhrCompleted(self.machineHandle)) {
                            var options = {
                                sort: 'name',
                                vpoolguid: self.guid(),
                                contents: ''
                            };
                            self.machineHandle = api.get('vmachines', { queryparams: options })
                                .done(function(data) {
                                    var guids = [], vmdata = {};
                                    $.each(data, function(index, item) {
                                        guids.push(item.guid);
                                        vmdata[item.guid] = item;
                                    });
                                    generic.crossFiller(
                                        guids, self.vMachines,
                                        function(guid) {
                                            var vmachine = new VMachine(guid);
                                            if ($.inArray(guid, guids) !== -1) {
                                                vmachine.fillData(vmdata[guid]);
                                            }
                                            vmachine.loading(true);
                                            return vmachine;
                                        }, 'guid'
                                    );
                                    machineDeferred.resolve();
                                })
                                .fail(machineDeferred.reject);
                        } else {
                            machineDeferred.resolve();
                        }
                    }).promise()];
                $.when.apply($, calls)
                    .done(function() {
                        self.loaded(true);
                        deferred.resolve();
                    })
                    .fail(deferred.reject)
                    .always(function() {
                        self.loading(false);
                    });
            }).promise();
        };
        self.loadStorageRouters = function() {
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.storageRouterHandle)) {
                    self.storageRouterHandle = api.get('vpools/' + self.guid() + '/storagerouters')
                        .done(function(data) {
                            self.storageRouterGuids(data.data);
                            deferred.resolve();
                        })
                        .fail(deferred.reject);
                } else {
                    deferred.resolve();
                }
            }).promise();
        };
        self.loadBackendType = function() {
            return $.Deferred(function(deferred) {
                if (self.backendTypeGuid() !== undefined) {
                    if (self.backendType() === undefined || self.backendTypeGuid() !== self.backendType().guid()) {
                        var backendType = new BackendType(self.backendTypeGuid());
                        backendType.load()
                            .then(deferred.resolve)
                            .fail(deferred.reject);
                        self.backendType(backendType);
                    } else {
                        self.backendType().load()
                            .then(deferred.resolve)
                            .fail(deferred.reject);
                    }
                } else {
                    self.backendType(undefined);
                    deferred.resolve();
                }
            }).promise();
        };
    };
});
