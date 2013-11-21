"""
Branding module
"""
from ovs.dal.dataobject import DataObject


class Branding(DataObject):
    """
    This class contains information regarding product branding
    """
    _blueprint = {'name': (None, str, 'Name of the brand'),
                  'description': (None, str, 'Description of the brand'),
                  'css': (None, str, 'CSS file used by the brand'),
                  'productname': (None, str, 'Commercial product name'),
                  'is_default': (False, bool, 'Indicates whether this brand is the default one')}
    _relations = {}
    _expiry = {}
