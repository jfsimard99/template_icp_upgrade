# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================


import os
import time
from datetime import datetime
import json
import requests
import auth as auth
import tenant as tenant
from logger import TestLogger
import env
import hcl
import random, string
from retrying import retry

logger = TestLogger(__name__)
POLL_INTERVAL = 60  # poll the job status every time 1 minutes


class IaaS(object):
    '''
    IaaS APIs
    '''

    def __init__(self):
        self._authenticate()
        self.tenant_id = tenant.get_tenant_id(self.bearer_token, self.org_guid, self.space_guid)
        self.logger = TestLogger(__name__)

    def _authenticate(self):
        auth_response = auth.authenticate()
        self.bearer_token = auth_response[0]
        self.org_guid = auth_response[1]
        self.space_guid = auth_response[2]

    def _get_request_params(self):
        return {'ace_orgGuid': self.org_guid, 'cloudOE_spaceGuid': self.space_guid, 'tenantId': self.tenant_id}

    def _get_request_header(self):
        return {'Authorization': self.bearer_token['token_type'] + ' ' + self.bearer_token['access_token'],
                'Accept': 'application/json'}


    def _get_variable_value(self, parameters, param):
        try:
            # use 'default', if not found, try 'value'
            value = None
            if 'autogenerate' in parameters['variable'][param]:
                value =  _generate_value(parameters['variable'][param]['autogenerate'])
            elif 'default' in parameters['variable'][param]:
                value = parameters['variable'][param]['default']
            else:
                value = parameters['variable'][param]['value']
            return value
        except KeyError:
            self.logger.error('Unable to find a value for variable: %s' %param)
            raise # re-raise


    def _build_request_parameters_old(self, parameters):
        # old-style
        request_parameters = {} # was None, now empty Hash
        for param in parameters['variable']:
            request_parameters[param] = self._get_variable_value(parameters, param)
        return request_parameters


    def _build_request_parameters_camVariables(self, parameters, camVariables):
        for varMap in camVariables:
            if not 'default' in varMap and not 'value' in varMap:
                # need to set a value for this camVariable entry
                if not 'name' in varMap: raise ValueError("Missing 'name' in: %s", varMap)
                varMap['value'] = self._get_variable_value(parameters, varMap['name'])
        return camVariables


    def _build_request_parameters(self, parameters, camVariables):
        request_parameters = None
        # request_parameters have two different formats, based on whether we
        # are using camvariables.json or not
        if not camVariables:
            request_parameters = self._build_request_parameters_old(parameters)
        else:
            request_parameters = self._build_request_parameters_camVariables(parameters, camVariables)
        return request_parameters


    def deploy(self, stack_name, template, parameters, camVariables, retry=True):
        '''
        Deploys the template
        '''

        template_format = "JSON" if template.strip().startswith("{") else "HCL"
        # parse the template and find the provider
        template_parsed = hcl.loads(template) # parse the JSON/HCL template into dict
        template_provider = template_parsed['provider'].keys()[0]

        self.logger.info('Deploying %s...' % stack_name)
        # find an appropriate cloud connection id
        cloud_connection = self.get_cloud_connection(template_provider)

        request_data = {
            "name": stack_name,
            "template_type": "Terraform",
            "template_format": template_format,
            "cloud_connection_ids": [
                str(cloud_connection['id'])
            ],
            "template": template,
            "catalogName": stack_name,
            "catalogType": "starter",
            "tenantId": self.tenant_id,
            "parameters": self._build_request_parameters(parameters, camVariables)
        }

        request_header = self._get_request_header()
        request_header['Content-Type'] = 'application/json'
        _request_data = json.dumps(request_data)

        response = requests.post(env.IAAS_HOST + '/stacks',
                                 data=_request_data,
                                 params=self._get_request_params(),
                                 headers=request_header,
                                 timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.deploy(stack_name, template, parameters, retry=False)
        if response.status_code != 200:
            raise Exception(
                "Failed to create stack %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" % (
                    request_data['name'], response.status_code, response.headers, response.content, response.request.url,
                    response.request.headers, response.request.body))

        stack = response.json()
        stack_id = stack['id']

        response = requests.post(env.IAAS_HOST + '/stacks/' + stack_id + '/create',
                                 data=json.dumps(stack),
                                 params=self._get_request_params(),
                                 headers=request_header,
                                 timeout=60)

        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.deploy(stack_name, template, parameters, retry=False)
        if response.status_code != 200:
            raise Exception(
                "Failed to deploy %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                (request_data['name'], response.status_code, response.headers, response.content, response.request.url,
                 response.request.headers, response.request.body))

        return response.json()

    def handleAuthError(self, response, retry):
        if retry:
            self.logger.warning(
                'Authentication error\nstatus code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s' % (
                    response.status_code, response.headers, response.content, response.request.url,
                    response.request.headers, response.request.body))
            self._authenticate()
        else:
            raise AuthException(
                'Authentication error\nstatus code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s' % (
                    response.status_code, response.headers, response.content, response.request.url,
                    response.request.headers, response.request.body))

    def get_cloud_connections(self):
        '''
        Retrieves all cloud connections
        '''
        request_header = self._get_request_header()
        return requests.get(env.IAAS_HOST + '/cloudconnections',
                            params=self._get_request_params(),
                            headers=request_header,
                            timeout=60)

    def delete(self, stack, retry=True):
        '''
        Delete the stack from IaaS
        '''
        self.logger.info('Deleting %s' % stack['name'])
        request_header = self._get_request_header()
        response = requests.delete(env.IAAS_HOST + '/stacks/' + stack['id'],
                                   params=self._get_request_params(),
                                   headers=request_header,
                                   timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.delete(stack, retry=False)
        if response.status_code > 300:
            raise Exception(
                "Failed to delete %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                (stack['name'], response.status_code, response.headers, response.content, response.request.url,
                 response.request.headers, response.request.body))

    def destroy(self, stack, retry=True):
        '''
        Destroy the stack from the infrastructure
        '''
        self.logger.info('Destroying %s' % stack['name'])
        request_header = self._get_request_header()
        response = requests.post(env.IAAS_HOST + '/stacks/' + stack['id'] + '/delete',
                                 data=json.dumps(stack),
                                 params=self._get_request_params(),
                                 headers=request_header,
                                 timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.destroy(stack, retry=False)
        if response.status_code > 300:
            raise Exception(
                "Failed to destroy %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                (stack['name'], response.status_code, response.headers, response.content, response.request.url,
                 response.request.headers, response.request.body))


    # retry: 10 times to get stack details, with 1sec exponential backoff (max 10-sec between tries)
    @retry(stop_max_attempt_number=10, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def retrieve(self, stack):
        '''
        Retrieves the stack details
        '''
        # self.logger.info('Retrieving the stack details')
        request_header = self._get_request_header()
        return requests.post(env.IAAS_HOST + '/stacks/' + stack['id'] + '/retrieve',
                             params=self._get_request_params(),
                             headers=request_header,
                             timeout=60)

    def waitForSuccess(self, stack, timeoutInSeconds):
        '''
        Wait until the stack job (deploy or destroy) finishes successfully
        '''

        sleep_time = POLL_INTERVAL
        count = 0

        while True:
            self.logger.info("Waiting for job of stack id %s" % stack['id'])
            response = self.retrieve(stack)
            if response.status_code == 401:
                self.logger.warning(
                    'Authentication error\nstatus code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s' % (
                        response.status_code, response.headers, response.content, response.request.url,
                        response.request.headers, response.request.body))
                self._authenticate()
                continue
            if response.status_code != 200:
                self.logger.error(
                    "Invalid response status code %s\nresponse:\n%s\n\nrequest url:\n%s" %
                    (response.status_code, response.content, response.request.url))

            if response.json()['status'] == "SUCCESS":
                self.logger.info("Job for stack id %s finished successfully." % stack['id'])
                return response.json()
            elif response.json()['status'] != "IN_PROGRESS":
                self.logger.info(json.dumps(response.json(), indent=4, separators=(',',': ')))
                raise Exception("Job for stack id %s failed with status %s" % (stack['id'], response.json()['status']))

            count += 1
            if count > (timeoutInSeconds / sleep_time):
                raise Exception("The job for stack %s did not complete in %s." % (stack['id'], timeoutInSeconds))
            #
            # sleep before polling the job result
            #
            time.sleep(sleep_time)

    def get_cloud_connection(self, template_provider, retry=True):
        '''
        Retrieves the cloud connection based on the template provider
        '''
        cloud_connection_name = None
        if template_provider.lower() == 'amazon ec2' or template_provider.lower() == 'amazonec2' or template_provider.lower() == 'aws':
            cloud_connection_name = os.environ['AWS_CLOUD_CONNECTION']
        elif template_provider.lower() == 'ibm cloud' or template_provider.lower() == 'ibmcloud':
            cloud_connection_name = os.environ['IBMCLOUD_CLOUD_CONNECTION']
        elif template_provider.lower() == 'vsphere' or template_provider.lower() == 'vmware':
            cloud_connection_name = os.environ['VMWARE_CLOUD_CONNECTION']
        else:
            raise Exception('Invalid template provider %s' % template_provider)

        request_header = self._get_request_header()
        response = requests.get(env.IAAS_HOST + '/cloudconnections',
                                params=self._get_request_params(),
                                headers=request_header,
                                timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.get_cloud_connection(template_provider, retry=False)
        if response.status_code != 200:
            raise Exception(
                "Failed to retrieve the cloud connections, status code %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s"
                % (response.status_code, response.headers, response.content, response.request.url,
                   response.request.headers, response.request.body))

        try:
            cloud_connections = response.json()
        except:
            raise Exception(
                "Failed to parse JSON\nstatus code%s\nresponse headers:\n%s\nresponse\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                (response.status_code, response.headers, response.content, response.request.url,
                 response.request.headers, response.request.body))
        for cloud_connection in cloud_connections:
            if cloud_connection['name'] == cloud_connection_name:
                return cloud_connection

        raise Exception('Cloud connection %s does not exist' %
                        cloud_connection_name)


def _generate_password():
    rnd = random.SystemRandom()
    special_chars = '!()-._~@#'
    all_chars = string.ascii_letters + string.digits + special_chars
    password = ''

    # loop until we generate a password that is complex enough
    #   has at least one lower-case letter, one upper-case, one digit, one special
    while (not (any((c in string.ascii_lowercase) for c in password)) or
           not (any((c in string.ascii_uppercase) for c in password)) or
           not (any((c in string.digits) for c in password)) or
           not (any((c in special_chars) for c in password))):
        password = ''.join(rnd.choice(all_chars) for i in range(10)) # length 10
    return password


def _generate_value(type):
    if type == 'sshkey':
        from Crypto.PublicKey import RSA
        return RSA.generate(2048).publickey().exportKey('OpenSSH')
    elif type == 'hostname':
        timestamp = datetime.now()
        return 'CAMContent-%s' % datetime.strftime(timestamp, '%H%M%S%f')
    elif type == 'sshkeyname':
        timestamp = datetime.now()
        return 'testkey%s' % datetime.strftime(timestamp, '%H%M%S%f')
    elif type == 'datacenter':
        return random.choice(['dal05','dal06','dal09','dal10','hou02','mon01','sjc01 ','sea01','tor01','wdc01','wdc04'])
    elif type == 'acct':
        return '1160447'
    elif type == 'password':
        return _generate_password()
    elif type == 'vpcname':
        timestamp = datetime.now()
        return  'starterpack%s' % datetime.strftime(timestamp, '%H%M%S%f')
    raise Exception('Invalid autogenerate type %s' % type)


class AuthException(Exception):
    pass
