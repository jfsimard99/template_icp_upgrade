import os
import requests
import env

from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

AUTH_HOST = env.AUTH_HOST



def authenticate():
    bearer_token = _get_bearer_token()
    org_guid = _get_org_guid()
    space_guid = _get_space_guid(bearer_token)

    return [bearer_token, org_guid, space_guid]


def _get_bearer_token():
    body = {
        "grant_type": "password",
        # "password": os.environ['W3_PASSWORD'],
        # "username": os.environ['W3_USERNAME'],
        "password": "admin",
        "username": "admin",
        "scope": "openid"
    }
    response = requests.post(env.AUTH_HOST, json=body, verify=False)
    return response.json()


def _get_org_guid():
    #
    # TODO: review this method when they change the security model again
    # For now we can hard code the same value UI uses
    #
    return 'dummy-org-id'


def _get_space_guid(bearer_token):
    #
    # TODO: review this method when they change the security model again
    # the method uses the getTenantOnPrem REST API and it picks up the 'default' namespace uid
    #
    headers = {'Authorization': bearer_token['token_type'] + ' ' + bearer_token['access_token']}
    response = requests.get(env.TENANT_HOST + '/tenants/getTenantOnPrem',
                            headers=headers, verify=False).json()
    namespaces = response['namespaces']
    for namespace in namespaces:
        if namespace['name'] == 'default':
            return namespace['uid']
    return None
