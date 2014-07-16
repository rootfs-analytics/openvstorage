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
    'plugins/router', 'jquery', 'knockout',
    'ovs/generic', 'ovs/shared'
], function(router, $, ko, generic, shared){
    "use strict";
    return function() {
        var self = this;

        self.onLoggedIn  = [];
        self.onLoggedOut = [];
        self.token       = undefined;
        self.required    = false;

        self.userGuid = ko.observable();
        self.username = ko.observable();
        self.password = ko.observable();
        self.loggedIn = ko.observable(false);

        self.login = function(username, password) {
            return $.Deferred(function(deferred) {
                var callData, cookie;
                callData = {
                    type: 'post',
                    data: {
                        grant_type: 'password',
                        username: username,
                        password: password
                    },
                    contentType: 'application/x-www-form-urlencoded',
                    headers: {}
                };
                cookie = generic.getCookie('csrftoken');
                if (cookie !== undefined) {
                    callData.headers['X-CSRFToken'] = cookie;
                }
                $.ajax('/api/oauth2/token/', callData)
                    .done(function(result) {
                        var i, events = [];
                        self.token = result.access_token;
                        self.userGuid(result.user_guid);
                        self.username(username);
                        self.password(password);
                        self.loggedIn(true);
                        for (i = 0; i < self.onLoggedIn.length; i += 1) {
                            events.push(self.onLoggedIn[i]());
                        }
                        $.when.apply($, events).always(deferred.resolve);
                    })
                    .fail(function(xmlHttpRequest) {
                        // We check whether we actually received an error, and it's not the browser navigating away
                        if (xmlHttpRequest.readyState === 4 && xmlHttpRequest.status === 502) {
                            generic.validate(shared.nodes);
                        } else if (xmlHttpRequest.readyState !== 0 && xmlHttpRequest.status !== 0) {
                            self.token = undefined;
                            self.username(undefined);
                            self.password(undefined);
                            self.userGuid(undefined);
                            self.loggedIn(false);
                            deferred.reject({
                                status: xmlHttpRequest.status,
                                statusText: xmlHttpRequest.statusText,
                                readyState: xmlHttpRequest.readyState,
                                responseText: xmlHttpRequest.responseText
                            });
                        } else if (xmlHttpRequest.readyState === 0 && xmlHttpRequest.status === 0) {
                            generic.validate(shared.nodes);
                        }
                    });
            }).promise();
        };
        self.logout = function() {
            var i, events = [];
            self.token = undefined;
            self.username(undefined);
            self.password(undefined);
            self.userGuid(undefined);
            self.loggedIn(false);
            for (i = 0; i < self.onLoggedOut.length; i += 1) {
                events.push(self.onLoggedOut[i]());
            }
            $.when.apply($, events)
                .always(function() {
                    router.navigate('');
                });
        };
        self.validate = function() {
            return self.token !== undefined;
        };
        self.header = function() {
            return 'Bearer ' + self.token;
        };
    };
});
