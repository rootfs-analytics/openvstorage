define([
    'ovs/generic',
    '../build', './gather', './confirm', './data'
], function (generic, build, Gather, Confirm, data) {
    "use strict";
    return function (options) {
        var self = this;

        self.data = data;
        build(self);

        self.title(generic.tryGet(options, 'title', 'Clone'));
        self.modal(generic.tryGet(options, 'modal', false));

        self.data.machineGuid(options.machineguid);
        self.steps([new Gather(), new Confirm()]);

        self.activateStep();
    };
});