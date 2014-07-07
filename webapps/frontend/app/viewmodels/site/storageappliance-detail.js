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
/*global define */
define([
    'jquery', 'knockout',
    'ovs/shared', 'ovs/generic', 'ovs/refresher', 'ovs/api',
    '../containers/storageappliance', '../containers/pmachine', '../containers/vpool', '../containers/storagedriver'
], function($, ko, shared, generic, Refresher, api, StorageAppliance, PMachine, VPool, StorageDriver) {
    "use strict";
    return function() {
        var self = this;

        // Variables
        self.shared                   = shared;
        self.guard                    = { authenticated: true };
        self.refresher                = new Refresher();
        self.widgets                  = [];
        self.pMachineCache            = {};
        self.vPoolCache               = {};
        self.vMachineCache            = {};
        self.loadVPoolsHandle         = undefined;
        self.loadStorageDriversHandle = {};

        // Observables
        self.storageAppliance     = ko.observable();
        self.vPoolsLoaded         = ko.observable(false);
        self.vPools               = ko.observableArray([]);
        self.checkedVPoolGuids    = ko.observableArray([]);

        // Functions
        self.load = function() {
            return $.Deferred(function (deferred) {
                var storageAppliance = self.storageAppliance();
                $.when.apply($, [
                        storageAppliance.load('_dynamics,_relations'),
                        storageAppliance.getAvailableActions()
                    ])
                    .then(self.loadStorageDrivers)
                    .then(self.loadVPools)
                    .done(function() {
                        self.checkedVPoolGuids(self.storageAppliance().vPoolGuids);
                        var pMachineGuid = storageAppliance.pMachineGuid(), pm;
                        if (pMachineGuid && (storageAppliance.pMachine() === undefined || storageAppliance.pMachine().guid() !== pMachineGuid)) {
                            if (!self.pMachineCache.hasOwnProperty(pMachineGuid)) {
                                pm = new PMachine(pMachineGuid);
                                pm.load();
                                self.pMachineCache[pMachineGuid] = pm;
                            }
                            storageAppliance.pMachine(self.pMachineCache[pMachineGuid]);
                        }
                        // Move child guids to the observables for easy display
                        storageAppliance.vPools(storageAppliance.vPoolGuids);
                        storageAppliance.vMachines(storageAppliance.vMachineGuids);
                    })
                    .always(deferred.resolve);
            }).promise();
        };
        self.loadVPools = function() {
            return $.Deferred(function(deferred) {
                if (generic.xhrCompleted(self.loadVPoolsHandle)) {
                    self.loadVPoolsHandle = api.get('vpools', undefined, {
                        sort: 'name',
                        contents: ''
                    })
                        .done(function(data) {
                            var guids = [], vpdata = {};
                            $.each(data, function(index, item) {
                                guids.push(item.guid);
                                vpdata[item.guid] = item;
                            });
                            generic.crossFiller(
                                guids, self.vPools,
                                function(guid) {
                                    var vpool = new VPool(guid);
                                    vpool.fillData(vpdata[guid]);
                                    return vpool;
                                }, 'guid'
                            );
                            self.vPoolsLoaded(true);
                            deferred.resolve();
                        })
                        .fail(deferred.reject);
                } else {
                    deferred.reject();
                }
            }).promise();
        };
        self.loadStorageDrivers = function() {
            return $.Deferred(function(deferred) {
                $.each(self.storageAppliance().storageDriverGuids, function(index, guid) {
                    if (generic.xhrCompleted(self.loadStorageDriversHandle[guid])) {
                        self.loadStorageDriversHandle[guid] = api.get('storagedrivers/' + guid)
                            .done(function(data) {
                                var storageDriverFound = false, storageDriver;
                                $.each(self.storageAppliance().StorageDrivers(), function(vindex, storageDriver) {
                                    if (storageDriver.guid() === guid) {
                                        storageDriver.fillData(data);
                                        storageDriverFound = true;
                                        return false;
                                    }
                                    return true;
                                });
                                if (storageDriverFound === false) {
                                    storageDriver = new StorageDriver(data.guid);
                                    storageDriver.fillData(data);
                                    self.storageAppliance().StorageDrivers.push(storageDriver);
                                }
                            });
                    }
                });
                deferred.resolve();
            }).promise();
        };

        // Durandal
        self.activate = function(mode, guid) {
            self.storageAppliance(new StorageAppliance(guid));
            self.storageAppliance().StorageDrivers = ko.observableArray();

            self.refresher.init(self.load, 5000);
            self.refresher.run();
            self.refresher.start();
            self.shared.footerData(self.storageAppliance);
        };
        self.deactivate = function() {
            $.each(self.widgets, function(index, item) {
                item.deactivate();
            });
            self.refresher.stop();
            self.shared.footerData(ko.observable());
        };
    };
});
