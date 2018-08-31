#! /usr/bin/env python
# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import os
import sys
import json
import zipfile
import argparse
import requests
import shutil
import gnupg
import gnupg._parsers
gnupg._parsers.Verify.TRUST_LEVELS["DECRYPTION_COMPLIANCE_MODE"] = 23


import lib.local.env as env
from lib.logger import TestLogger
import lib.worker as worker

LOGGER = TestLogger(__name__)

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


def download_file(url, user, password):
    local_filename = url.split('/')[-1]
    r = requests.get(url, stream=True, auth=(user, password))
    with open(local_filename, 'wb') as f:
        shutil.copyfileobj(r.raw, f)

    return local_filename

def main():
    '''
    Runs a TF template with CAM
    '''
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
        '-f', '--connection_file_url', type=str, default='https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/environment_setup/cloud_connections.zip.gpg',
        help='Encrypted Cloud Connection File')          # https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/labs/environs.yml.gpg

    args = parser.parse_args()


    if not os.getenv('ARCHIVE_PASSWORD', None):
        sys.exit('Error: ARCHIVE_PASSWORD environment variable must be '
                 'set (see help)')
    if not os.getenv('DOCKER_REGISTRY_USER', None):
        sys.exit('Error: DOCKER_REGISTRY_USER environment variable must be '
                 'set (see help)')
    if not os.getenv('DOCKER_REGISTRY_PASS', None):
        sys.exit('Error: DOCKER_REGISTRY_PASS environment variable must be '
                 'set (see help)')

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
    with open('cloud_connections.zip.gpg', 'rb') as f:
        status = gpg.decrypt_file(f, passphrase=archive_password, output='./cloud_connections.zip')

    zip = zipfile.ZipFile('cloud_connections.zip')
    zip.extractall()


    with open("cloudconnection_vmware_rack36.json") as json_file:
        data = json.load(json_file)
        #print(data)
    LOGGER.info('Creating Cloud Connection for VMware vSphere - Rack36')
    worker.create_cc('VMware vSphere', data)
    
    with open("cloudconnection_vmware.json") as json_file:
        data = json.load(json_file)
        #print(data)
    LOGGER.info('Creating Cloud Connection for VMware vSphere - Rochester')
    worker.create_cc('VMware vSphere', data)

    with open("cloudconnection.vmware.json") as json_file:
        data = json.load(json_file)
        #print(data)
    LOGGER.info('Creating Cloud Connection for VMware vSphere - Rochester')
    worker.create_cc('VMware vSphere', data)

    with open("cloudconnection_vmware_ftpfit3.json") as json_file:
        data = json.load(json_file)
        #print(data)
    LOGGER.info('Creating Cloud Connection for VMware vSphere - Fit3')
    worker.create_cc('VMware vSphere', data)

    with open("cloudconnection.vmware.rtpcam.json") as json_file:
        data = json.load(json_file)
        #print(data)
    LOGGER.info('Creating Cloud Connection for VMware vSphere - CAM RTP VCenter')
    worker.create_cc('VMware vSphere', data)

    with open("cloudconnection_vmware_rtpcam.json") as json_file:
        data = json.load(json_file)
        #print(data)
    LOGGER.info('Creating Cloud Connection for VMware vSphere - CAM RTP VCenter')
    worker.create_cc('VMware vSphere', data)

    with open("cloudconnection_ibmcloud.json") as json_file:
        data = json.load(json_file)
        # print(data)
    LOGGER.info('Creating Cloud Connection for IBM')
    worker.create_cc('IBM', data)

    with open("cloudconnection.ibmcloud.json") as json_file:
        data = json.load(json_file)
        # print(data)
    LOGGER.info('Creating Cloud Connection for IBM')
    worker.create_cc('IBM', data)

    with open("cloudconnection_aws.json") as json_file:
        data = json.load(json_file)
        # print(data)
    LOGGER.info('Creating Cloud Connection for Amazon EC2')
    worker.create_cc('Amazon EC2', data)

    with open("cloudconnection.aws.json") as json_file:
        data = json.load(json_file)
        # print(data)
    LOGGER.info('Creating Cloud Connection for Amazon EC2')
    worker.create_cc('Amazon EC2', data)

    with open("cloudconnection_openstack.json") as json_file:
        data = json.load(json_file)
        # print(data)
    LOGGER.info('Creating Cloud Connection for OpenStack')
    worker.create_cc('OpenStack', data)

if __name__ == "__main__":
    main()
