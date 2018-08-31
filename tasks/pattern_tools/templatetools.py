# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import sys
import os
import logging
import glob
import yaml
import re
import json

# Tokens
T_EOF                = 'T_EOF'
T_EOL                = 'T_EOL'
T_CHAR               = 'T_CHAR'
T_CLOUD_TYPE         = 'T_CLOUD_TYPE'
T_VERSION            = 'T_VERSION'
T_DESCRIPTION        = 'T_DESCRIPTION'
T_FEATURES           = 'T_FEATURES'
T_SOFTWARE           = 'T_SOFTWARE'
T_MAJOR_VERSIONS     = 'T_MAJOR_VERSIONS'
T_MINOR_VERSIONS     = 'T_MINOR_VERSIONS'
T_PLATFORMS          = 'T_PLATORMS'
T_NODES_DESCRIPTION  = 'T_NODES_DESCRIPTION'
T_SOFTWARE_RESOURCES = 'T_SOFTWARE_RESOURCES'
T_DISK               = 'T_DISK'
T_PORTS              = 'T_PORTS'
T_LIBRARIES          = 'T_LIBRARIES'
T_REPO               = 'T_REPO'
T_NAME               = 'T_NAME'
T_CLOUD_SPECIFIC     = 'T_CLOUD_SPECIFIC'
T_PATH               = 'T_PATH'
T_FILE               = 'T_FILE'
T_BULLETS            = 'T_BULLETS'
T_SHORT_DESCRIPTION  = 'T_SHORT_DESCRIPTION'
T_LONG_DESCRIPTION  = 'T_LONG_DESCRIPTION'


template_types = {'heat': 'heat' + os.sep + '*.yaml',
                  'amazon': 'amazon' + os.sep + 'terraform'+ os.sep + '*.tf',
                  'vmware': 'vmware' + os.sep + 'terraform'+ os.sep + '*.tf',
                  'ibmcloud': 'ibmcloud' + os.sep + 'terraform' + os.sep + '*.tf'}

template_dir = {'heat': 'heat',
                  'amazon': 'amazon' + os.sep + 'terraform',
                  'vmware': 'vmware' + os.sep + 'terraform',
                  'ibmcloud': 'ibmcloud' + os.sep + 'terraform'}

cloud_text = {'heat': 'heat',
              'amazon': 'Amazon EC2',
              'vmware': 'VMware vSphere',
              'ibmcloud': 'IBM'}

cloud_types = ['amazon', 'vmware', 'ibmcloud']

enterprise_dir_identifier = 'Enterprise_Middleware'

def _tokenise(text, token_regexs):

    pos = 0
    tokens = []
    while pos < len(text):
        match = None
        for token_regex in token_regexs:
            pattern, tag = token_regex
            regex = re.compile(pattern)
            match = regex.match(text, pos)
            if match:
                data = match.group(0)
                if tag:
                    token = (data, tag)
                    tokens.append(token)
                break
        if not match:
            sys.stderr.write('Illegal character: %s\n' % text[pos])
            sys.exit(1)
        else:
            pos = match.end(0)
    token = ('T_EOF', 'T_EOF')
    tokens.append(token)
    return tokens

def _merge_dict(org_dict, new_dict):
    mrg_dict = dict(org_dict)
    for key, item in new_dict.items():
        if key in mrg_dict:
            mrg_dict[key] = _merge(org_dict[key], new_dict[key])
        else:
            mrg_dict[key] = item
    return mrg_dict

def _merge_list(org_list, new_list):
    mrg_list = list(org_list)
    for item in new_list:
        if item not in mrg_list:
            mrg_list.append(item)
    return mrg_list

def _merge(org_item, new_item):
    org_type = type(org_item)
    new_type = type(new_item)
    if org_type != new_type:
        print('XXXXX ORGS DO NOT MATCH')

    fn = TYPE_MERGE_FNS.get(org_type, None)
    if fn:
        return fn(org_item, new_item)
    return new_item

def _get_server_roles(in_dict, server_name):

    roles = []
    for resource, item in in_dict['resources'].items():


        if item['type'] == 'IBM::CAMC::SoftwareDeployment':
            if item['properties']['server']['get_resource'] == server_name:
                if item.has_key('properties'):
                    if item['properties'].has_key('data'):
                        if item['properties']['data'].has_key('runlist'):
                            role = item['properties']['data']['runlist']
                            role = re.sub(r'^role\[', '', role)
                            role = re.sub(r']', '', role)
                            roles.append(role)
    return roles

def _get_cookbook_from_role(components, role):

    cookbooks = set([])
    for component in components['components']:
        if component['name'] == role and component.has_key('run_list'):
            for recipe in component['run_list']:
                recipe = re.sub(r'^recipe\[', '', recipe)
                recipe  = re.sub(r'\]', '', recipe)
                cookbook = recipe.split("::")[0]
                cookbooks.add(cookbook)
    return cookbooks

def _get_version_text(template_metadata):

    """

    _get_version_text will return the value of the template version from the
    template_metadata construct


    :param dict template_metadata: Standard Template Metadata dictionary.

    """

    if template_metadata['version']:
        return template_metadata['version']
    else:
        return 'Unknown Version'

def _get_cloud_type(input_text):

    cloud_type = False

    """

    _get_cloud_type will interpret the input_text field and return the cloud type
    based on the first non-text field. For example, '  amazon: someothertext' will return
    'amazon'. If no clouds are present then "None" is returned.


    :param dict input_text: Line of text to be interpretted.


    """

    for cloud in cloud_types:
        regex = '^[ ]*' + cloud + ':'
        if re.search(regex, input_text):
            cloud_type = cloud

    return cloud_type

def _get_cloud_text(cloud_type):

    """

    _get_cloud_text will convert a cloud short name into the actual cloud
    name used in text. This is via a simple lookup to the cloud_text dictionary.


    :param str cloud_type: The short name of the cloud.

    """

    if cloud_text[cloud_type]:
        return cloud_text[cloud_type]
    else:
        return 'Unknown'

def _get_name_text(template_metadata):

    """

    _get_name_text will return the template name based on metadata within the template.


    :param dict template_metadata: Standard Template Metadata dictionary.

    """

    if template_metadata['name']:
        return template_metadata['name']
    else:
        return ' '

def _get_description_text(template_metadata):

    """

    _get_description_text will return the value of the template description.


    :param dict template_metadata: Standard Template Metadata dictionary.

    """

    if template_metadata['description']:
        return template_metadata['description'].replace('\n', '<br>')
    else:
        return ' '

def _get_long_description_text(template_metadata):

    """

    _get_long_description_text will return the value of the template description.


    :param dict template_metadata: Standard Template Metadata dictionary.

    """

    if template_metadata['description']:
        return template_metadata['description'].replace('\n', '')
    else:
        return ' '

def _get_short_description_text(template_metadata):

    """

    _get_short_description_text will return the first line of the description.


    :param dict template_metadata: Standard Template Metadata dictionary.

    """

    if template_metadata['description']:
        line_pos = template_metadata['description'].find('\n')
        if line_pos != -1:
            line = template_metadata['description'][:line_pos]
            return line
        else:
            return template_metadata['description']
    else:
        return ' '

def _get_features_text(template_metadata, cloud_type):

    """

    _get_features_text will return multiline text describing the features
    from the template_metadata, this will be formatted in MD format.
    ### feature1
    feature line1
    feature line2
    ### feature2
    feature line1
    feature line2

    NOTE:, features prefixed with {CLOUD_TYPE}: Some feature text, will only be returned for
    the cloud in question.

    :param dict template_metadata: Standard Template Metadata dictionary.

    """
    features = ""
    if 'features' in template_metadata:
        for feature in sorted(template_metadata['features']):
            features = features + "### " + re.sub('^[0-9]*', '', feature)
            features = features + "\n\n"
            for feature_line in template_metadata['features'][feature].split('\n'):
                if _get_cloud_type(feature_line) == cloud_type or not _get_cloud_type(feature_line):
                  features = features + re.sub(cloud_type + ':', '', feature_line) + '<br>\n'
        return features
    else:
        return ' '

def _get_bullets_text(template_metadata, cloud_type):

    """

    _get_bullets_text will return a json fragment to describe the features.
    For example

        }
         "title": "Clouds",
         "description": "IBM Cloud/Softlayer"
       },

    :param dict template_metadata: Standard Template Metadata dictionary.

    """
    bullets = ""
    feature_length = len(template_metadata['features'])
    iteration = 0
    if 'features' in template_metadata:
        for bullet in sorted(template_metadata['features']):
            iteration = iteration + 1
            bullets = bullets + '{\n'
            bullets = bullets + '    \"title\": \"' + re.sub('^[0-9]*', '', bullet) + '\",' + '\n'

            bullet_text = ""
            for bullet_line in template_metadata['features'][bullet].split('\n'):
                if _get_cloud_type(bullet_line) == cloud_type or not _get_cloud_type(bullet_line):
                    if bullet_line:
                        bullet_text = bullet_text + re.sub(cloud_type + ':', '', bullet_line) + '<br>'

            bullets = bullets + '    \"description\": \"' + bullet_text + '\"'
            bullets = bullets + '}'
            if iteration < feature_length:
                bullets = bullets + ',\n'
            else:
                bullets = bullets + '\n'
        return bullets
    else:
        return ''

def _get_software_text(template_metadata, cookbook_metadata):

    """

    _get_software_text will return a list of software derived from the cookbooks.
    This requires an intersection of cookbooks from template_metadata married to the
    description from cookbook_metadata. The MD format is as follows:

    - software1
    - software2

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """
    software = ""
    cookbooks_used = []
    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook not in cookbooks_used:
                software = software + '- ' + cookbook_metadata[cookbook]['software']['name'] + '\n'
                cookbooks_used.append(cookbook)

    return software

def _get_major_versions_text(template_metadata, cookbook_metadata):

    """

    _get_major_versions_text will return a list of major software versions derived
    from the cookbooks.
    This requires an intersection of cookbooks from template_metadata married to the
    description from cookbook_metadata. The MD format is as follows:

    - software1 version 1
    - software2 version 2

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """
    versions = ""
    cookbooks_used = []
    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook in cookbook_metadata and cookbook not in cookbooks_used:
                for major_version in cookbook_metadata[cookbook]['software']['major_version']:
                    versions = versions + '- ' + cookbook_metadata[cookbook]['software']['name'] + ' ' + major_version + '\n'
                cookbooks_used.append(cookbook)

    return versions

def _get_minor_versions_text(template_metadata, cookbook_metadata):

    """

    _get_minor_versions_text will return a list of minor software versions derived
    from the cookbooks.
    This requires an intersection of cookbooks from template_metadata married to the
    description from cookbook_metadata. The MD format is as follows:

    - software1 version 1
    - software2 version 2

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """
    versions = ""
    cookbooks_used = []
    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook in cookbook_metadata and cookbook not in cookbooks_used:
                for minor_version in cookbook_metadata[cookbook]['software']['minor_version']:
                    versions = versions + '- ' + cookbook_metadata[cookbook]['software']['name'] + ' ' + minor_version + '\n'
                cookbooks_used.append(cookbook)

    return versions

def _get_platforms_supported_text(template_metadata, cookbook_metadata):

    """

    _get_platforms_supported_text will return a list of plaftorms supported by the
    template in question.

    This requires an intersection of cookbooks from template_metadata married to the
    description from cookbook_metadata. The MD format is as follows:

    - Platform version 1
    - Platform version 2

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """
    platforms = ""
    cookbooks_used = []
    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook in cookbook_metadata and cookbook not in cookbooks_used:
                for platform in cookbook_metadata[cookbook]['software']['platforms']:
                    platforms = platforms + '- ' + platform +  '\n'
                cookbooks_used.append(cookbook)

    return platforms


def _get_nodes_description_text(template_metadata, cookbook_metadata, component_metadata):

    """

    _get_nodes_description_text will return a table mapping Nodes to Roles.

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.
    :param dict component_metadata: Aggregated component metadata dictionary.

    """

    nodes_description = "<table>" + "\n"
    nodes_description = nodes_description + "  <tr>" + "\n"
    nodes_description = nodes_description + "    <th>Node Name</th>" + "\n"
    nodes_description = nodes_description + "    <th>Component</th>" + "\n"
    nodes_description = nodes_description + "    <th>Description</th>" + "\n"
    nodes_description = nodes_description + "  </tr>" + "\n"

    for server in template_metadata['servers']:
        for role in template_metadata['servers'][server]['roles']:
            role_description = ""
            for component in component_metadata['components']:
                if component['name'] == role:
                    role_description = component['description']
            nodes_description = nodes_description + "  <tr>" + "\n"
            nodes_description = nodes_description + "    <td>" + server + "</code></td>" + "\n"
            nodes_description = nodes_description + "    <td>" + role + "</code></td>" + "\n"
            nodes_description = nodes_description + "    <td>" + role_description + "</code></td>" + "\n"
            nodes_description = nodes_description + "  </tr>" + "\n"

    nodes_description = nodes_description + "</table>" + "\n"

    return nodes_description

def _get_software_resources_text(template_metadata, cookbook_metadata):

    """

    _get_software_resources_text will return a table of software resources
    for each cookbook relevant to the template.

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """

    cookbooks_used = []
    software_resources = ""

    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook not in cookbooks_used and cookbook in cookbook_metadata:
                software_resources = software_resources + '### ' + cookbook_metadata[cookbook]['software']['name']+ "\n"
                software_resources = software_resources + "<table>" + "\n"
                for prereq in cookbook_metadata[cookbook]['prerequisites']:
                    software_resources = software_resources + "  <tr>" + "\n"
                    software_resources = software_resources + "    <td>" + prereq + "</td>\n"
                    software_resources = software_resources + "    <td>" + cookbook_metadata[cookbook]['prerequisites'][prereq] + "</td>\n"
                    software_resources = software_resources + "  </tr>" + "\n"
                software_resources = software_resources + "</table>" + "\n\n"
                cookbooks_used.append(cookbook)

    return software_resources


def _get_disk_text(template_metadata, cookbook_metadata):

    """

    _get_disk_text will return a table of prerequisite disk requirements for each
    software installed in the template.

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """

    cookbooks_used = []
    disk_resources = ""

    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook not in cookbooks_used and cookbook in cookbook_metadata:
                disk_resources  = disk_resources  + '### ' + cookbook_metadata[cookbook]['software']['name']+ "\n"
                disk_resources  = disk_resources  + "<table>" + "\n"
                for disk in cookbook_metadata[cookbook]['disk']:
                    disk_resources = disk_resources + "  <tr>" + "\n"
                    disk_resources = disk_resources + "    <td>" + disk + "</td>\n"
                    disk_resources = disk_resources + "    <td>" + cookbook_metadata[cookbook]['disk'][disk] + "</td>\n"
                    disk_resources = disk_resources + "  </tr>" + "\n"
                disk_resources = disk_resources  + "</table>" + "\n\n"
                cookbooks_used.append(cookbook)

    return disk_resources

def _get_ports_text(template_metadata, cookbook_metadata):

    """

    _get_ports_text will return a table of ports that are required to be open as
    standard for each software component.

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """

    cookbooks_used = []
    ports_resources = ""

    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook not in cookbooks_used and cookbook in cookbook_metadata:
                ports_resources  = ports_resources  + '### ' + cookbook_metadata[cookbook]['software']['name']+ "\n"
                ports_resources  = ports_resources  + "<table>" + "\n"
                for port in cookbook_metadata[cookbook]['ports']:
                    ports_resources = ports_resources + "  <tr>" + "\n"
                    ports_resources = ports_resources + "    <td>" + port + "</td>\n"
                    ports_resources = ports_resources + "    <td>" + cookbook_metadata[cookbook]['ports'][port] + "</td>\n"
                    ports_resources = ports_resources + "  </tr>" + "\n"
                ports_resources = ports_resources  + "</table>" + "\n\n"
                cookbooks_used.append(cookbook)

    return ports_resources

def _get_libraries_text(template_metadata, cookbook_metadata):

    """

    _get_ports_text will return a table of ports that are required to be open as
    standard for each software component.

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """

    cookbooks_used = []
    libraries_resources = ""

    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook not in cookbooks_used and cookbook in cookbook_metadata:
                libraries_resources  = libraries_resources  + '### ' + cookbook_metadata[cookbook]['software']['name']+ "\n"
                libraries_resources  = libraries_resources  + "<table>" + "\n"
                for platform in cookbook_metadata[cookbook]['os_repository']:
                    for arch in cookbook_metadata[cookbook]['os_repository'][platform]:
                        libraries_resources = libraries_resources + "  <tr>" + "\n"
                        libraries_resources = libraries_resources + "    <td>" + platform + "</td>\n"
                        libraries_resources = libraries_resources + "    <td>" + arch + "</td>\n"
                        libraries_resources = libraries_resources + "    <td>" + cookbook_metadata[cookbook]['os_repository'][platform][arch]['libraries'] + "</td>\n"
                        libraries_resources = libraries_resources + "  </tr>" + "\n"
                libraries_resources = libraries_resources  + "</table>" + "\n\n"
                cookbooks_used.append(cookbook)

    return libraries_resources


def _get_repo_text(template_metadata, cookbook_metadata):

    """

    _get_repo_text will return markdown per product per version to describe the
    neccessary files to contain on the Repository Server in order to successfully install
    the software product in question.

    :param dict template_metadata: Standard Template Metadata dictionary.
    :param dict cookbook_metadata: Aggregated cookbook metadata dictionary.

    """

    cookbooks_used = []
    repo_resources = ""

    for server in template_metadata['servers']:
        for cookbook in template_metadata['servers'][server]['cookbooks']:
            if cookbook not in cookbooks_used and cookbook in cookbook_metadata:
                repo_resources  = repo_resources  + '\n## ' + cookbook_metadata[cookbook]['software']['name'] + "\n"
                repo_resources  = repo_resources  + '\n### Installation' + "\n"
                repo_resources  = repo_resources  + "<table>" + "\n"
                repo_resources = repo_resources + "  <tr>" + "\n"
                repo_resources = repo_resources + "    <th>Version</th>" + "\n"
                repo_resources = repo_resources + "    <th>Arch</th>" + "\n"
                repo_resources = repo_resources + "    <th>Repository Root</th>" + "\n"
                repo_resources = repo_resources + "    <th>File</th>" + "\n"
                repo_resources = repo_resources + "  </tr>" + "\n"
                for version in cookbook_metadata[cookbook]['installation_files']:
                    for arch in cookbook_metadata[cookbook]['installation_files'][version]:
                        repo_resources = repo_resources + "  <tr>" + "\n"
                        repo_resources = repo_resources + "    <td>" + version + "</td>\n"
                        repo_resources = repo_resources + "    <td>" + arch + "</td>\n"
                        if cookbook_metadata[cookbook]['installation_files'][version][arch].has_key('repo_root'):
                            repo_resources = repo_resources + "    <td>" + cookbook_metadata[cookbook]['installation_files'][version][arch]['repo_root'] + "</td>\n"
                        else:
                            repo_resources = repo_resources + "    <td>" + 'not applicable' + "</td>\n"
                        repo_resources = repo_resources + "    <td>"
                        for file in cookbook_metadata[cookbook]['installation_files'][version][arch]['file']:
                            repo_resources = repo_resources + "<br>" + file +"</br>"
                        repo_resources = repo_resources + "</td>\n"
                        repo_resources = repo_resources + "  </tr>" + "\n"
                repo_resources = repo_resources  + "</table>" + "\n"
                if cookbook_metadata[cookbook].has_key('fixpack_files'):
                    repo_resources = repo_resources  + '\n### Fixpack' + "\n"
                    repo_resources = repo_resources  + "<table>" + "\n"
                    repo_resources = repo_resources + "  <tr>" + "\n"
                    repo_resources = repo_resources + "    <th>Fixpack Version</th>" + "\n"
                    repo_resources = repo_resources + "    <th>Arch</th>" + "\n"
                    repo_resources = repo_resources + "    <th>Repository Root</th>" + "\n"
                    repo_resources = repo_resources + "    <th>File</th>" + "\n"
                    repo_resources = repo_resources + "  </tr>" + "\n"
                    for version in cookbook_metadata[cookbook]['fixpack_files']:
                        for arch in cookbook_metadata[cookbook]['fixpack_files'][version]:
                            repo_resources = repo_resources + "  <tr>" + "\n"
                            repo_resources = repo_resources + "    <td>" + version + "</td>\n"
                            repo_resources = repo_resources + "    <td>" + arch + "</td>\n"
                            repo_resources = repo_resources + "    <td>" + cookbook_metadata[cookbook]['fixpack_files'][version][arch]['repo_root'] + "</td>\n"
                            repo_resources = repo_resources + "    <td>"
                            for file in cookbook_metadata[cookbook]['fixpack_files'][version][arch]['file']:
                                repo_resources = repo_resources + "<br>" + file +"</br>"
                            repo_resources = repo_resources + "</td>\n"
                            repo_resources = repo_resources + "  </tr>" + "\n"
                    repo_resources = repo_resources  + "</table>" + "\n"
                cookbooks_used.append(cookbook)

    return repo_resources

def get_template_roots(template_repository_root):

    """

    get_template_roots will find a dictionary of full template root directories.
    It will handle the situation where a single template is to be processed or
    a complete list based on the template_repository_root value.


    :param str template_repository_root: The current directory to search from.

    """

    template_roots = []

    # Determine if we are in a repository with multiple templates
    # else work backwards and try to identify the .yaml file and return a single
    # template_root

    #if os.path.isdir(template_repository_root + os.sep + enterprise_dir_identifier):
    # print template_repository_root
    if "Enterprise_Middleware" in template_repository_root:
        for template_root in glob.glob(template_repository_root + os.sep + '*'):
            if len(glob.glob(template_root + os.sep + template_types['heat'])) > 0:
                template_roots.append(template_root)
    else:

        dir_name = template_repository_root

        while dir_name:

            if len(glob.glob(dir_name + os.sep + template_dir['heat'])) > 0:
                found_root = True
                template_roots.append(dir_name)
                break
            else:
                last_dir = os.path.basename(os.path.normpath(dir_name))
                dir_name = dir_name[:-(len(last_dir)+1)]

    return(template_roots)


def get_template_name(template_root):


    """

    get_template_name will find return the name of the Template. The template
    name is assumed to be the rightmost directory relative to the template_root.


    :param str template_root: The root directory of the Template.

    """

    return os.path.basename(os.path.normpath(template_root)).replace("template_", "")


def get_template_heat(template_root, template_name):

    """

    get_template_heat will return the full path of the HOT Template
    related


    :param str template_root: The root directory of the Template.
    :param str template_name: Name of the template.

    """

    if os.path.isfile(template_root + os.sep+ template_dir['heat'] + os.sep + template_name + '.yaml'):
        return template_root + os.sep + 'heat' + os.sep + template_name + '.yaml'
    else:
        return None


def get_template_dir(template_root, template_type):


    """

    get_template_dir will return a Template Dir for the particular
    template type or return a blank string if one does not exist.


    :param str template_root: The root directory of the Template.
    :param str template_type: Type of template, delimited by cloud type.


    """

    if len(glob.glob(template_root + os.sep + template_types[template_type])) > 0:
        return template_root + os.sep + template_dir[template_type]
    else:
        return ""

def _get_file_text(template_metadata):

    """

    _get_file_text will return the file name that represents the template.


    :param dict template_metadata: Standard Template Metadata dictionary.

    """

    if template_metadata['name']:
        return template_metadata['name']
    else:
        return ' '

def read_heat_template(heat_template):

    """

    read_heat_template will read a HOT Template YAML file and return a
    list structure representing the data.


    :param str heat_template: Full file path to the HOT Template.


    """

    with open(heat_template, 'r') as stream:
        heat_dict = yaml.load(stream)

    return heat_dict


def get_template_data(heat_dict, components):


    """

    get_template_data will generate list of dict structure which describes the template
    in terms of:

    name:
    description:
    features:
    version:
    Server:
        roles:

    :param str heat_dict: A dict structure which describes the HOT Template.
    :param str component_file: Full path to a json file with the aggregated components.


    """

    heat_metadata = {}
    success = True
    error = None

    # Check and assign name and version, fail if not exist
    if heat_dict.has_key('automation_content_template_metadata'):

        if heat_dict['automation_content_template_metadata'].has_key('name'):
            heat_metadata['name'] = heat_dict['automation_content_template_metadata']['name']
        else:
            success = False
            error = 'Missing automation_content_template_metadata:name'
            return success, error, heat_metadata

        if heat_dict['automation_content_template_metadata'].has_key('version'):
            heat_metadata['version'] = heat_dict['automation_content_template_metadata']['version']
        else:
            success = False
            error = 'Missing automation_content_template_metadata:version'
            return success, error, heat_metadata

    else:
            success = False
            error = 'Missing automation_content_template_metadata:'
            return success, error, heat_metadata

    # Set description
    if heat_dict.has_key('description'):
        heat_metadata['description'] = heat_dict['description']
    else:
        success = False
        error = 'Missing description'
        return success, error, heat_metadata

    # Set features
    if heat_dict.has_key('features'):
        heat_metadata['features'] = heat_dict['features']
    elif heat_dict['automation_content_template_metadata'].has_key('features'):
        heat_metadata['features'] = heat_dict['automation_content_template_metadata']['features']

    else:
        success = False
        error = 'Missing features'
        return success, error, heat_metadata

    # Allocate Resources
    servers = {}
    for resource, item in heat_dict['resources'].items():
        if item['type'] == 'OS::Nova::Server':
            server_name = resource
            server_id = item['properties']['name']['get_param']
            roles = _get_server_roles(heat_dict, server_name)
            cookbooks = set([])
            for role in roles:
                cookbook = _get_cookbook_from_role(components, role)
                for new_cookbook in cookbook:
                    cookbooks.add(new_cookbook)
            new_server = {server_name: {'id': server_id, 'roles': roles, 'cookbooks': cookbooks}}
            servers = _merge_dict(servers, new_server)

    heat_metadata['servers'] = servers
    return success, error, heat_metadata

TYPE_MERGE_FNS = {dict: _merge_dict, list: _merge_list}


def create_template_readme(template_metadata, component_metadata, cookbook_metadata, cloud_type):

    """

    create_template_readme will create a markdown version of a template readme based on
    the template_type. Will return a string type object with the full README.
    The return will be a dictionary of {cloud_type: readme}.

    :param dict template_metadata: Dictionary of the template metadata.
    :param str component_metadata: Component metadata taken from the aggregated components.json.
    :param str cookbook_metadata: Cookbook metadata taken from the aggregated cookbook_metadata.json.
    :param str cloud_type: Name of the cloud the readme is targetted at.


    """

    token_regexs = [
        (r'#{NAME}',              T_NAME),
        (r'#{CLOUD_TYPE}',        T_CLOUD_TYPE),
        (r'#{VERSION}',           T_VERSION),
        (r'#{DESCRIPTION}',       T_DESCRIPTION),
        (r'#{SHORT_DESCRIPTION}', T_SHORT_DESCRIPTION),
        (r'#{LONG_DESCRIPTION}',  T_LONG_DESCRIPTION),
        (r'#{FEATURES}',          T_FEATURES),
        (r'#{SOFTWARE}',          T_SOFTWARE),
        (r'#{MAJOR_VERSIONS}',    T_MAJOR_VERSIONS),
        (r'#{MINOR_VERSIONS}',    T_MINOR_VERSIONS),
        (r'#{PLATFORMS}',         T_PLATFORMS),
        (r'#{NODES_DESCRIPTION}', T_NODES_DESCRIPTION),
        (r'#{SOFTWARE_RESOURCES}', T_SOFTWARE_RESOURCES),
        (r'#{DISK}',               T_DISK),
        (r'#{PORTS}',              T_PORTS),
        (r'#{LIBRARIES}',          T_LIBRARIES),
        (r'#{REPO}',               T_REPO),
        (r'#{CLOUD_SPECIFIC}',     T_CLOUD_SPECIFIC),
        (r'.',                     T_CHAR),
        (r'[\n]',                  T_EOL),
        (r'[ \n\t]+',              None),
    ]

    readme = ""
    # Open readme template file and assign full text
    readme_template_file = 'readme_templates' + os.sep + 'template-readme.md'
    readme_files = {}
    readme_template = open(readme_template_file, "r+")
    template_text = readme_template.read()

    #Tokenise readme template file
    tokens = _tokenise(template_text, token_regexs)

    #Cycle through each character and process the metadata
    current_position = 0
    while current_position < len(tokens):
        if tokens[current_position][1] == T_CHAR:
            readme = readme + tokens[current_position][0]

        elif tokens[current_position][1] == T_EOL:
            readme = readme + tokens[current_position][0]

        elif tokens[current_position][1] == T_CLOUD_TYPE:
            cloud_name = _get_cloud_text(cloud_type)
            readme = readme + cloud_name

        elif tokens[current_position][1] == T_VERSION:
            version = _get_version_text(template_metadata)
            readme = readme + version

        elif tokens[current_position][1] == T_NAME:
            name = _get_name_text(template_metadata)
            readme = readme + name

        elif tokens[current_position][1] == T_DESCRIPTION:
            description = _get_description_text(template_metadata)
            readme = readme + description

        elif tokens[current_position][1] == T_SHORT_DESCRIPTION:
            description = _get_short_description_text(template_metadata)
            readme = readme + description

        elif tokens[current_position][1] == T_LONG_DESCRIPTION:
            description = _get_long_description_text(template_metadata)
            readme = readme + description

        elif tokens[current_position][1] == T_FEATURES:
            features = _get_features_text(template_metadata, cloud_type)
            readme = readme + features

        elif tokens[current_position][1] == T_SOFTWARE:
            software = _get_software_text(template_metadata, cookbook_metadata)
            readme = readme + software

        elif tokens[current_position][1] == T_MAJOR_VERSIONS:
            versions = _get_major_versions_text(template_metadata, cookbook_metadata)
            readme = readme + versions

        elif tokens[current_position][1] == T_MINOR_VERSIONS:
            versions= _get_minor_versions_text(template_metadata, cookbook_metadata)
            readme = readme + versions

        elif tokens[current_position][1] == T_PLATFORMS:
            platforms = _get_platforms_supported_text(template_metadata, cookbook_metadata)
            readme = readme + platforms

        elif tokens[current_position][1] == T_NODES_DESCRIPTION:
            nodes_description = _get_nodes_description_text(template_metadata, cookbook_metadata, component_metadata)
            readme = readme + nodes_description

        elif tokens[current_position][1] == T_SOFTWARE_RESOURCES:
            software_resources = _get_software_resources_text(template_metadata, cookbook_metadata)
            readme = readme + software_resources

        elif tokens[current_position][1] == T_DISK:
            disk = _get_disk_text(template_metadata, cookbook_metadata)
            readme = readme + disk

        elif tokens[current_position][1] == T_PORTS:
            ports = _get_ports_text(template_metadata, cookbook_metadata)
            readme = readme + ports

        elif tokens[current_position][1] == T_LIBRARIES:
            libraries = _get_libraries_text(template_metadata, cookbook_metadata)
            readme = readme + libraries

        elif tokens[current_position][1] == T_REPO:
            repo = _get_repo_text(template_metadata, cookbook_metadata)
            readme = readme + repo

        elif tokens[current_position][1] == T_CLOUD_SPECIFIC:
            cloud_template_file = 'readme_templates' + os.sep + cloud_type + '-readme.md'
            if os.path.isfile(cloud_template_file):
                cloud_file = open(cloud_template_file, "r+")
                cloud_text = cloud_file.read()
                readme = readme + cloud_text

        current_position = current_position + 1

    return readme

    readme_template.close()

def create_catalog(template_metadata, component_metadata, cookbook_metadata, cloud_type, template_name):

    """

    create_catalogs will create a dictionary of camtemplate.json based on the template camtemplate.json.

    :param dict template_metadata: Dictionary of the template metadata.
    :param str component_metadata: Component metadata taken from the aggregated components.json.
    :param str cookbook_metadata: Cookbook metadata taken from the aggregated cookbook_metadata.json.
    :param str cloud_type: Name of the cloud the readme is targetted at.


    """

    token_regexs = [
        (r'#{NAME}',              T_NAME),
        (r'#{CLOUD_TYPE}',        T_CLOUD_TYPE),
        (r'#{VERSION}',           T_VERSION),
        (r'#{DESCRIPTION}',       T_DESCRIPTION),
        (r'#{SHORT_DESCRIPTION}', T_SHORT_DESCRIPTION),
        (r'#{LONG_DESCRIPTION}',  T_LONG_DESCRIPTION),
        (r'#{FEATURES}',          T_FEATURES),
        (r'#{SOFTWARE}',          T_SOFTWARE),
        (r'#{MAJOR_VERSIONS}',    T_MAJOR_VERSIONS),
        (r'#{MINOR_VERSIONS}',    T_MINOR_VERSIONS),
        (r'#{PLATFORMS}',         T_PLATFORMS),
        (r'#{NODES_DESCRIPTION}', T_NODES_DESCRIPTION),
        (r'#{SOFTWARE_RESOURCES}', T_SOFTWARE_RESOURCES),
        (r'#{DISK}',               T_DISK),
        (r'#{PORTS}',              T_PORTS),
        (r'#{LIBRARIES}',          T_LIBRARIES),
        (r'#{REPO}',               T_REPO),
        (r'#{CLOUD_SPECIFIC}',     T_CLOUD_SPECIFIC),
        (r'#{FILE}',               T_FILE),
        (r'#{PATH}',               T_PATH),
        (r'#{BULLETS}',            T_BULLETS),
        (r'.',                     T_CHAR),
        (r'[\n]',                  T_EOL),
        (r'[ \n\t]+',              None),
    ]

    catalog = ""
    # Open readme template file and assign full text
    catalog_template_file = 'readme_templates' + os.sep + 'template-catalog'
    catalog_files = {}
    catalog_template = open(catalog_template_file, "r+")
    catalog_text = catalog_template.read()

    #Tokenise readme template file
    tokens = _tokenise(catalog_text, token_regexs)

    #Cycle through each character and process the metadata
    current_position = 0
    while current_position < len(tokens):
        if tokens[current_position][1] == T_CHAR:
            catalog = catalog + tokens[current_position][0]

        elif tokens[current_position][1] == T_EOL:
            catalog = catalog + tokens[current_position][0]

        elif tokens[current_position][1] == T_CLOUD_TYPE:
            cloud_name = _get_cloud_text(cloud_type)
            catalog = catalog + cloud_name

        elif tokens[current_position][1] == T_VERSION:
            version = _get_version_text(template_metadata)
            catalog = catalog + version

        elif tokens[current_position][1] == T_NAME:
            name = _get_name_text(template_metadata)
            catalog = catalog + name

        elif tokens[current_position][1] == T_DESCRIPTION:
            description = _get_description_text(template_metadata)
            catalog = catalog + description

        elif tokens[current_position][1] == T_SHORT_DESCRIPTION:
            description = _get_short_description_text(template_metadata)
            catalog = catalog + description

        elif tokens[current_position][1] == T_LONG_DESCRIPTION:
            description = _get_long_description_text(template_metadata)
            catalog = catalog + description

        elif tokens[current_position][1] == T_PATH:
            #path = template_name + '_template/' + template_dir[cloud_type]
            path = template_dir[cloud_type]
            catalog = catalog + path

        elif tokens[current_position][1] == T_FILE:
            file = template_name + ".tf"
            catalog = catalog + file

        elif tokens[current_position][1] == T_BULLETS:
            bullets = _get_bullets_text(template_metadata, cloud_type)
            catalog = catalog + bullets

        current_position = current_position + 1

    return catalog

    readme_catalog.close()

def create_template_readmes(template_metadata, component_metadata, cookbook_metadata):

    """

    create_template_readme will create a dictionary of cloud readmes, one for each non-heat
    cloud.

    :param dict template_metadata: Dictionary of the template metadata.
    :param str component_metadata: Component metadata taken from the aggregated components.json.
    :param str cookbook_metadata: Cookbook metadata taken from the aggregated cookbook_metadata.json.


    """

    readmes = {}
    for cloud in template_types:
        readme = create_template_readme(template_metadata, component_metadata, cookbook_metadata, cloud)
        if readme:
            readmes[cloud] = readme

    return readmes


def create_catalogs(template_metadata, component_metadata, cookbook_metadata, template_name):

    """

    create_catalogs will create a dictionary of cloud camtemplate.json files.

    :param dict template_metadata: Dictionary of the template metadata.
    :param str component_metadata: Component metadata taken from the aggregated components.json.
    :param str cookbook_metadata: Cookbook metadata taken from the aggregated cookbook_metadata.json.


    """

    catalogs = {}
    for cloud in template_types:
        catalog = create_catalog(template_metadata, component_metadata, cookbook_metadata, cloud, template_name)
        if catalog:
            catalogs[cloud] = catalog

    return catalogs

def write_template_readmes(readmes, template_root):

    """

    write_template_readmes will the readme's for each cloud based on the existence of a template
    having been generated for that cloud.

    :param dict readmes: A dictionary of a readme for each cloud type.
    :param str template_root: The root directory of the template.


    """

    for cloud_type in template_dir:
        if os.path.exists(template_root + os.sep + template_dir[cloud_type]) and cloud_type != 'heat':
            print 'Writing  ' + template_root + os.sep + template_dir[cloud_type] + os.sep + 'readme.md'
            with open(template_root + os.sep + template_dir[cloud_type] + os.sep + 'readme.md', 'w+') as readme_file:
                readme_file.write(readmes[cloud_type])

def write_catalogs(catalogs, template_root):

    """

    write_catalogs will write readmes for each cloud if that cloud template exists.

    :param dict catalogs: A dictionary of a catalogs for each cloud type.
    :param str template_root: The root directory of the template.


    """

    for cloud_type in template_dir:
        if os.path.exists(template_root + os.sep + template_dir[cloud_type]) and cloud_type != 'heat':
            print 'Writing  ' + template_root + os.sep + template_dir[cloud_type] + os.sep + 'camtemplate.json'
            with open(template_root + os.sep + template_dir[cloud_type] + os.sep + 'camtemplate.json', 'w+') as catalog_file:
                catalog_file.write(catalogs[cloud_type])
