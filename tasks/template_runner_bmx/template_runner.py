#! /usr/bin/env python
# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================
"""Template_Runner CLI -- see 'template_runner -h' for usage"""
import json
import os
import sys

import argparse
import hcl

import lib.env as env
from lib.logger import TestLogger
import lib.worker as worker


LOGGER = TestLogger(__name__)


def get_local_template(tf_template_file, tf_variable_files, cam_variable_file):
    '''
    Retrieves the TF template and variable file(s) as python dictionaries
    '''
    # parse the files -- hcl.load() dually supports both JSON and HCL formats
    # If HCL contains heredoc notation, and file has CRLF encodings, it will
    # fail. See: https://github.com/virtuald/pyhcl/issues/25
    template_str = tf_template_file.read()  # load the entire file into String
    hcl.loads(template_str)  # test parse / raise error on parse failure

    # read the variable file(s), updating/overwriting variables_dict as we go
    variables_dict = {}
    for variable_file in tf_variable_files:
        variables_dict.update(hcl.load(variable_file)['variable'])

    camvariables_dict = {}
    if cam_variable_file:
        camvariables_dict = json.load(cam_variable_file)

    return [template_str, {'variable': variables_dict}, camvariables_dict]


def env_or_cli(env_key, cli_arg):
    '''
    Sets ENV env_key to value of cli_arg if env_key is not already set in the
    environment.  Exits with error if neither are set.
    '''
    if not os.getenv(env_key, cli_arg):
        sys.exit('Error: Must provide %s as either ENV variable or '
                 'CLI argument.' % env_key)
    else:
        os.environ[env_key] = os.getenv(env_key, cli_arg)


def set_connection_env(env_key, cli_arg):
    '''Sets the ENV variable env_key, to value cli_arg is not None'''
    if cli_arg:
        os.environ[env_key] = os.getenv(env_key, cli_arg)


def main():
    '''
    Runs a TF template with CAM
    '''
    parser = argparse.ArgumentParser(
        description='Runs a terraform template against CAMaaS.',
        epilog='Note: environment variable BLUEMIX_PASSWORD must contain '
               'your BMx password or API-Key.  When using API-Keys, '
               '--bluemix_username must be "apikey"')
    parser.add_argument(
        '-t', '--tf_template_file',
        type=argparse.FileType('r'), required=True,
        help='Terraform template file')
    parser.add_argument(
        '-v', '--tf_variable_files',
        type=argparse.FileType('r'), required=True, nargs='+',  # one or more
        help='Terraform variable file(s), can specify multiple.  Later files '
             'have precedence.')
    parser.add_argument(
        '-cv', '--cam_variable_file',
        type=argparse.FileType('r'),
        help='A "camvariable.json" file.')
    parser.add_argument(
        '-e', '--cam_environment',
        choices=['dev', 'qa', 'pen', 'prod'], required=True, default='dev',
        help='The Cloud Automation Manager (CAM) environment to target')
    parser.add_argument(
        '-n', '--stack_name', type=str, required=True,
        help='CAM stackname for the deployment')
    parser.add_argument(
        '-u', '--bluemix_username', type=str, default='apikey',
        help='BlueMix username, default: "apikey" for use with BMx API-Keys '
             'instead of passwords. Set BLUEMIX_USERNAME as ENV override.')
    parser.add_argument(
        '-o', '--bluemix_org_name', type=str,
        help='BlueMix organization name.  Can set BLUEMIX_ORG_NAME '
             'as ENV override.')
    parser.add_argument(
        '-s', '--bluemix_space_name', type=str,
        help='BlueMix space name.  Can set BLUEMIX_SPACE_NAME '
             'as ENV override.')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-aws', '--aws_cloud_connection', type=str,
        help='Cloud connection name for AWS')
    group.add_argument(
        '-ibmcloud', '--ibmcloud_cloud_connection', type=str,
        help='Cloud connection name for IBM-Cloud (Softlayer)')
    group.add_argument(
        '-vmware', '--vmware_cloud_connection', type=str,
        help='Cloud connection name for VMWare (VMWare)')
    parser.add_argument(
        '--delete_failed_deployments', default=False, action='store_true',
        help="Delete failed deployments (default: False)")
    parser.add_argument(
        '--autodestroy', default=False, action='store_true',
        help="Automatically destroy after deploying (default: False)")
    args = parser.parse_args()

    # setup the environment variables needed for worker & iaas
    os.environ['BLUEMIX_USERNAME'] = os.getenv(
        'BLUEMIX_USERNAME', args.bluemix_username)
    if not os.getenv('BLUEMIX_PASSWORD', None):
        sys.exit('Error: BLUEMIX_PASSWORD environment variable must be '
                 'set (see help)')

    env_or_cli('BLUEMIX_ORG_NAME', args.bluemix_org_name)
    env_or_cli('BLUEMIX_SPACE_NAME', args.bluemix_space_name)
    set_connection_env('AWS_CLOUD_CONNECTION', args.aws_cloud_connection)
    set_connection_env('IBMCLOUD_CLOUD_CONNECTION',
                       args.ibmcloud_cloud_connection)
    set_connection_env('VMWARE_CLOUD_CONNECTION', args.vmware_cloud_connection)
    env.set_env(args.cam_environment)  # set environment
    [template_str, variables_dict, camvariables_dict] = get_local_template(
        args.tf_template_file, args.tf_variable_files, args.cam_variable_file)

    LOGGER.info('Deploying: %s' %args.stack_name)
    result = worker.life_cycle_stack(
        args.stack_name, template_str, variables_dict, camvariables_dict,
        args.delete_failed_deployments, delete=args.autodestroy)
    if 'deploy_error' in result:
        raise result['deploy_error']
    if 'destroy_error' in result:
        raise result['destroy_error']
    return result

if __name__ == "__main__":
    main()
