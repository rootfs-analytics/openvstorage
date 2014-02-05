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
    'jquery', 'ovs/generic',
    '../build', './gather', './data'
], function($, generic, build, Gather, data) {
    "use strict";
    return function(options) {
        var self = this;

        self.data = data;
        build(self);

        self.title(generic.tryGet(options, 'title', $.t('ovs:wizards.createft.title')));
        self.modal(generic.tryGet(options, 'modal', false));

        self.data.guid(options.vmachineguid);
        self.steps([new Gather()]);

        self.activateStep();

        self.compositionComplete = function() {
            var i, fields = ['amount', 'startnr'], element;
            for (i = 0; i < fields.length; i += 1) {
                element = $("#" + fields[i]);
                element.on('keypress', function(e) {
                    // Guard keypresses, only accepting numeric values
                    return !(e.which !== 8 && e.which !== 0 && (e.which < 48 || e.which > 57));
                });
                element.on('change', function() {
                    // Guard ctrl+v
                    element.val(Math.max(1, parseInt('0' + element.val(), 10)));
                });
            }
        };
    };
});
