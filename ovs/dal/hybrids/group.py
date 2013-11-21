"""
Group module
"""
from ovs.dal.dataobject import DataObject


class Group(DataObject):
    """
    This class defines a group. A group can be used to bind a set of Users to a set of Roles
    """
    _blueprint = {'name': (None, str, 'Name of the group'),
                  'description': (None, str, 'Description of the group')}
    _relations = {}
    _expiry = {}
