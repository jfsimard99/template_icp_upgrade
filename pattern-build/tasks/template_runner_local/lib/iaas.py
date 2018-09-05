# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import os
from datetime import datetime
import time
import json
import requests
import urllib
from lib.logger import TestLogger
import local.env as env

import hcl
import random, string
from retrying import retry

from requests.packages.urllib3.exceptions import InsecureRequestWarning
from lib.translate import resolve_parameters

if env.ENV == 'local':
    import local.env as env
    import local.tenant as tenant
    import local.auth as auth
else:
    import saas.env as env
    import saas.tenant as tenant
    import saas.auth as auth

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

POLL_INTERVAL = 120  # poll the job status every time 2 minutes


class IaaS(object):
    '''
    IaaS APIs
    '''

    def __init__(self):
        self.verify = os.environ['ENV'] != 'local'
        self._authenticate()

        auth = [self.bearer_token, self.org_guid, self.space_guid]
        self.tenant_id = tenant.get_tenant_id(auth)

        self.request_params = {
            'ace_orgGuid': self.org_guid,
            'cloudOE_spaceGuid': self.space_guid,
            'tenantId': self.tenant_id
            }
        self._remove_none(self.request_params)
        self.logger = TestLogger(__name__)

    def _authenticate(self):
        auth_response = auth.authenticate()
        self.bearer_token = auth_response[0]
        self.org_guid = auth_response[1]
        self.space_guid = auth_response[2]

    def _get_request_header(self):
        return {'Authorization': self.bearer_token['token_type'] + ' ' + self.bearer_token['access_token'], 'Accept': 'application/json'}

    def _get_request_params(self):
        return self.request_params

    def _remove_none(self, obj):
        rem = []
        for i in obj:
            if not obj[i]:
                rem.append(i)
        for i in rem:
            del obj[i]

    def _get_variable_value(self, parameters, param):
        try:
            # use 'default', if not found, try 'value'
            value = None
            if 'autogenerate' in parameters['variable'][param]:
                # print "************"
                # print parameters['variable'][param]['autogenerate']
                value =  _generate_value(parameters['variable'][param]['autogenerate'])
            elif 'default' in parameters['variable'][param]:
                value = parameters['variable'][param]['default']
            else:
                value = parameters['variable'][param]['value']

            # print value
            # print "************"
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
        # print camVariables
        updated_parameters = {}
        for varMap in camVariables:
            if not 'default' in varMap and not 'value' in varMap:
                # print "BB2" + varMap
                # need to set a value for this camVariable entry
                if not 'name' in varMap: raise ValueError("Missing 'name' in: %s", varMap)
                # print varMap['name']
                varMap['default'] = self._get_variable_value(parameters, varMap['name'])
        # print "#########"
        # print   camVariables

        return camVariables

    def _build_request_parameters(self, parameters, camVariables):
        request_parameters = None
        if 'input_datatypes' in camVariables:
            request_parameters = camVariables
            request_parameters['template_input_params'] = self._build_request_parameters_camVariables(parameters, camVariables['template_input_params'])
        elif 'output_datatype' in camVariables and camVariables['output_datatype'] == 'advanced_content_runtime_chef':
            request_parameters = self._build_request_parameters_camVariables(parameters, camVariables['template_input_params'])
        else:
            request_parameters = self._build_request_parameters_camVariables(parameters, camVariables)
        return request_parameters

    def deploy(self, stack_name, template_id, template, parameters, camVariables, retry=True, use_case='default'):
        '''
        Deploys the template
        '''
        self.logger.info('Deploying %s' % stack_name)
        self.logger.info('Deploygin template_id %s' % template_id)

        template_format = "JSON" if template.strip().startswith("{") else "HCL"

        # parse the template and find the provider
        template_parsed = hcl.loads(template) # parse the JSON/HCL template into dict
        #self.logger.info('template_parsed %s' % template_parsed)
        template_provider=""
        while (template_provider == ""):
            for provider in template_parsed['provider'].keys():
                self.logger.info('template_provider_parsed %s' % provider)
                if provider.lower() == 'amazon ec2' or  provider.lower() == 'amazonec2' or  provider.lower() == 'aws':
                    template_provider = provider
                    break
                elif provider.lower == 'vmware vsphere' or provider.lower() == 'vsphere' or  provider.lower() == 'vmware':
                    template_provider = provider
                    break
                elif provider.lower() == 'ibm cloud' or provider.lower() == 'ibmcloud' or provider.lower() == 'ibm':
                    template_provider = provider
                    break


        # template_provider = template_parsed['provider'].keys()[0]
        self.logger.info('template_provider %s' % template_provider)
        # find an appropiate cloud connection id
        cloud_connection = self.get_cloud_connection(template_provider)

        # build the request data
        #template_content = json.loads(template['manifest']['template']['templateData'])
        #template_content = template['manifest']['template']['templateData']

        # determine the catalog type
        #try:
        #    catalog_type = template['type'] # prebuilt or starter (bring your own)
        #except KeyError:
        #    catalog_type = 'starter'

        # Ticket 1855 - Add a translation and override file environment
        # TEMPLATE_TRANSLATION set by Travis indicates the Translation type
        if os.getenv('TEMPLATE_TRANSLATION', None) and os.getenv('TEMPLATE_TRANSLATION').upper() == 'TRUE':
            if os.path.isfile(os.getenv('OVERRIDE_FILE', None)):
                override_file = open(os.getenv('OVERRIDE_FILE', None))
                override_variables = json.load(override_file)
                override_file.close()
            else:
                override_variables = {}

            translation_file = open(os.getenv('TRANSLATION_FILE', None))
            translation_variables = json.load(translation_file)
            translation_file.close()
        """
        Get the data types for template
        """
        template_details=self.get_template_details(template_id)
        """
        Get the advanced_content_runtime_chef data objects.
        Used downstream to find the instance id for content runtime
        created using rake task.
        """        
        acrdataobjects=self.getDataObjects(template_details,"advanced_content_runtime_chef")

        # 1891, if using translations, pass them to update_cam_variables
        if os.getenv('TEMPLATE_TRANSLATION', None).upper()=='TRUE':
            updatedCamVariables = self.update_cam_variables(cloud_connection, camVariables, translation_variables=translation_variables,acrdataObjects=acrdataobjects)
            updatedCamVariables, iplist = resolve_parameters(override_variables, translation_variables, updatedCamVariables, template_provider)
            self.iplist = iplist
            parameters = self._build_request_parameters(parameters, _decode_dict(updatedCamVariables))
        else:
            updatedCamVariables = self.update_cam_variables(cloud_connection, camVariables,acrdataObjects=acrdataobjects)
            parameters = self._build_request_parameters(parameters, updatedCamVariables)

        request_data = {
            "cloud_connection_ids": [
                str(cloud_connection['id'])
            ],
            "forceCreate": "true",
            "name": stack_name,
            "namespaceId": "default",
            "parameters": parameters,
            "template_type": "Terraform",
            "template_format": template_format,
            "templateId": template_id,
            "tenantId": self.tenant_id
        }

        # Starting in CAM 2.1.0.2, the namespace resolution happens during the deploy request. If you are
        # running with an earlier version of CAM, comment this part out.
        if 'input_datatypes' in camVariables:
            inputDataObj=[]
            camInputDatatypes = camVariables['input_datatypes']
            if camInputDatatypes:
                template_details=self.get_template_details(template_id)
                for camInputDatatype in camInputDatatypes:
                    if camInputDatatype['name'] and camInputDatatype['name'] == "bastionhost":
                        dataobjects=self.getDataObjects(template_details,"bastionhost")
                        bastionhostvalue=None
                        if 'bastionhostobj' in override_variables:
                            bastionhostvalue=override_variables['bastionhostobj']                        
                        if not bastionhostvalue and 'bastionhostobj' in translation_variables['test_data']:
                            bastionhostvalue=translation_variables['test_data']['bastionhostobj']
                        if not bastionhostvalue:
                            #bastionhostvalue="Default - No Bastion Host Required"
                            bastionhostvalue="DefaultNoBastionHostRequired"
                        dataObject=self.getDataObject(dataobjects,bastionhostvalue)
                        inputDataObj.append(dataObject)
                    if camInputDatatype['name'] and camInputDatatype['name'] == "httpproxy":
                        dataobjects=self.getDataObjects(template_details,"httpproxy")
                        httpproxyvalue=None
                        if 'httpproxy' in override_variables:
                            httpproxyvalue=override_variables['httpproxy']                        
                        if not httpproxyvalue and 'httpproxy' in translation_variables['test_data']:
                            httpproxyvalue=translation_variables['test_data']['httpproxy']
                        if not httpproxyvalue:
                            #bastionhostvalue="Default - No Bastion Host Required"
                            httpproxyvalue="DefaultNoProxyRequired"
                        dataObject=self.getDataObject(dataobjects,httpproxyvalue)
                        inputDataObj.append(dataObject)                        
                    """
                    For advanced_content_runtime_chef, if content runtime stack ise created using 
                    rake create_cloud_connections then get it from get_default_instance_ids.
                    If not found use harcoded instanceid values.
                    """
                    if camInputDatatype['name'] and camInputDatatype['name'] == "advanced_content_runtime_chef":
                        dataobjects=self.getDataObjects(template_details,"advanced_content_runtime_chef")
                        (instance_id,advcr)=self.get_default_instance_ids(cloud_connection, dataobjects)
                        if instance_id and advcr:
                            inputDataObj.append(advcr)
                        else:
                            advcr={'id': self.get_instance_ids(cloud_connection, translation_variables)[0],'datatype':'advanced_content_runtime_chef'}
                            inputDataObj.append(advcr)
                self.logger.info('inputDataObj %s' % (inputDataObj))
                request_data['input_dataobjects'] = inputDataObj

        # request_parameters = {}
        # for param in parameters:
        #     if 'autogenerate' in param:
        #         request_parameters[param['name']] = _generate_value(
        #             param['autogenerate'])
        #     else:
        #         request_parameters[param['name']] = param['value']
        # # add the request parameters
        # request_data['parameters'] = request_parameters

        request_header = self._get_request_header()
        request_header['Content-Type'] = 'application/json'

        _request_data = json.dumps(request_data)
        # print "$$$$$$$$"
        # print _request_data
        response = requests.post(env.IAAS_HOST + '/stacks',
                                 data=_request_data,
                                 headers=request_header,
                                 params=self._get_request_params(),
                                 verify=self.verify,
                                 timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.deploy(stack_name, template, parameters, retry=False)
        if response.status_code != 200:
            raise Exception("Failed to create stack %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" % (
                request_data['name'], response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

        stack = response.json()
        return stack

    def handleAuthError(self, response, retry):
        if retry:
            self.logger.warning('Authentication error\nstatus code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s' % (
                    response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))
            self._authenticate()
        else:
            raise AuthException('Authentication error\nstatus code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s' % (
                    response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

    def get_cloud_connections(self):
        '''
        Retrieves all cloud connections
        '''
        request_header = self._get_request_header()
        return requests.get(env.IAAS_HOST + '/cloudconnections',
                             headers=request_header,
                             params=self._get_request_params(),
                             verify=self.verify,
                             timeout=60)

    def get_templates(self):
        request_header = self._get_request_header()
        return requests.get(env.IAAS_HOST + '/templates',
                             headers=request_header,
                             params=self._get_request_params(),
                             verify=self.verify,
                             timeout=60)

    def get_template_details(self, id):
        self.logger.info('Enter get_template_details %s' % (id))
        request_headers = self._get_request_header()
        details = '/templates/getTemplateDetails?includeDataObjects=true&includeConnections=true'
        data={"id":id}
        result= requests.post(env.IAAS_HOST + details,
                                data,
                                headers=request_headers,
                                params=self._get_request_params(),
                                verify=self.verify,
                                timeout=60)       
        self.logger.info('Exit get_template_details %s' % (result)) 
        return result

    def getDataObjects(self, template_details, datatypename):
        self.logger.info('Enter getDataObjects %s,%s' % (template_details, datatypename))
        dataObjs=None
        if template_details: 
            template_details_json = template_details.json()
            if template_details_json and "datatypes" in template_details_json:
                datatypes=template_details_json["datatypes"]
                self.logger.info('datatypes %s' % (datatypes))
                if datatypes:
                    for datatype in datatypes:
                        self.logger.info('datatypes name %s' % (datatype['name']))
                        if datatype['name'] == datatypename:    
                            dataObjs = datatype['dataobjects']
                            self.logger.info('Exit get_template_details %s' % (dataObjs)) 
                            return dataObjs                            
        self.logger.info('Exit get_template_details %s' % (dataObjs)) 
        return dataObjs

    def getDataObject(self, dataobjects, dataobjname):
        self.logger.info('Enter getDataObject %s,%s' % (dataobjects, dataobjname))
        dataobjectval=None
        if dataobjects and dataobjname:
            for dataobject in dataobjects:
                self.logger.info('dataobject name %s' % (dataobject['name']))
                if dataobject['name'] == dataobjname:
                    dataobjectval = dataobject
                    self.logger.info('Exit getDataObject %s' % (dataobjectval)) 
                    return dataobjectval
        self.logger.info('Exit getDataObject %s' % (dataobjectval)) 
        return dataobjectval

    def import_template(self, github_hostname, github_repo_url, github_path, github_branch, github_token, type=None, retry=True):
        """ Makes an import template request """
        request_data = {
            'template_source': {},
            'template_type': 'Terraform'
        }
        request_data['template_source'][github_hostname] = {
            'url': github_repo_url,
            'dir': github_path,
            'ref': github_branch,
            'token': github_token
        }
        if type:
            request_data['type'] = type

        self.logger.info("Request data: %s" % request_data)

        request_headers = self._get_request_header()
        request_headers['Content-Type'] = 'application/json'

        response = requests.post(env.IAAS_HOST + '/templates/createFromSource',
                                 data=json.dumps(request_data),
                                 headers=request_headers,
                                 params=self._get_request_params(),
                                 verify=self.verify,
                                 timeout=60)

        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.import_template(github_hostname, github_repo_url, github_path, github_branch, github_token, retry=False)
        if response.status_code != 200:
            raise Exception("Failed to import template %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" % (
                github_repo_url, response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

        return response.json()['id']

    def delete_template(self, template_id):
        request_header = self._get_request_header()
        response = requests.delete(env.IAAS_HOST + '/templates/%s' % template_id,
                                   headers=request_header,
                                   params=self._get_request_params(),
                                   verify=self.verify,
                                   timeout=60)

        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.delete_template(template_id)
        if response.status_code != 200:
            raise Exception("Failed to delete template %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" % (
                template_id, response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

    def delete(self, stack, retry=True):
        '''
        Delete the stack from IaaS
        '''
        self.logger.info('Deleting %s' % stack['name'])
        request_header = self._get_request_header()
        response = requests.delete(env.IAAS_HOST + '/stacks/' + stack['id'],
                                   headers=request_header,
                                   params=self._get_request_params(),
                                   verify=self.verify,
                                   timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.delete(stack, retry=False)
        if response.status_code > 300:
            raise Exception("Failed to delete %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                    (stack['name'], response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

    # Ticket 1855 - Add a translation and override file environment
    # TEMPLATE_TRANSLATION set by Travis indicates the Transaltion type

    def _refresh_ip_pool(self):
        '''
        Refresh the IP Pool if TEMPLATE_TRANSLATION is set to true
        '''
        if os.getenv('TEMPLATE_TRANSLATION', None).upper()=='TRUE':
            translation_file = open(os.getenv('TRANSLATION_FILE', None))
            translation_variables = json.load(translation_file)
            translation_file.close()

            if translation_variables['test_data']['provider'] == "minipam":
                for ip in self.iplist:
                    response = requests.get(translation_variables['test_data']['minipam_url'] + "/free?ip_address="+ ip)
        return True

    def destroy(self, stack, retry=True):
        '''
        Destroy the stack from the infrastructure
        '''
        self.logger.info('Destroying %s' % stack['name'])
        request_header = self._get_request_header()
        response = requests.post(env.IAAS_HOST + '/stacks/' + stack['id'] + '/delete',
                                 data=json.dumps(stack),
                                 headers=request_header,
                                 params=self._get_request_params(),
                                 verify=self.verify,
                                 timeout=60)
        self._refresh_ip_pool()
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.destroy(stack, retry=False)
        if response.status_code > 300:
            raise Exception("Failed to destroy %s, status code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                    (stack['name'], response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))


    # retry: 10 times to get stack details, with 1sec exponential backoff (max 10-sec between tries)
    @retry(stop_max_attempt_number=10, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def retrieve(self, stack):
        '''
        Retrieves the stack details
        '''
        request_header = self._get_request_header()
        return requests.post(env.IAAS_HOST + '/stacks/' + stack['id'] + '/retrieve',
                             headers=request_header,
                             params=self._get_request_params(),
                             verify=self.verify,
                             timeout=60)

    def retrieveAll(self):
        '''
        Retrieves all stacks
        '''
        request_header = self._get_request_header()
        return requests.get(env.IAAS_HOST + '/stacks',
                             headers=request_header,
                             params=self._get_request_params(),
                             verify=self.verify,
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
                self.logger.warning('Authentication error\nstatus code is %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s' % (
                    response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))
                self._authenticate()
                continue
            if response.status_code != 200:
                self.logger.error("Invalid response status code %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                                     (response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))
                continue

            if response.json()['status'] == "SUCCESS":
                self.logger.info("Job for stack id %s finished successfully." % stack['id'])
                return response.json()
            elif response.json()['status'] != "IN_PROGRESS":
                self.logger.info(json.dumps(response.json(), indent=4, separators=(',',': ')))
                raise Exception("Job for stack id %s failed with status %s" % (stack['id'], response.json()['status']))

            count += 1
            if count > (timeoutInSeconds / sleep_time):
                raise Exception("The job for stack %s did not complete in %s." % (
                                stack['id'], timeoutInSeconds))

            #
            # sleep before polling the job result
            #
            time.sleep(sleep_time)

    def create_cloud_connection(self, template_provider, data, retry=True):
        self.logger.info("Template Provider %s ." % template_provider)
        # self.logger.info("request data %s ." % data)

        request_headers = self._get_request_header()
        request_headers['Content-Type'] = 'application/json'
        request_data = data.copy()
        request_data['providerId'] = self.get_provider_id(template_provider)
        response = requests.post(env.IAAS_HOST + '/cloudconnections',
                                 data=json.dumps(request_data),
                                 headers=request_headers,
                                 params=self._get_request_params(),
                                 verify=self.verify,
                                 timeout=60)

        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.create_cloud_connection(type, data, retry=False)
        if response.status_code != 200:
            raise Exception("Failed to create the cloud connections, status code %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s"
                            % (response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

    def get_cloud_connection(self, template_provider, retry=True):
        '''
        Retrieves the cloud connection based on the template provider
        '''
        cloud_connection_name = None

        if template_provider.lower() == 'amazon ec2' or  template_provider.lower() == 'amazonec2' or  template_provider.lower() == 'aws':
            cloud_connection_name = os.environ['AWS_CLOUD_CONNECTION']
            self.cloud_connection_type = 'aws'
        elif template_provider.lower == 'vmware vsphere' or template_provider.lower() == 'vsphere' or  template_provider.lower() == 'vmware':
            cloud_connection_name = os.environ['VSPHERE_CLOUD_CONNECTION']
            self.cloud_connection_type = 'vsphere'
        elif template_provider.lower() == 'ibm cloud' or template_provider.lower() == 'ibmcloud' or template_provider.lower() == 'ibm':
            cloud_connection_name = os.environ['IBMCLOUD_CLOUD_CONNECTION']
            self.cloud_connection_type = 'ibm'

        else:
            raise Exception('Invalid template provider %s' % template_provider)

        request_header = self._get_request_header()
        response = requests.get(env.IAAS_HOST + '/cloudconnections',
                                headers=request_header,
                                params=self._get_request_params(),
                                verify=self.verify,
                                timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.get_cloud_connection(template_provider, retry=False)
        if response.status_code != 200:
            raise Exception("Failed to retrieve the cloud connections, status code %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s"
                    % (response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

        try:
            cloud_connections = response.json()
            #self.logger.info('Cloud connections %s' % cloud_connections);
        except:
            raise Exception("Failed to parse JSON\nstatus code%s\nresponse headers:\n%s\nresponse\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s" %
                    (response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))
        for cloud_connection in cloud_connections:

            if cloud_connection['name'] == cloud_connection_name:
                return cloud_connection

        raise Exception('Cloud connection %s does not exist' %
                        cloud_connection_name)

    def get_provider_id(self, template_provider, retry=True):
        request_header = self._get_request_header()
        response = requests.get(env.IAAS_HOST + '/providers',
                                headers=request_header,
                                params=self._get_request_params(),
                                verify=self.verify,
                                timeout=60)
        if response.status_code == 401:
            self.handleAuthError(response, retry)
            return self.get_provider_id(template_provider, retry=False)
        if response.status_code != 200:
            raise Exception("Failed to retrieve the cloud connections, status code %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s"
                    % (response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

        providers = response.json()
        for provider in providers:
            if template_provider.lower() == provider['name'].lower():
                return provider['id']

        return None

    def get_instance_ids(self, cloud_connection, translation_variables=None, dataObjects=None):
        # 1891 - Get connection varibales from the translation fileNone
        instance_ids=None
        #If dataobject is present then get the instance from dataobject
        #If dataobject is absent or get_default_instance_ids returns empty fall back to
        #hardcoded value.
        if dataObjects:
            (instance_ids,acrDataObj) = self.get_default_instance_ids(cloud_connection, dataObjects)
            if instance_ids:
                return instance_ids
        self.logger.info('Use harcoded instance values')
        if translation_variables:
            instance_ids = [translation_variables['test_data']['content_runtime'][self.cloud_connection_type]]
        else:
            if 'aws' in cloud_connection['name']:  # camc-aws-octravis
                instance_ids = ['5b4d2aa71fce8a00463851ac']
                print "AWS Advanced Content runtime selected"
            elif 'vmware' in cloud_connection['name']:  # camc-vmware-octravis
                instance_ids = ['5b4d1d301fce8a004638518b']  #
                print "VMware Advanced Content runtime selected"
            elif 'ibm' in cloud_connection['name']:  # camc-ibm-octravis
                instance_ids = ['5b4d2e341fce8a00463851b4']  #
                print "IBM Advanced Content runtime selected"
        return instance_ids

    """
    Returns instance id based on camc deployed using rake task create_content_runtimes.
    """
    def get_default_instance_ids(self, cloud_connection, dataObjects):
        self.logger.info('Enter get_default_instance_ids: %s,%s'  % (cloud_connection, dataObjects))
        instance_ids = []
        acrDataObj={}
        dataObjName=None
        if 'aws' in cloud_connection['name']:  # camc-aws-octravis
            dataObjName="camc-aws-octravis"
        elif 'vmware' in cloud_connection['name']:  # camc-vmware-octravis
            dataObjName="camc-vmware-octravis"
        elif 'ibm' in cloud_connection['name']:  # camc-ibm-octravis
            dataObjName="camc-ibm-octravis"
        if dataObjName:
            for dataObject in dataObjects:
                if dataObject['name'] == dataObjName:
                    instance_ids.append(dataObject['id'])
                    acrDataObj=dataObject
                    return (instance_ids,acrDataObj)
        self.logger.info('Exit get_default_instance_ids: %s,%s'  % (instance_ids,acrDataObj))
        return (instance_ids,acrDataObj)

    def update_cam_variables(self, cloud_connection, cam_variables, translation_variables=None, retry=True, acrdataObjects=None):
        # namespaces/resolve has been removed from CAM 2.1.0.2. If you are running with an older version of CAM,
        # then comment out this return statement
        return cam_variables

        if 'input_datatypes' in cam_variables:
            instance_ids = []
            # Get the instance IDs from https://9.5.38.159:30000/cam/api/v1/namespaces/advanced_content_runtime_chef
            # Note: need a token retrieved from POST https://9.5.38.159:30000/cam/v1/auth/camtoken
            #       Headers: "Content-Type: application/json"
            #       Body: {"grant_type": "password", "password": "<w3_pass>", "username": "<w3_id>", "scope": "openid profile email"}
            self.logger.info('Get instance id from update_cam_variables')
            instance_ids = self.get_instance_ids(cloud_connection, translation_variables,acrdataObjects)

            data = {'parameters': cam_variables,
                    'instance_ids': instance_ids}

            request_header = self._get_request_header()
            request_header['Content-Type'] = 'application/json'

            response = requests.post(env.IAAS_HOST + 'namespaces/resolve',
                                     data=json.dumps(data),
                                     headers=request_header,
                                     verify=False,
                                     params=self._get_request_params(),
                                     timeout=60)

            if response.status_code == 401:
                self.handleAuthError(response, retry)
                return self.update_cam_variables(cam_variables, retry=False, acrdataObjects=dataObjects)
            if response.status_code != 200:
                raise Exception("Failed to update the cam variables, status code %s\nresponse headers:\n%s\nresponse:\n%s\n\nrequest url:\n%s\nrequest headers:\n%s\nrequest body:\n%s"
                                % (response.status_code, response.headers, response.content, response.request.url, response.request.headers, response.request.body))

            return response.json()
        else:
            return cam_variables




def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv

def _generate_password():
    rnd = random.SystemRandom()
    #special_chars = '!()-._~@#'
    special_chars = '!().~@#'
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
        return 'camcontent-%s' % datetime.strftime(timestamp, '%H%M%S%f')
    elif type == 'sshkeyname':
        timestamp = datetime.now()
        return 'testkey%s' % datetime.strftime(timestamp, '%H%M%S%f')
    elif type == 'datacenter':
        return random.choice(['dal05','dal06','dal09','dal10','hou02','mon01','sea01','tor01','wdc01','wdc04'])
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
