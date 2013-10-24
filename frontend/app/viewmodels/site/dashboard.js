﻿define(['ovs/shared', 'knockout'], function (shared, ko) {
    "use strict";
    return function () {
        var self = this;

        // System
        self.shared = shared;

        // Data
        self.displayName = ko.observable('Welcome to Open vStorage');
        self.description = ko.observable('Open vStorage is the next generation storage');
    };
});