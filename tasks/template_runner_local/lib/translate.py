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
import re
import random
import string
import requests
import ast

from platform import system as system_name # Returns the system/OS name
from os import system as system_call       # Execute a shell command
from lib.logger import TestLogger

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

def _ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that some hosts may not respond to a ping request even if the host name is valid.
    """

    # Ping parameters as function of OS
    parameters = "-n 1 -w 2" if system_name().lower()=="windows" else "-c 1"

    # Pinging
    return system_call("ping " + parameters + " " + host) == 0

def print_dictionary(in_dict, spaces=0):

    '''
    Formatted print of a print_dictionary
    '''

    print_dict = dict(in_dict)

    spaces = spaces + 2

    for key in print_dict.keys():
        if isinstance(print_dict[key], dict):
            print(spaces*' ' + key + ':')
            print_dictionary(print_dict[key], spaces)
        else:
            item = str(print_dict[key])
            print(spaces*' ' + key + ' : ' + item)

def _get_node_list(cam_variables, variables):

    '''
    Return a dictionary of the variables related to IP Address Management.
    This is needed because IP Address variables are to be built on a per-node basis.
    For this method to work properly, the ip_hostname type must only be assigned to
    a single variable per node.
    '''

    node_list = list()
    ip_dict = {}

    if 'node' in variables:
        node_variables = variables['node']

    # Build field name list from cam variables
    cam_fields = list()
    for cam_variable in cam_variables:
        cam_fields.append(cam_variable['name'])

    #parse for unqiue nodes

    for cam_variable in cam_variables:
        for variable in node_variables:
            found = False
            if node_variables[variable]['type'] == "ip_hostname":
                regex = variable + '$'
                if re.search(regex, cam_variable['name']):
                    regex = variable + '$'
                    node_name = re.sub(regex, '', cam_variable['name'])
                    for field in variables['ip_fields']:
                        resolved_field = node_name[:-1] + field
                        if resolved_field in cam_fields:
                            found = True
                    if found:
                        if node_name[:-1] not in node_list:
                            node_list.append(node_name[:-1])
    return node_list

def _is_override(variable, override_variables):

    '''
    Return true if the variable name is an over-ride variable.
    If true, return the override value as a second parameter
    '''

    if variable in override_variables:
        return (True, override_variables[variable])
    else:
        return (False, 0)

def _is_lookup(variable, variables):

    '''
    Return true if the variable name is a lookup variable.
    Return the generic variable name, for example, MQV9Node01-flavor will
    return flavor.
    '''

    if 'node' in variables:
        node_variables = variables['node']

    if 'global' in variables:
        global_variables = variables['global']

    # If a variable is a NODE variable then return the resolved variable name
    for current_variable in node_variables:
        if node_variables[current_variable]['type'] == 'lookup':
            regex = current_variable + '$'
            if re.search(regex, variable):
                return (True, current_variable)

    # If a variable is a GLOBAL variable then return the resolved variable name
    for current_variable in global_variables:
        if global_variables[current_variable]['type'] == 'lookup':
            regex = current_variable + '$'
            if re.search(regex, variable):
                return (True, current_variable)

    return (False, 0)

def _get_ip_pool(ip_pool_provider, ip_pool, used_ip, node, minipam_url):

    '''
    Interrogate the IP Pool for a free entry and return the ip, domain, hostname
    '''

    if ip_pool_provider == "local":
        for ip_entry in ip_pool:
            if ip_entry['ip_ipaddress'] not in used_ip:
                if not _ping(ip_entry['ip_ipaddress']):
                    return (ip_entry['ip_ipaddress'], ip_entry['ip_domain'], ip_entry['ip_hostname'])
        raise Exception("IP Pool Exhausted")
    elif ip_pool_provider == "minipam":
        response = requests.get(minipam_url + "/get")
        if response.status_code == 200:
            ip_entry = ast.literal_eval(response.content)
            return (ip_entry['ipaddress'], ip_entry['domain'], ip_entry['hostname'])
        elif response.status_code == 400:
            raise Exception("IP Pool Exhausted")
        else:
            return None
    else:
        raise Exception("Not valid IP Provider for %s" % ip_pool_provider)

def _is_random(variable, variables):

    '''
    Type Random variables need to be generated
    '''

    if 'node' in variables:
        node_variables = variables['node']

    if 'global' in variables:
        global_variables = variables['global']

    timestamp = datetime.now()
    value = 'camcontent-%s' % datetime.strftime(timestamp, '%H%M%S%f')

    if variable in node_variables:
        if node_variables[variable]['type'] == "random":
            return (True, value)
    elif variable in global_variables:
        if global_variables[variable]['type'] == "random":
            return (True, value)
    return (False, 0)

def _gen_hostname():

    '''
    Generate a random hostname
    '''


    timestamp = datetime.now()
    value = 'camcontent-%s' % datetime.strftime(timestamp, '%H%M%S%f')

    return value

def _is_reserved(variable, variables):

    '''
    Return true if the variable is generated by the environment and can therefore be ignored
    '''

    reserved_types = ['connection', 'content_runtime']

    if 'node' in variables:
        node_variables = variables['node']

    if 'global' in variables:
        global_variables = variables['global']

    if variable in node_variables:
        if node_variables[variable]['type'] in reserved_types:
            return True
    elif variable in global_variables:
        if global_variables[variable]['type'] in reserved_types:
            return True
    return False

def _is_public_key(variable, variables):

    '''
    Return ssh key if the variable is a public ssh key that needs to be generated
    '''

    ssh_keys = ['public_ssh_key']

    if variable in ssh_keys:
        from Crypto.PublicKey import RSA
        return RSA.generate(2048).publickey().exportKey('OpenSSH')
    else:
        return None

#Ticket 1891, added the resolution of use case variables.
def _resolve_usecase_variables(variables, use_case="default"):

    '''
    Resolve the variable specific to the use case specified, value of default means that no
    test case variable will be chosen, instead, the default list will be returned.

    A dictionary or resovled variables will be returned of None if the use case does no exist.

    The general structure will be as follows:

    CLOUD_TYPE:
        variable1: "somevalue"
        variable2: "somevalue"
        variable3: "somevalue"
        ....
        use_cases:
            use_case1:
                variable1: "someNEWvalue"
                variable2: "someNEWvalue"
            use_case2:
                variable1: "someNEWvalue"
                variable2: "someNEWvalue"

    Only variables defined in the default case can be over-ridden by specific use case
    variables.
    '''

    if use_case == "default":
        return variables
    elif "use_cases" in variables:
        if not use_case in variables['use_cases']:
            return None

    # If we make it this far we can assert that variables['use_cases'][use_case] exists
    # Cycle through each variable and over-ride if a use case variable exists
    temp_variables = {}
    for variable in variables:
        if variable in variables['use_cases'][use_case]:
            temp_variables[variable] = variables['use_cases'][use_case][variable]
        else:
            temp_variables[variable] = variables[variable]

    return temp_variables


def resolve_parameters(override_variables, variables, camVariables, image_type="vmware", use_case="default"):

    '''
    Return the translated list of CAM Variables parsed from the variables structure.
    '''

    variable_map = {}

    # Instanciate IP Pool Variables

    used_ip = list()
    ip_pool = {}
    ip_overrides = {}
    ip_pool_provider = variables['test_data']['provider']
    minipam_url = ""
    ip_list = list()

    if ip_pool_provider == "local":
        ip_pool = variables['ip_pool']

    if ip_pool_provider == "minipam":
        minipam_url = variables['test_data']['minipam_url']

    node_list = _get_node_list(camVariables['template_input_params'], variables)

    for node in node_list:
        if image_type == "vmware" or image_type == "vsphere":
            ip, domain, hostname = _get_ip_pool(ip_pool_provider, ip_pool, used_ip, node, minipam_url)
            used_ip.append(ip)
        else:
            ip = "dummy"
            domain = "dummy"
            hostname = _gen_hostname()
        ip_list.append(ip)
        ip_overrides[node + '_ipv4_address'] = ip
        ip_overrides[node + '_domain'] = domain
        ip_overrides[node + '-name'] = hostname

    # Match images based on image_type

    if 'virtual_machines' in variables:
        virtual_machines = variables['virtual_machines']

        if image_type in virtual_machines:
            vm_variables = virtual_machines[image_type]
            vm_variables = _resolve_usecase_variables(vm_variables, use_case)
            if not vm_variables:
                raise Exception("The specified Use Case %s does not exist." % use_case)
        else:
            raise Exception("The Image %s has no definition in the variables file." % image_type)

    # Inspect all variables in CAMVariables and resolve.

    logger = TestLogger(__name__)

    index = 0
    for variable in camVariables['template_input_params']:

        # PRIORITY 1 - OverRide Values
        override, value = _is_override(variable['name'], override_variables)
        if override:
            variable['default'] = value
            camVariables['template_input_params'][index] = variable
            logger.info('Translation Override - %s : %s' % (variable['name'], value))
            index = index + 1
            continue

        # PRIORITY 2 - Lookup Variables
        lookup, value = _is_lookup(variable['name'], variables)
        if lookup:
            if value in vm_variables:
                # Ticket 1915 - randomize IBM Data Center
                if value == "datacenter" and vm_variables[value] == "":
                    variable['default'] = random.choice(['dal05','dal06','dal09','dal10','hou02','mon01','sea01','tor01','wdc01','wdc04'])
                else:
                    variable['default'] = vm_variables[value]
                camVariables['template_input_params'][index] = variable
                logger.info('Translation Lookup - %s : %s' % (variable['name'], variable['default']))
                index = index + 1
                continue
            else:
                raise Exception("The required variable %s has no valid lookup value" % variable['name'])

        # PRIORITY 3 - Randoms
        israndom, value = _is_random(variable['name'], variables)
        if israndom:
            variable['default'] = value
            camVariables['template_input_params'][index] = variable
            logger.info('Translation Random - %s : %s' % (variable['name'], value))
            index = index + 1
            continue

        # PRIORITY 4 - IP Addresses
        override, value = _is_override(variable['name'], ip_overrides)
        if override:
            variable['default'] = value
            camVariables['template_input_params'][index] = variable
            logger.info('Translation IP Address - %s : %s' % (variable['name'], value))
            index = index + 1
            continue

        # PRIORITY 5 - Ignore entries with existing default values
        if 'default' in variable or 'value' in variable:
            logger.info('Translation Ignore - %s' % variable['name'])
            index = index + 1
            continue

        # PRIORITY 6 - Dummy entries with system reserved types
        if _is_reserved(variable['name'], variables):
            if 'default' not in variable:
                variable['default'] = 'dummy'
                camVariables['template_input_params'][index] = variable

            logger.info('Translation Reserved - %s' % variable['name'])
            index = index + 1
            continue

        # PRIORITY 7 - public ssh keys for IBM Cloud
        ssh_key = _is_public_key(variable['name'], variables)
        if ssh_key:
            variable['default'] = ssh_key

            logger.info('Translation public SSH key - %s' % variable['name'])
            index = index + 1
            continue

        # FALLTHOUGH - No default nothing set, randomise a value as its probably a password
        variable['default'] = _generate_password()
        camVariables['template_input_params'][index] = variable
        logger.info('Translation Password Generate - %s : %s' % (variable['name'], variable['default']))
        index = index + 1

    return (camVariables, ip_list)
