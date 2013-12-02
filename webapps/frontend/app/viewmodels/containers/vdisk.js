// license see http://www.openvstorage.com/licenses/opensource/
/*global define */
define([
    'jquery', 'knockout',
    'ovs/generic', 'ovs/api'
], function($, ko, generic, api) {
    "use strict";
    return function(guid) {
        var self = this;

        // Variables
        self.loadHandle             = undefined;
        self.loadVSAGuidHandle      = undefined;
        self.loadVMachineGuidHandle = undefined;
        
        // External dependencies
        self.vsa          = ko.observable();
        self.vMachine     = ko.observable();

        // Obserables
        self.loading      = ko.observable(false);
        self.loaded       = ko.observable(false);
        
        self.guid         = ko.observable(guid);
        self.name         = ko.observable();
        self.vpool        = ko.observable();
        self.order        = ko.observable(0);
        self.snapshots    = ko.observableArray([]);
        self.size         = ko.observable(0);
        self.storedData   = ko.smoothObservable(undefined, generic.formatBytes);
        self.cacheHits    = ko.smoothDeltaObservable();
        self.cacheMisses  = ko.smoothDeltaObservable();
        self.iops         = ko.smoothDeltaObservable(generic.formatShort);
        self.readSpeed    = ko.smoothDeltaObservable(generic.formatSpeed);
        self.writeSpeed   = ko.smoothDeltaObservable(generic.formatSpeed);
        self.vsaGuid      = ko.observable();
        self.vMachineGuid = ko.observable();
        
        self.cacheRatio = ko.computed(function() {
            var total = (self.cacheHits.raw() || 0) + (self.cacheMisses.raw() || 0);
            if (total === 0) {
                total = 1;
            }
            return generic.formatRatio((self.cacheHits.raw() || 0) / total * 100);
        });

        // Functions
        self.fetchVSAGuid = function() {
            return $.Deferred(function(deferred) {
                generic.xhrAbort(self.loadVSAGuid);
                self.loadVSAGuid = api.get('vdisks/' + self.guid() + '/get_vsa')
                    .done(function(data) {
                        self.vsaGuid(data);
                        deferred.resolve();
                    })
                    .fail(deferred.reject);
            }).promise();
        };
        self.fetchVMachineGuid = function() {
            return $.Deferred(function(deferred) {
                generic.xhrAbort(self.loadVMachineGuidHandle);
                self.loadVMachineGuidHandle = api.get('vdisks/' + self.guid() + '/get_vmachine')
                    .done(function(data) {
                        self.vMachineGuid(data);
                        deferred.resolve();
                    })
                    .fail(deferred.reject);
            }).promise();
        };
        self.load = function() {
            return $.Deferred(function(deferred) {
            	self.loading(true);
                $.when.apply($, [
                        $.Deferred(function(deferred) {
			                generic.xhrAbort(self.loadHandle);
			                self.loadHandle = api.get('vdisks/' + self.guid())
			                    .done(function(data) {
			                    	var stats = data.statistics;
			                        self.name(data.name);
			                        if (stats !== undefined) {
			                        	self.iops(stats.write_operations + stats.read_operations);
				                        self.cacheHits(stats.sco_cache_hits + stats.cluster_cache_hits);
	                                    self.cacheMisses(stats.sco_cache_misses);
	                                    self.readSpeed(stats.data_read);
	                                    self.writeSpeed(stats.data_written);
			                        }
			                        self.order(data.order);
			                        self.snapshots(data.snapshots);
			                        self.size(data.size);
			                        self.stored_data(data.info['stored']);
			                        self.vpool(data.vpool);
			                        deferred.resolve();
			                    })
			                    .fail(deferred.reject);
			            }).promise()
                    ])
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
