#! /usr/bin/env python
# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import argparse
import hcl
import json
import os
import requests
import shutil
import sys
import zipfile

import lib.local.env as env
from lib.logger import TestLogger
import lib.worker as worker
import gnupg
import gnupg._parsers
gnupg._parsers.Verify.TRUST_LEVELS["DECRYPTION_COMPLIANCE_MODE"] = 23

LOGGER = TestLogger(__name__)


def env_or_cli(env_key, cli_arg):
    """
    Sets ENV env_key to value of cli_arg if env_key is not already set in the
    environment.  Exits with error if neither are set.
    """
    if not os.getenv(env_key, cli_arg):
        sys.exit('Error: Must provide %s as either ENV variable or '
                 'CLI argument.' % env_key)
    else:
        os.environ[env_key] = os.getenv(env_key, cli_arg)


def set_connection_env(env_key, cli_arg):
    """Sets the ENV variable env_key, to value cli_arg is not None"""
    if cli_arg:
        os.environ[env_key] = os.getenv(env_key, cli_arg)


def get_local_template(tf_template_file, tf_variable_files):
    """Retrieves the TF template and variable file(s) as python dictionaries"""
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

    return [template_str, {'variable': variables_dict}]


def download_file(url, user, password):
    """Download file from the specified url"""
    print "In download file. Url: %s" % url

    local_filename = url.split('/')[-1]
    r = requests.get(url, stream=True, auth=(user, password))

    print "Download results: %s" % r

    with open(local_filename, 'wb') as f:
        shutil.copyfileobj(r.raw, f)

    return local_filename


def merge_secrets(cam_variable_file, provider, cam_url):
    """Merges CAM Variables with the secrets downloaded from artifactory"""
    cam_variables_dict = json.load(cam_variable_file)
    with open("contentruntime_%s.json" % provider, 'r') as json_file:
        data = json.load(json_file)

    for cam_variable in cam_variables_dict['template_input_params']:
        if cam_variable['name'] in data:
            cam_variable['default'] = data[cam_variable['name']]
        # If using the default hostname, update ir to include the last digits of the CAM IP address
        # so that we can deploy to multiple CAM instances without hitting naming issues
        if cam_variable['name'] == 'runtime_hostname' and cam_variable['default'] == "camc-%s-octravis" % provider:
            last_digit = cam_url.split('.')[-1]
            print "Setting runtime_hostname to camc-%s-octravis-%s" % (provider, last_digit)
            cam_variable['value'] = "camc-%s-octravis-%s" % (provider, last_digit)

    return cam_variables_dict


def main():
    """Runs a TF template with CAM"""
    parser = argparse.ArgumentParser(
        description='Runs a terraform template against CAMaaS.',
        epilog='')
    parser.add_argument(
        '-c', '--cam_url', type=str, required=True,
        help='CAM Local URL IP Address')
    parser.add_argument(
        '-p', '--cam_port', type=str, default='30000',
        help='CAM Local Port Number')
    parser.add_argument(
        '-f', '--connection_file_url', type=str, default='https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/environment_setup/content_runtimes.zip.gpg',
        help='Encrypted Content Runtime Secrets File')
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
        '-o', '--override_file', type=str, required=False,
        help='CAM Variables Override File')
    parser.add_argument(
        '-tf', '--translation_file', type=str, required=False,
        help='Location of the translation file')
    parser.add_argument(
        '-pr', '--provider', type=str, required=True,
        help='Cloud provider: AWS, IBM, VMWare, or Bring your own')
    parser.add_argument(
        '-b', '--git_branch', type=str, required=True,
        help='Template branch in GitHub')
    parser.add_argument(
        '-e', '--use_existing', default=False, action='store_true',
        help='Do not import new templates. Use the existing ones.')

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
        '--autodestroy', default=False, action='store_true',
        help="Automatically destroy after deploying (default: False)")
    parser.add_argument(
        '--delete_failed_deployments', default=False, action='store_true',
        help="Delete failed deployments (default: False)")

    args = parser.parse_args()

    if not os.getenv('GIT_TOKEN', None):
        sys.exit('Error: GIT_TOKEN environment variable must be '
                 'set (see help)')
    if not os.getenv('ARCHIVE_PASSWORD', None):
        sys.exit('Error: ARCHIVE_PASSWORD environment variable must be '
                 'set (see help)')
    if not os.getenv('DOCKER_REGISTRY_USER', None):
        sys.exit('Error: DOCKER_REGISTRY_USER environment variable must be '
                 'set (see help)')
    if not os.getenv('DOCKER_REGISTRY_PASS', None):
        sys.exit('Error: DOCKER_REGISTRY_PASS environment variable must be '
                 'set (see help)')

    provider_map = {'aws': 'amazon',
                    'ibm': 'ibm',
                    'vmware': 'vmware',
                    'Bring your own': 'other'}
    if args.provider not in provider_map:
        sys.exit('Error: provider specified not supported. Provider must be set to '
                 'one of: AWS, IBM, VMWare, or Bring your own')

    if args.override_file:
        env_or_cli('OVERRIDE_FILE', args.override_file)
    if args.translation_file:
        env_or_cli('TRANSLATION_FILE', args.translation_file)

    set_connection_env('AWS_CLOUD_CONNECTION', args.aws_cloud_connection)
    set_connection_env('IBMCLOUD_CLOUD_CONNECTION',
                       args.ibmcloud_cloud_connection)
    set_connection_env('VSPHERE_CLOUD_CONNECTION', args.vmware_cloud_connection)

    env_or_cli('ENV', 'local')
    env_or_cli('VM_URL', args.cam_url)
    env_or_cli('CAM_PORT', args.cam_port)
    env.set_env(args.cam_url, args.cam_port, "local")  # set environment

    artifactory_file = args.connection_file_url
    user = os.getenv('DOCKER_REGISTRY_USER')
    password = os.getenv('DOCKER_REGISTRY_PASS')
    archive_password = os.getenv('ARCHIVE_PASSWORD')
    download_file(artifactory_file, user, password)
    gpg = gnupg.GPG()
    with open('content_runtimes.zip.gpg', 'rb') as f:
        gpg.decrypt_file(f, passphrase=archive_password, output='./content_runtimes.zip')

    zip = zipfile.ZipFile('content_runtimes.zip')
    zip.extractall()

    provider = args.provider
    path_name = provider_map[provider]

    # If true, find an existing cam runtime template, otherwise grab the latest from github
    if (args.use_existing):
        templates = worker.get_cr_templates(provider)
        if templates:
            template_id = templates[0]['id']
            print 'Using existing for provider %s: %s' % (path_name, template_id)
        else:
            sys.exit('No templates found for provider %s' % path_name)
    else:
        print "Creating new templates for %s" % provider
        worker.delete_cr_templates(provider)
        template_id = worker.import_cr_template("github",
                                                "https://github.ibm.com/OpenContent/advanced_content_runtime_chef",
                                                "content_runtime_template/%s/public" % path_name,
                                                args.git_branch,
                                                os.getenv('GIT_TOKEN'),
                                                "ContentRuntime")

    # Merge the secrets into the cam variables
    cam_variables_merged = merge_secrets(args.cam_variable_file, provider, args.cam_url)
    [template_str, variables_dict] = get_local_template(args.tf_template_file, args.tf_variable_files)

    # Deploy the content runtime using worker.life_cycle_stack
    result = worker.life_cycle_stack(
        "local", args.stack_name, None, None, template_str, variables_dict, cam_variables_merged,
        args.delete_failed_deployments, delete=args.autodestroy, template_id=template_id)

    if 'deploy_error' in result:
        raise result['deploy_error']
    if 'destroy_error' in result:
        raise result['destroy_error']

    return result


if __name__ == "__main__":
    main()
