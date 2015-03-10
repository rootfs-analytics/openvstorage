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
define(['knockout'], function(ko) {
    "use strict";
    ko.deltaObservable = function(formatFunction) {
        var formattedValue = ko.observable(), rawValue = ko.observable(), initialized = ko.observable(false),
            timestamp, newTimestamp, previousCounter, delta, timeDelta, result, newRaw;
        result = ko.computed({
            read: function() {
                return formattedValue();
            },
            write: function(newCounter) {
                newTimestamp = (new Date()).getTime();
                if (typeof newCounter === 'object') {
                    newTimestamp = newCounter.timestamp;
                    newCounter = newCounter.value;
                }
                if ((typeof previousCounter) === 'undefined') {
                    previousCounter = newCounter;
                    timestamp = newTimestamp;
                } else {
                    delta = newCounter - previousCounter;
                    timeDelta = (newTimestamp - timestamp) / 1000;
                    if (timeDelta <= 0) {
                        timeDelta = 1;
                    }
                    newRaw = Math.max(0, delta / timeDelta);
                    rawValue(newRaw);
                    if (formatFunction.call) {
                        formattedValue(formatFunction(newRaw));
                    } else {
                        formattedValue(newRaw);
                    }
                    timestamp = newTimestamp;
                    previousCounter = newCounter;
                    initialized(true);
                }
            }
        });
        result.initialized = initialized;
        result.raw = rawValue;
        return result;
    };
    ko.splitRows = function(columns, array) {
        return ko.computed(function () {
            var result = [], row;
            // Loop through items and push each item to a row array that gets pushed to the final result
            for (var i = 0, j = array().length; i < j; i++) {
                if (i % columns === 0) {
                    if (row) {
                        result.push({ items: row });
                    }
                    row = [];
                }
                row.push(array()[i]);
            }
            // Push the final row
            if (row) {
                result.push({ items: row });
            }
            return result;
        });
    };
});
