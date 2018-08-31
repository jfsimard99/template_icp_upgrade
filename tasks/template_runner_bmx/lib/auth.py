# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import os
import requests
import lib.env as env
from logger import TestLogger
from retrying import retry

logger = TestLogger(__name__)

def authenticate():
    bearer_token = _get_bearer_token()
    org_guid = _get_org_guid(bearer_token)
    space_guid = _get_space_guid(bearer_token, org_guid)

    return [bearer_token, org_guid, space_guid]


# retry: 5 times to get bearer_token, with 2sec exponential backoff (max 10-sec between tries)
@retry(stop_max_attempt_number=5, wait_exponential_multiplier=2000, wait_exponential_max=10000)
def _get_bearer_token():
    for envvar in ['BLUEMIX_USERNAME', 'BLUEMIX_PASSWORD']:
        if not os.getenv(envvar, None):
            raise Exception("Environment variable '%(envvar)s' must be set to non-empty value" % locals())

    logger.info('Logging into %s as %s...' % (env.AUTH_HOST, os.environ['BLUEMIX_USERNAME']))
    info = requests.get(env.AUTH_HOST + '/info', timeout=60)
    auth_endpoint = info.json()['authorization_endpoint'] + '/oauth/token'

    params = {
        "grant_type": "password",
        "username": os.environ['BLUEMIX_USERNAME'],
        "password": os.environ['BLUEMIX_PASSWORD'] }

    headers = {'authorization': 'Basic Y2Y6',
               'accept': 'application/json',
               'content-type': 'application/x-www-form-urlencoded' }

    response = requests.post(auth_endpoint, params=params, headers=headers, timeout=60)

    if response.status_code < 200 or response.status_code > 299:
        msg = "Failed to get oauth/token, status code is %s\nresponse:\n%s" % (
            response.status_code, response.content)
        logger.error(msg)
        raise Exception(msg)

    return response.json()


def _get_org_guid(bearer_token):
    region = 'us-south'  # TODO: make it more generic
    bmx_org_name = os.environ['BLUEMIX_ORG_NAME']

    request_header = {'Authorization': bearer_token[
        'token_type'] + ' ' + bearer_token['access_token']}
    url = env.AUTH_HOST + '/v2/organizations?region=' + \
        region + '&q=name%3A' + bmx_org_name
    response = requests.get(url, headers=request_header, timeout=60)

    if response.status_code < 200 or response.status_code > 299:
        raise Exception(
            "Unable to get details, status code is %s\nresponse headers:\n%s\nresponse:\n%s\nrequest headers:\n%s\nrequest body:\n%s" % (
                response.status_code, response.headers, response.content,
                response.request.headers, response.request.body))
    response = response.json()

    try:
      return _findKey(response, 'guid')[0]
    except:
      print "Can't find 'guid' for org %s in output: %s" % (bmx_org_name, response)
      raise


def _get_space_guid(bearer_token, org_guid):
    request_header = {'Authorization': bearer_token[
        'token_type'] + ' ' + bearer_token['access_token']}
    url = env.AUTH_HOST + '/v2/organizations/' + org_guid + \
        '/spaces?q=name%3A' + os.environ['BLUEMIX_SPACE_NAME']
    response = requests.get(url, headers=request_header, timeout=60).json()
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
