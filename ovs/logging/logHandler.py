# license see http://www.openvstorage.com/licenses/opensource/
"""
Contains the loghandler module
"""
import logging
import logstash_formatter


class LogHandler(object):
    """
    Log handler
    """
    def __init__(self, logFile):
        """
        This empties the log targets
        """
        self.logger = logging.getLogger()
        handler = logging.FileHandler('/var/log/ovs/%s' % logFile)
        handler.setFormatter(logstash_formatter.LogstashFormatter())
        self.logger.addHandler(handler)
        self.logger.setLevel(6)

