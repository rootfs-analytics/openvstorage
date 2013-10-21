define(['knockout', 'ovs/generic'], function (ko, generic){
    "use strict";
    var singleton = function () {
        return {
            init: function (mode) {
                var self = this;
                self.mode = mode;
            },
            mode: undefined,
            username: ko.observable(),
            password: ko.observable(),
            loggedin: ko.observable(false),
            token: undefined,
            login: function (username, password) {
                var self = this;
                return $.Deferred(function (deferred) {
                    $.ajax('/api/auth/', {
                        type: 'post',
                        data: ko.toJSON({
                            'username': username,
                            'password': password
                        }),
                        contentType: 'application/json',
                        headers: { 'X-CSRFToken': self.getCSRFToken() }
                    })
                    .done(function(result) {
                        self.token = result.token;
                        self.username(username);
                        self.password(password);
                        self.loggedin(true);
                        deferred.resolve();
                    })
                    .fail(function (xmlHttpRequest, textStatus, errorThrown) {
                        // We check whether we actually received an error, and it's not the browser navigating away
                        if (xmlHttpRequest.readyState !== 0 && xmlHttpRequest.status !== 0) {
                            self.token = undefined;
                            self.username(undefined);
                            self.password(undefined);
                            self.loggedin(false);
                            deferred.reject();
                        }
                    });
                }).promise();
            },
            logout: function () {
                var self = this;
                self.token = undefined;
                self.username(undefined);
                self.password(undefined);
                self.loggedin(false);
            },
            validate: function () {
                var self = this;
                if (self.token !== undefined) {
                    return true;
                }
                return { redirect: '#' + self.mode + '/login' };
            },
            header: function () {
                var self = this;
                return 'Token ' + self.token;
            },
            getCSRFToken: function () {
                return generic.get_cookie('csrftoken');
            }
        };
    };
    return singleton();
});