import requests
import env
from requests.packages.urllib3.exceptions import InsecureRequestWarning


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_tenant_id(auth):

  bearerToken = auth[0]

  headers = {'Authorization': bearerToken['token_type'] + ' ' + bearerToken['access_token']}
  return requests.get(env.TENANT_HOST + '/tenants/getTenantOnPrem', headers=headers, verify=False).json()['id']
