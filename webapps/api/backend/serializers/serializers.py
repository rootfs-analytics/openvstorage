# Copyright 2014 CloudFounders NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module contains generic hybrid serializers
"""
from ovs.dal.relations.relations import RelationMapper
from rest_framework import serializers


class FullSerializer(serializers.Serializer):
    """
    Serializes the persistent and dynamic stack of a hybrid object
    """
    def __init__(self, hybrid, contents=None, *args, **kwargs):
        """
        Initializes the serializer, mapping field types
        """
        allow_passwords = False
        if 'allow_passwords' in kwargs:
            allow_passwords = kwargs['allow_passwords']
            del kwargs['allow_passwords']
        super(FullSerializer, self).__init__(*args, **kwargs)
        self.hybrid = hybrid
        for key, default in self.hybrid._blueprint.iteritems():
            if not 'password' in key or allow_passwords:
                self.fields[key] = FullSerializer._map_type_to_field(default[1])
        for key in self.hybrid._expiry:
            if contents is None or (('_dynamics' in contents or key in contents)
                                    and '-{0}'.format(key) not in contents):
                self.fields[key] = serializers.Field()
        for key in self.hybrid._relations:
            if contents is None or (('_relations' in contents or key in contents)
                                    and '-{0}'.format(key) not in contents):
                self.fields['%s_guid' % key] = serializers.CharField(required=False)
        relations = RelationMapper.load_foreign_relations(hybrid)
        if relations is not None:
            for key, info in relations.iteritems():
                if contents is None or (('_relations' in contents or key in contents)
                                        and '-{0}'.format(key) not in contents):
                    if info['list'] is True:
                        self.fields['%s_guids' % key] = serializers.Field()
                    else:
                        self.fields['%s_guid' % key] = serializers.Field()

    guid = serializers.Field()

    def get_identity(self, data):
        """
        This hook makes sure the guid is returned as primary key
        """
        return data.get('guid', None)

    def restore_object(self, attrs, instance=None):
        """
        Provides deserializing functionality for persistent properties
        """
        if instance is not None:
            for key in self.hybrid._blueprint:
                setattr(instance, key, attrs.get(key, getattr(instance, key)))
            for key, relation in self.hybrid._relations.iteritems():
                guid_key = '{0}_guid'.format(key)
                if guid_key in attrs and attrs[guid_key] != getattr(instance, guid_key):
                    setattr(instance, key, None if attrs[guid_key] is None else relation[0](attrs[guid_key]))
            return instance
        return self.hybrid(data=attrs)

    @staticmethod
    def _map_type_to_field(field_type):
        """
        Maps the given field type to a serializer field
        """
        if isinstance(field_type, list):
            field_type = type(field_type[0])
        if field_type is str:
            return serializers.CharField(required=False)
        if field_type is int:
            return serializers.IntegerField(required=False)
        if field_type is bool:
            return serializers.BooleanField(required=False)
        return serializers.Field()

    class Meta:
        """
        Meta class
        """
        fields = ('guid',)
        read_only_fields = ('guid',)
