# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import requests
import env


def get_tenant_id(bearer_token, org_guid, space_guid):
    '''
    Retrieve the tenant ID
    '''
    request_header = {'Authorization': bearer_token['token_type'] + ' ' + bearer_token['access_token'], 'Accept': 'application/json'}
    params = {'organizationId': org_guid, 'spaceId': space_guid, 'serviceId': _get_service_id(bearer_token, space_guid)}

    return requests.get(env.TENANT_HOST + '/tenants/findTenantByOrgSpaceServiceId',
        headers=request_header,
        params=params,
        timeout=60).json()['id']


def _get_service_id(bearer_token, space_guid):
    '''
    Retrieve the service ID (for environment specified in environment variable TEST_ENVIRONMENT)
    '''
    request_header = {'Authorization': bearer_token['token_type'] + ' ' + bearer_token['access_token'], 'Accept': 'application/json'}

    response = requests.get(env.AUTH_HOST + '/v2/service_instances',
        headers=request_header,
        timeout=60).json()['resources']

    for i in response:
        if i['entity']['dashboard_url'] == env.DASHBOARD and i['entity']['space_guid'] == space_guid:
            return i['metadata']['guid']
