/*global define */
define(['jquery', 'jqp/pnotify'], function($) {
    "use strict";
    function getTimestamp() {
        return new Date().getTime();
    }
    function getBytesHuman(value) {
        var units, counter;
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
        counter = 0;
        while (value > 2048) {
            value = value / 1024;
            counter += 1;
        }
        return (Math.round(value * 100) / 100).toString() + ' ' + units[counter];
    }
    function padRight(value, character, length) {
        while (value.length < length) {
            value += character;
        }
        return value;
    }
    function tryGet(object, key, fallback) {
        if (object !== undefined && object.hasOwnProperty(key)) {
            return object[key];
        }
        return fallback;
    }
    function getCookie(name) {
        var i, cookie, cookies;
        cookies = document.cookie.split(';');
        for (i = 0; i < cookies.length; i += 1) {
            cookie = $.trim(cookies[i]);
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }
        return undefined;
    }
    function setCookie(name, value, expiry) {
        var date, expires = '';
        if (expiry) {
            date = new Date();
            date.setTime(date.getTime() +
                (tryGet(expiry, 'days', 0) * 24 * 60 * 60 * 1000) +
                (tryGet(expiry, 'hours', 0) * 60 * 60 * 1000) +
                (tryGet(expiry, 'minutes', 0) * 60 * 1000) +
                (tryGet(expiry, 'seconds', 0) * 1000)
            );
            expires = '; expires=' + date.toUTCString();
        }
        document.cookie = name + '=' + value + expires + '; path=/';
    }
    function alert(title, message, type) {
        var data = {
            title: title,
            text: message,
            nonblock: true,
            delay: 3000
        };
        if (type !== undefined) {
            data.type = type;
        }
        return $.pnotify(data);
    }
    function alertInfo(title, message) {
        return alert(title, message, 'info');
    }
    function alertSuccess(title, message) {
        return alert(title, message, 'success');
    }
    function alertError(title, message) {
        return alert(title, message, 'error');
    }
    function keys(object) {
        var allKeys = [], key;
        for (key in object) {
            if (object.hasOwnProperty(key)) {
                allKeys.push(key);
            }
        }
        return allKeys;
    }
    function xhrAbort(token) {
        if (token !== undefined && token.state() === 'pending') {
            try {
                token.abort();
            } catch (error) {
                // Ignore these errors
            }
        }
    }
    function removeElement(array, element) {
        var index = array.indexOf(element);
        if (index !== -1) {
            array.splice(index, 1);
        }
    }
    function smooth(observable, targetValue, steps) {
        var startValue, diff, stepSize, decimals, execute;
        if (steps === undefined) {
            steps = 3;
        }
        startValue = observable() || 0;
        diff = targetValue - startValue;
        if (diff !== 0) {
            decimals = Math.max((startValue.toString().split('.')[1] || []).length, (targetValue.toString().split('.')[1] || []).length);
            stepSize = decimals === 0 ? Math.round(diff / steps) : Math.round(diff / steps * (10 * decimals)) / (10 * decimals);
            execute = function() {
                var current = observable();
                if (Math.abs(targetValue - current) > Math.abs(stepSize)) {
                    observable(observable() + stepSize);
                    window.setTimeout(execute, 75);
                } else {
                    observable(targetValue);
                }
            };
            window.setTimeout(execute, 75);
        }
    }

    return {
        getTimestamp : getTimestamp,
        getBytesHuman: getBytesHuman,
        padRight     : padRight,
        getCookie    : getCookie,
        setCookie    : setCookie,
        tryGet       : tryGet,
        alert        : alert,
        alertInfo    : alertInfo,
        alertSuccess : alertSuccess,
        alertError   : alertError,
        keys         : keys,
        xhrAbort     : xhrAbort,
        removeElement: removeElement,
        smooth       : smooth
    };
});