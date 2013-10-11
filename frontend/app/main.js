﻿requirejs.config({
    paths: {
        'text'        : '../lib/require/text',
        'durandal'    : '../lib/durandal/js',
        'plugins'     : '../lib/durandal/js/plugins',
        'transitions' : '../lib/durandal/js/transitions',
        'knockout'    : '../lib/knockout/knockout-2.3.0',
        'bootstrap'   : '../lib/bootstrap/js/bootstrap',
        'jquery'      : '../lib/jquery/jquery-1.9.1',
        'ovs'         : '../lib/ovs',
        'models'      : 'viewmodels/models'
    },
    shim: {
        'bootstrap': {
            deps   : ['jquery'],
            exports: 'jQuery'
        }
    },
    urlArgs: "bust=" + (new Date()).getTime()
});

define(['durandal/system', 'durandal/app', 'durandal/viewLocator'],  function (system, app, viewLocator) {
    "use strict";
    system.debug(true);

    app.title = 'Open vStorage';
    app.configurePlugins({
        router: true,
        dialog: true,
        widget: true
    });
    app.start().then(function () {
        viewLocator.useConvention();
        app.setRoot('viewmodels/shell', 'entrance');
    });
});