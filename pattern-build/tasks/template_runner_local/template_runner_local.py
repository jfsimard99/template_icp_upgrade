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

import lib.local.env as env
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
    if tf_variable_files:
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
        epilog='')
    parser.add_argument(
        '-t', '--tf_template_file',
        type=argparse.FileType('r'), required=True,
        help='Terraform template file')
    parser.add_argument(
        '-v', '--tf_variable_files',
        type=argparse.FileType('r'), required=False, nargs='+',  # one or more
        help='Terraform variable file(s), can specify multiple.  Later files '
             'have precedence.')
    parser.add_argument(
        '-cv', '--cam_variable_file',
        type=argparse.FileType('r'),
        help='A "camvariable.json" file.')
    parser.add_argument(
        '-n', '--stack_name', type=str, required=True,
        help='CAM stackname for the deployment')
    parser.add_argument(
        '-u', '--w3_username', type=str, default='apikey',
        help='W3 username, default: Set W3_USERNAME as ENV override.')
    parser.add_argument(
        '-c', '--cam_url', type=str, required=True,
        help='CAM Local URL IP Address')
    parser.add_argument(
        '-p', '--cam_port', type=str, default='30000',
        help='CAM Local Port Number')
    parser.add_argument(
        '-b', '--git_branch', type=str, required=True,
        help='Template branch in GitHub')
    parser.add_argument(
        '-o', '--override_file', type=str, required=False,
        help='CAM Variables Override File')
    parser.add_argument(
        '-tf', '--translation_file', type=str, required=False,
        help='Location of the translation file')
    parser.add_argument(
        '-uc', '--use_case', type=str, required=False, default='default',
        help='Use case in the translation file to use as source data' )

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
    # os.environ['W3_USERNAME'] = os.getenv(
    #     'W3_USERNAME', args.w3_username)
    # if not os.getenv('W3_PASSWORD', None):
    #     sys.exit('Error: W3_PASSWORD environment variable must be '
    #              'set (see help)')
    if not os.getenv('GIT_TOKEN', None):
        sys.exit('Error: GIT_TOKEN environment variable must be '
                 'set (see help)')

    # Ticket 1855 - Add a translation and override file environment
    if args.override_file:
        env_or_cli('OVERRIDE_FILE', args.override_file)
    if args.translation_file:
        env_or_cli('TRANSLATION_FILE', args.translation_file)

    env_or_cli('ENV', 'local')
    env_or_cli('VM_URL', args.cam_url)
    env_or_cli('CAM_PORT', args.cam_port)
    set_connection_env('AWS_CLOUD_CONNECTION', args.aws_cloud_connection)
    set_connection_env('IBMCLOUD_CLOUD_CONNECTION',
                       args.ibmcloud_cloud_connection)
    set_connection_env('VSPHERE_CLOUD_CONNECTION', args.vmware_cloud_connection)
    env.set_env(args.cam_url, args.cam_port, "local")  # set environment
    [template_str, variables_dict, camvariables_dict] = get_local_template(
        args.tf_template_file, args.tf_variable_files, args.cam_variable_file)
    template_path = args.tf_template_file.name

    LOGGER.info('Deploying: %s' %args.stack_name)

    result = worker.life_cycle_stack("local",
       args.stack_name, args.git_branch, template_path, template_str, variables_dict, camvariables_dict,
       args.delete_failed_deployments, delete=args.autodestroy, use_case=args.use_case)

    if 'deploy_error' in result:
        raise result['deploy_error']
    if 'destroy_error' in result:
        raise result['destroy_error']
    return result

if __name__ == "__main__":
    main()
