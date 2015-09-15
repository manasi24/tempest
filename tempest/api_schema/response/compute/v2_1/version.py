# Copyright 2014 NEC Corporation.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

version = {
    'status_code': [200],
    'response_body': {
        'type': 'object',
        'properties': {
            'version': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string'},
                    'links': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'href': {'type': 'string', 'format': 'uri'},
                                'rel': {'type': 'string'},
                                'type': {'type': 'string'}
                            },
                            'required': ['href', 'rel']
                        }
                    },
                    'media-types': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'base': {'type': 'string'},
                                'type': {'type': 'string'}
                            },
                            'required': ['base', 'type']
                        }
                    },
                    'status': {'type': 'string'},
                    'updated': {'type': 'string', 'format': 'date-time'},
                    'version': {'type': 'string'},
                    'min_version': {'type': 'string'}
                },
                # NOTE: version and min_version have been added since Kilo,
                # so they should not be required.
                'required': ['id', 'links', 'media-types', 'status', 'updated']
            }
        },
        'required': ['version']
    }
}