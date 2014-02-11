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
    'ovs/generic', 'ovs/api'
], function($, ko, generic, api) {
    "use strict";
    return function(guid) {
        var self = this;

        // Variables
        self.loadHandle       = undefined;
        self.diskHandle       = undefined;
        self.machineHandle    = undefined;

        // Observables
        self.loading           = ko.observable(false);
        self.loaded            = ko.observable(false);

        self.guid              = ko.observable(guid);
        self.name              = ko.observable();
        self.size              = ko.smoothObservable(undefined, generic.formatBytes);
        self.iops              = ko.smoothDeltaObservable(generic.formatNumber);
        self.storedData        = ko.smoothObservable(undefined, generic.formatBytes);
        self.cacheHits         = ko.smoothDeltaObservable();
        self.cacheMisses       = ko.smoothDeltaObservable();
        self.numberOfDisks     = ko.smoothObservable(undefined);
        self.numberOfMachines  = ko.smoothObservable(undefined);
        self.readSpeed         = ko.smoothDeltaObservable(generic.formatSpeed);
        self.writeSpeed        = ko.smoothDeltaObservable(generic.formatSpeed);
        self.backendWriteSpeed = ko.smoothDeltaObservable(generic.formatSpeed);
        self.backendReadSpeed  = ko.smoothDeltaObservable(generic.formatSpeed);
        self.backendReads      = ko.smoothObservable(undefined, generic.formatNumber);
        self.backendWritten    = ko.smoothObservable(undefined, generic.formatBytes);
        self.backendRead       = ko.smoothObservable(undefined, generic.formatBytes);
        self.bandwidthSaved    = ko.smoothObservable(undefined, generic.formatBytes);
        self.backendType       = ko.observable();
        self.backendConnection = ko.observable();
        self.backendLogin      = ko.observable();

        self.cacheRatio = ko.computed(function() {
            var total = (self.cacheHits.raw() || 0) + (self.cacheMisses.raw() || 0);
            if (total === 0) {
                total = 1;
            }
            return generic.formatRatio((self.cacheHits.raw() || 0) / total * 100);
        });
        self.freeSpace = ko.computed(function() {
            if ((self.size.raw() || 0) === 0) {
                return generic.formatRatio(0);
            }
            return generic.formatRatio((self.size.raw() - (self.storedData.raw() || 0)) / self.size.raw() * 100);
        });

        self._bandwidth = ko.computed(function() {
            var total = (self.readSpeed.raw() || 0) + (self.writeSpeed.raw() || 0),
                initialized = self.readSpeed.initialized() && self.writeSpeed.initialized();
            return {
                value: generic.formatSpeed(total),
                initialized: initialized
            };
        });
        self.bandwidth = ko.computed(function() {
            return self._bandwidth().value;
        });
        self.bandwidth.initialized = ko.computed(function() {
            return self._bandwidth().initialized;
        });

        self.fillData = function(data) {
             var type = '', stats = data.statistics,
                statsTime = Math.round(stats.timestamp * 1000);
            if (data.backend_type) {
                type = $.t('ovs:vpools.backendtypes.' + data.backend_type);
            }
            self.name(data.name);
            self.iops({ value: stats.write_operations + stats.read_operations, timestamp: statsTime });
            self.size(data.size);
            self.storedData(data.stored_data);
            self.cacheHits({ value: stats.sco_cache_hits + stats.cluster_cache_hits, timestamp: statsTime });
            self.cacheMisses({ value: stats.sco_cache_misses, timestamp: statsTime });
            self.readSpeed({ value: stats.data_read, timestamp: statsTime });
            self.writeSpeed({ value: stats.data_written, timestamp: statsTime });
            self.backendReadSpeed({ value: stats.backend_data_read, timestamp: statsTime });
            self.backendWriteSpeed({ value: stats.backend_data_written, timestamp: statsTime });
            self.backendWritten(stats.data_written);
            self.backendRead(stats.data_read);
            self.backendReads(stats.backend_read_operations);
            self.bandwidthSaved(stats.data_read - stats.backend_data_read);
            self.backendType(type);
            self.backendConnection(data.backend_connection);
            self.backendLogin(data.backend_login);

            self.loaded(true);
            self.loading(false);
        };
        self.load = function(onlyextends) {
            self.loading(true);
            onlyextends = onlyextends || false;
            return $.Deferred(function(deferred) {
                var calls = [];
                if (!onlyextends) {
                    calls.push($.Deferred(function(mainDeferred) {
                            if (generic.xhrCompleted(self.loadHandle)) {
                                self.loadHandle = api.get('vpools/' + self.guid())
                                    .done(function(data) {
                                        self.fillData(data);
                                        mainDeferred.resolve();
                                    })
                                    .fail(mainDeferred.reject);
                            } else {
                                mainDeferred.reject();
                            }
                        }).promise());
                }
                calls.push($.Deferred(function(diskDeferred) {
                            if (generic.xhrCompleted(self.diskHandle)) {
                                self.diskHandle = api.get('vpools/' + self.guid() + '/count_disks')
                                    .done(function(data) {
                                        self.numberOfDisks(data);
                                        diskDeferred.resolve();
                                    })
                                    .fail(diskDeferred.reject);
                            } else {
                                diskDeferred.reject();
                            }
                        }).promise());
                calls.push($.Deferred(function(machineDeferred) {
                            if (generic.xhrCompleted(self.machineHandle)) {
                                self.machineHandle = api.get('vpools/' + self.guid() + '/count_machines')
                                    .done(function(data) {
                                        self.numberOfMachines(data);
                                        machineDeferred.resolve();
                                    })
                                    .fail(machineDeferred.reject);
                            } else {
                                machineDeferred.reject();
                            }
                        }).promise());
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
    };
});
