// license see http://www.openvstorage.com/licenses/opensource/
/*global define */
define(function() {
    "use strict";
    return {
        canActivate: function() {
            return { redirect: '#full' };
        }
    };
});