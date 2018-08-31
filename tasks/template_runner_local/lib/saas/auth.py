import os
import requests
import env

AUTH_HOST = env.AUTH_HOST

def authenticate():
    bearer_token = _get_bearer_token()
    org_guid = _get_org_guid(bearer_token)
    space_guid = _get_space_guid(bearer_token, org_guid)

    return [bearer_token, org_guid, space_guid]


def _get_bearer_token():
    info = requests.get(AUTH_HOST + '/info')
    auth_endpoint = info.json()['authorization_endpoint'] + '/oauth/token'
    params = {
        "grant_type": "password",
        "password": os.environ['BLUEMIX_PASSWORD'],
        "scope": "",
        "username": os.environ['BLUEMIX_USERNAME']
    }
    response = requests.post(auth_endpoint, params=params, auth=('cf', ''))
    return response.json()


def _get_org_guid(bearer_token):
    region = 'us-south'  # TODO: make it more generic

    request_header = {'Authorization': bearer_token[
        'token_type'] + ' ' + bearer_token['access_token']}
    url = AUTH_HOST + '/v2/organizations?region=' + \
        region + '&q=name%3A' + os.environ['BLUEMIX_ORG_NAME']
    response = requests.get(url, headers=request_header).json()
    return _findKey(response, 'guid')[0]


def _get_space_guid(bearer_token, org_guid):
    request_header = {'Authorization': bearer_token[
        'token_type'] + ' ' + bearer_token['access_token']}
    url = AUTH_HOST + '/v2/organizations/' + org_guid + \
        '/spaces?q=name%3A' + os.environ['BLUEMIX_SPACE_NAME']
    response = requests.get(url, headers=request_header).json()
    return _findKey(response, 'guid')[0]


def _findKey(s, key):
    if type(s) == list:
        ret = []
        for i in s:
            ret += _findKey(i, key)
        return ret
    elif type(s) == dict:
        if key in s:
            return [s[key]]
        else:
            ret = []
            for i in s:
                ret += _findKey(s[i], key)
            return ret
    else:
        return []
