import os
import json
from lib.logger import TestLogger
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

if env.ENV == 'local':
    import local.env as env
    import local.tenant as tenant
    import local.auth as auth
else:
    import saas.env as env
    import saas.tenant as tenant
    import saas.auth as auth

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class Catalog:

    def __init__(self):
        self.verify = os.environ['ENV'] != 'local'

        auth_response = auth.authenticate()
        self.bearer_token = auth_response[0]
        self.org_guid = auth_response[1]
        self.space_guid = auth_response[2]
        self.tenant_id = tenant.get_tenant_id([self.bearer_token, self.org_guid, self.space_guid])

        self.request_params = {
            'ace_orgGuid': self.org_guid,
            'cloudOE_spaceGuid': self.space_guid,
            'tenantId': self.tenant_id
            }

        self._remove_none(self.request_params)

        self.logger = TestLogger(__name__)

    def _remove_none(self, obj):
        rem = []
        for i in obj:
            if not obj[i]:
                rem.append(i)
        for i in rem:
            del obj[i]

    def _get_request_header(self):
        return {'Authorization': self.bearer_token['token_type'] + ' ' + self.bearer_token['access_token']}

    def _get_request_params(self):
        return self.request_params

    def get_templates(self):
        """
        Retrieves all the templates from the catalog and saves them locally
        """
        response = requests.get(env.CATALOG_HOST + '/catalogs',
                                headers=self._get_request_header(),
                                params=self._get_request_params(),
                                verify=self.verify)

        templates = response.json()
        for template in templates:
            if template['type'] == 'prebuilt':
                self.logger.info("Retrieving the template %s" % template['name'])
                self.get_template(template['id'])
            else:
                self.logger.warning("Skip the template %s, type %s" % (template['name'], template['type']))

    def get_template(self, template_id):
        """
        Retrieves the template from the catalog and saves the content locally
        """
        response = requests.get(env.CATALOG_HOST + '/catalogs/' + template_id,
                                headers=self._get_request_header(),
                                params=self._get_request_params(),
                                verify=self.verify)
        if response.status_code != 200:
            raise Exception("Failed to retrieve template %s from the catalog, status code is %s" % (
                template_id, response.status_code))

        template_json = response.json()
        variables_json = self.parse_variables(template_json)
        self.persist_template(template_json, variables_json)

    def persist_template(self, template, variables):
        """
        Saves the template content to $CATALOG_HOME/{template_name}
        """
        template_name = template['name']
        template_folder = os.path.join(
            os.environ['CATALOG_HOME'], template_name.replace(" ", "_"))

        self.logger.info("Saving the template %s to %s" % (template['name'], template_folder))
        if not os.path.exists(template_folder):
            os.makedirs(template_folder)

        with open(template_folder + '/template.json', 'w') as outfile:
            json.dump(template, outfile, indent=4, sort_keys=True)

        # check if we need to overwrite the variables.json
        overwrite_variables = True
        if os.path.isfile(os.path.join(template_folder, 'variables.json')):
            with open(os.path.join(template_folder, 'variables.json'), 'r') as variables_file:
                local_variables = json.load(variables_file)
                if compare_variables(variables, local_variables):
                    overwrite_variables = False

        if overwrite_variables:
            with open(os.path.join(template_folder, 'variables.json'), 'w') as outfile:
                json.dump(variables, outfile, indent=4, sort_keys=True)
        else:
            self.logger.info('Variables for template %s are up to date, no need to overwrite...' % template_name)

    def parse_variables(self, template):
        """
        Retrieves the variables defined in the template
        """
        request_body = {
            'template_type': template['manifest']['template_type'],
            'template_format': template['manifest']['template_format'],
            'template_content': template['manifest']['template']['templateData']

        }
        response = requests.post(env.IAAS_HOST + '/templates/parsevariables',
                                 headers=self._get_request_header(),
                                 data=request_body,
                                 params=self._get_request_params(),
                                 verify=self.verify)

        if response.status_code != 200:
            raise Exception("Failed to parse variables for %s, status code is %s\nRequest Headers:\n%s\nRequest URL:%s" % (
                template['name'], response.status_code, response.request.headers, response.request.url))

        variables = response.json()
        for variable in variables:
            variable['value'] = ""
        return variables


def get_local_templates():
    """
    Retrieves all the template names that were saved on the filesystem
    """
    catalogdir = os.environ['CATALOG_HOME']
    return os.listdir(catalogdir)


def get_local_template(template_folder_name):
    """
    Retrieves the template and variables from the local filesystem
    """
    catalogdir = os.environ['CATALOG_HOME']
    template_dir = os.path.join(catalogdir, template_folder_name)

    # retrieve the template
    with open(os.path.join(template_dir, 'template.json')) as template_file:
        template = json.load(template_file)
    #retrieve the variables
    with open(os.path.join(template_dir, 'variables.json')) as variables_file:
        variables = json.load(variables_file)

    return [template, variables]

def compare_variables(variables1, variables2):
    """
    Compare two variables JSON arrays
    It only checks the variable 'name' attributes
    """
    _variables1 = []
    for var in variables1:
        _variables1.append(var['name'])
    _variables2 = []
    for var in variables2:
        _variables2.append(var['name'])

    return sorted(_variables1) == sorted(_variables2)
