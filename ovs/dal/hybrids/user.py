from ovs.dal.dataobject import DataObject
from ovs.dal.hybrids.group import Group


class User(DataObject):
    _blueprint = {'username': None,
                  'password': None,
                  'email'   : None}
    _relations = {'group'   : (Group, 'users')}
    _expiry = {}