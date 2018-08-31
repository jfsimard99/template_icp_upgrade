## =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# ===============================================================

import sys
import os

import tempfile
import repotools
import chef_repo
import json
import shutil

from chef_repo import ChefRepo
from optparse import OptionParser
from chef_repo import RepositoryMetadata
from git_helper import LocalGitClone
from git_helper import get_repos
from git_helper import clone_repos
from metadatatools import write_components_json

# Process command line parameters

parser = OptionParser()
parser.add_option("-b", "--branch", dest="git_branch", default='landscaper-predev-pat-01',
                  help="Enter a branch to clone")

parser.add_option("-g", "--giturl", dest="git_url", default='github.ibm.com',
                  help="Enter a GIT URL")

parser.add_option("-k", "--keyfile", dest="keyfile", default='$HOME/gittoken',
                  help="Enter GIT Token Keyfile")

parser.add_option("-d", "--dir", dest="temp_dir", default='/tmp/git',
                  help="Enter location of the temp dir")

parser.add_option("-c", "--cookbook_root", dest="cookbook_root", default='.',
                  help="Enter the location of the cookbook root")

(options, args) = parser.parse_args()

#Set options

project = 'infra-temp-metadata-files'
components_file = 'temp_software_components.json'
attributes_file = 'temp_attributes.json'

#Key Access Key
key_file = open(options.keyfile)
auth_key = key_file.readline().strip()

#Check base dir for repo

rc,data = repotools.get_repo_root('chef', options.cookbook_root)

if rc != 0:
    print('ERROR:' + data)
    exit(rc)
else:
    repo_root = data

# Download all cookbooks from a GIT repo on a specific BRANCH
if not options.temp_dir:
    repo_base_dir = tempfile.mkdtemp()
else:
    repo_base_dir = options.temp_dir

print('-----------------------------------------------------------------------')
print('GIT URL     - ' + options.git_url)
print('REPO        - ' + project)
print('BRANCH      - ' + options.git_branch)
print('TEMP DIR    - ' + repo_base_dir)
print('GIT KEY     - ' + options.keyfile)
print('LOCAL ROOT  - ' + repo_root)
print('-----------------------------------------------------------------------')

# Remove temporary repo if already exists
if os.path.exists(repo_base_dir + '/' + project):
    shutil.rmtree(repo_base_dir + '/' + project)

repos = get_repos(options.git_url, 'OpenContent', project, auth_key)
x = clone_repos(repos, auth_key, repo_base_dir, options.git_branch)

# Read temp metadata files

temp_components_file = open(repo_base_dir + '/' + project  + '/temp_software_components.json', "r+")
temp_attributes_file = open(repo_base_dir + '/' + project  + '/temp_attributes.json', "r+")

temp_components = json.load(temp_components_file)
temp_attributes_in = json.load(temp_attributes_file)

temp_role_dictionary = temp_components['components']

temp_components_file.close()
temp_attributes_file.close()

temp_components_file = open(repo_base_dir + '/' + project + '/temp_software_components.json', "w+")
temp_attributes_file = open(repo_base_dir + '/' + project + '/temp_attributes.json', "w+")

# Cycle through each cookbook updating new components and attribute metadata

if os.path.isdir(repo_root):
    chef_repo = ChefRepo(repo_root)

    new_temp_role_dictionary = []
    for cookbook in chef_repo.cookbooks:

        # Process Roles
        cookbook_roles = cookbook.metadata_roles.keys()
        for temp_role in temp_role_dictionary:
            if not temp_role['name'] in cookbook_roles:
                new_temp_role_dictionary.append(temp_role)
        write_components_json(cookbook.metadata_roles, cookbook.dynamic_attributes, temp_components_file, new_temp_role_dictionary)

        # Process Attributes
        cookbook_name =  cookbook.cookbook_root.split('/')[-1]
        temp_attributes = {}
        for attribute in temp_attributes_in.keys():
            if not attribute == cookbook_name:
                temp_attributes[attribute] = temp_attributes_in[attribute]
        temp_attributes[cookbook_name] = cookbook.metadata_attributes[cookbook_name]
        json.dump(temp_attributes, temp_attributes_file, sort_keys=True, indent=4, separators=(',', ': '))

else:
    print "ERROR: Output path does not exist: " + out_dir
    sys.exit(1)

print '-----------------------------------------------------------------------'
print 'Updated - ' + repo_base_dir + '/' + project + '/temp_software_components.json'
print 'Updated - ' + repo_base_dir + '/' + project + '/temp_attributes.json'

temp_components_file.close()
temp_attributes_file.close()
sys.exit(0)