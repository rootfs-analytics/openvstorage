﻿/*global define */
define([
    'plugins/router', 'plugins/dialog', 'jqp/pnotify',
    'ovs/shared', 'viewmodels/wizards/changepassword/index'
], function(router, dialog, $, shared, ChangePasswordWizard) {
    "use strict";
    var mode = router.activeInstruction().params[0];
    var childRouter = router.createChildRouter()
                            .makeRelative({
                                moduleId: 'viewmodels/site',
                                route: ':mode',
                                fromParent: true
                            })
                            .map([
                                // Navigation routes
                                { route: '',                moduleId: 'dashboard',   hash: '#' + mode,                  title: 'Dashboard',   nav: true  },
                                { route: 'statistics',      moduleId: 'statistics',  hash: '#' + mode + '/statistics',  title: 'Statistics',  nav: true  },
                                { route: 'vmachines',       moduleId: 'vmachines',   hash: '#' + mode + '/vmachines',   title: 'vMachines',   nav: true  },
                                // Non-navigation routes
                                { route: 'login',           moduleId: 'login',       hash: '#' + mode + '/login',       title: 'Login',       nav: false }
                            ])
                            .buildNavigationModel();
    childRouter.guardRoute = function(instance, instruction) {
        if (instance !== undefined && instance.hasOwnProperty('guard')) {
            if (instance.guard.authenticated === true) {
                if (instance.shared.authentication.validate()) {
                    return true;
                }
                window.localStorage.setItem('referrer', instruction.fragment);
                return instruction.params[0] + '/login';
            }
        }
        return true;
    };
    childRouter.mapUnknownRoutes('../404');

    return {
        shared: shared,
        router: childRouter,
        changePassword: function() {
            dialog.show(new ChangePasswordWizard({
                modal: true
            }));
        },
        activate: function(mode) {
            var self = this;
            // Config
            self.shared.mode(mode);

            // Notifications
            $.pnotify.defaults.history = false;
            $.pnotify.defaults.styling = "bootstrap";
        }
    };
});