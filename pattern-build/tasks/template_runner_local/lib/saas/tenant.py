import requests
import env

def get_tenant_id(auth):
    '''
    Retrieve the tenant ID
    '''

    bearer_token = auth[0]
    org_guid = auth[1]
    space_guid = auth[2]

    request_header = {'Authorization': bearer_token['token_type'] + ' ' + bearer_token['access_token'], 'Accept': 'application/json'}
    params = {'organizationId': org_guid, 'spaceId': space_guid, 'serviceId': _get_service_id(bearer_token, space_guid)}

    return requests.get(env.TENANT_HOST + '/tenants/findTenantByOrgSpaceServiceId', headers=request_header, params=params).json()['id']


def _get_service_id(bearer_token, space_guid):
    '''
    Retrieve the service ID (for environment specified in environment variable TEST_ENVIRONMENT)
    '''
    request_header = {'Authorization': bearer_token['token_type'] + ' ' + bearer_token['access_token'], 'Accept': 'application/json'}

    response = requests.get(env.AUTH_HOST + '/v2/service_instances', headers=request_header).json()['resources']

    for i in response:
        if i['entity']['dashboard_url'] == env.DASHBOARD and i['entity']['space_guid'] == space_guid:
            return i['metadata']['guid']
