# license see http://www.openvstorage.com/licenses/opensource/
"""
VDiskList module
"""
from ovs.dal.datalist import DataList
from ovs.dal.dataobjectlist import DataObjectList
from ovs.dal.hybrids.vdisk import VDisk


class VDiskList(object):
    """
    This VDiskList class contains various lists regarding to the VDisk class
    """

    @staticmethod
    def get_vdisks():
        """
        Returns a list of all VDisks
        """
        vdisks = DataList({'object': VDisk,
                           'data': DataList.select.DESCRIPTOR,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': []}}).data
        return DataObjectList(vdisks, VDisk)

    @staticmethod
    def get_vdisk_by_volumeid(volumeid):
        """
        Returns a list of all VDisks based on a given volumeid
        """
        # pylint: disable=line-too-long
        vdisks = DataList({'object': VDisk,
                           'data': DataList.select.DESCRIPTOR,
                           'query': {'type': DataList.where_operator.AND,
                                     'items': [('volumeid', DataList.operator.EQUALS, volumeid)]}}).data
        # pylint: enable=line-too-long
        if vdisks:
            return DataObjectList(vdisks, VDisk)[0]
        return None

    @staticmethod
    def get_by_devicename(devicename):
        """
        Returns a list of all VDisks based on a given volumeid
        """
        # pylint: disable=line-too-long
        vds = DataList({'object': VDisk,
                        'data': DataList.select.DESCRIPTOR,
                        'query': {'type': DataList.where_operator.AND,
                                  'items': [('devicename', DataList.operator.EQUALS, devicename)]}}).data  # noqa
        # pylint: enable=line-too-long
        if vds:
            return DataObjectList(vds, VDisk)[0]
        return None
