from ovs.dal.dataobject import DataObject
from ovs.dal.hybrids.pmachine import pMachine


class vMachine(DataObject):
    _blueprint = {'name'        : None,
                  'description' : None,
                  'hvtype'      : None,
                  'cpu'         : 1,
                  'memory'      : 1024,
                  'vmid'        : None,
                  'template'    : True}
    _relations = {'node': (pMachine, 'guests')}
    _expiry = {}