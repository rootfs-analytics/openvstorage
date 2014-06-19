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
/*global define, window */
define([
    'jquery', 'knockout',
    'ovs/shared', 'ovs/api', 'ovs/generic',
    '../../containers/vmachine', '../../containers/volumestoragerouter', './data'
], function($, ko, shared, api, generic, VMachine, VolumeStorageRouter, data) {
    "use strict";
    return function() {
        var self = this;

        // Variables
        self.shared           = shared;
        self.data             = data;
        self.loadVSASHandle   = undefined;
        self.checkS3Handle    = undefined;
        self.loadVSAHandle    = undefined;
        self.loadVSRsHandle   = {};

        // Observables
        self.preValidateResult = ko.observable({ valid: true, reasons: [], fields: [] });

        // Computed
        self.canContinue = ko.computed(function() {
            var valid = true, showErrors = false, reasons = [], fields = [], preValidation = self.preValidateResult();
            if (!self.data.name.valid()) {
                valid = false;
                fields.push('name');
                reasons.push($.t('ovs:wizards.addvpool.gathervpool.invalidname'));
            }
            if (self.data.backend().match(/^.+_S3$/)) {
                if (!self.data.host.valid()) {
                    valid = false;
                    fields.push('host');
                    reasons.push($.t('ovs:wizards.addvpool.gathervpool.invalidhost'));
                }
                if (self.data.accesskey() === '' || self.data.secretkey() === '') {
                    valid = false;
                    fields.push('accesskey');
                    fields.push('secretkey');
                    reasons.push($.t('ovs:wizards.addvpool.gathervpool.nocredentials'));
                }
            }

            if (preValidation.valid === false) {
                showErrors = true;
                reasons = reasons.concat(preValidation.reasons);
                fields = fields.concat(preValidation.fields);
            }
            return { value: valid, showErrors: showErrors, reasons: reasons, fields: fields };
        });

        // Functions
        self.preValidate = function() {
            self.preValidateResult({ valid: true, reasons: [], fields: [] });
            return $.Deferred(function(deferred) {
                if (self.data.backend().match(/^.+_S3$/)) {
                    generic.xhrAbort(self.checkS3Handle);
                    var postData = {
                        host: self.data.host(),
                        port: self.data.port(),
                        accesskey: self.data.accesskey(),
                        secretkey: self.data.secretkey()
                    };
                    self.checkS3Handle = api.post('vmachines/' + self.data.target().guid() + '/check_s3', postData)
                        .then(self.shared.tasks.wait)
                        .done(function(data) {
                            if (!data) {
                                self.preValidateResult({
                                    valid: false,
                                    reasons: [$.t('ovs:wizards.addvpool.gathervpool.invalids3info')],
                                    fields: ['accesskey', 'secretkey', 'host']
                                });
                                deferred.reject();
                            } else {
                                deferred.resolve();
                            }
                        })
                        .fail(deferred.reject);
                } else {
                    deferred.resolve();
                }
            }).promise();
        };
        self.next = function() {
            return $.Deferred(function(deferred) {
                var calls = [
                    $.Deferred(function(mtptDeferred) {
                        generic.xhrAbort(self.loadVSAHandle);
                        var postData = {};
                        if (self.data.backend() === 'CEPH_S3') {
                            postData.files = '/etc/ceph/ceph.conf,/etc/ceph/ceph.keyring';
                        }
                        self.loadVSAHandle = api.post('vmachines/' + self.data.target().guid() + '/get_physical_metadata', postData)
                            .then(self.shared.tasks.wait)
                            .then(function(data) {
                                self.data.mountpoints(data.mountpoints);
                                self.data.ipAddresses(data.ipaddresses);
                                self.data.vRouterPort(data.xmlrpcport);
                                self.data.files(data.files);
                                self.data.allowVPool(data.allow_vpool);
                            })
                            .done(function() {
                                mtptDeferred.resolve();
                            })
                            .fail(mtptDeferred.reject);
                    }).promise()
                ];
                generic.crossFiller(
                    self.data.target().servedVSRGuids, self.data.vsrs,
                    function(guid) {
                        var vsr = new VolumeStorageRouter(guid);
                        calls.push($.Deferred(function(deferred) {
                            generic.xhrAbort(self.loadVSRsHandle[guid]);
                            self.loadVSAHandle[guid] = api.get('volumestoragerouters/' + guid)
                                .done(function(vsrData) {
                                    vsr.fillData(vsrData);
                                    deferred.resolve();
                                })
                                .fail(deferred.reject);
                        }).promise());
                        return vsr;
                    }, 'guid'
                );
                $.when.apply($, calls)
                    .done(deferred.resolve)
                    .fail(deferred.reject);
            });
        };

        // Durandal
        self.activate = function() {
            generic.xhrAbort(self.loadVSASHandle);
            var query = {
                query: {
                    type: 'AND',
                    items: [['is_internal', 'EQUALS', true]]
                }
            };
            self.loadVSASHandle = api.post('vmachines/filter', query, {
                contents: 'served_vsrs',
                sort: 'name'
            })
                .done(function(data) {
                    var guids = [], vmdata = {};
                    $.each(data, function(index, item) {
                        guids.push(item.guid);
                        vmdata[item.guid] = item;
                    });
                    generic.crossFiller(
                        guids, self.data.vsas,
                        function(guid) {
                            return new VMachine(guid);
                        }, 'guid'
                    );
                    $.each(self.data.vsas(), function(index, vmachine) {
                        vmachine.fillData(vmdata[vmachine.guid()]);
                    });
                    if (self.data.target() === undefined && self.data.vsas().length > 0) {
                        self.data.target(self.data.vsas()[0]);
                    }
                });
        };
    };
});
