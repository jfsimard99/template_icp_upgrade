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

from optparse import OptionParser
from chef_repo import RepositoryMetadata
from git_helper import LocalGitClone
from git_helper import get_repos
from git_helper import clone_repos

# Process command line parameters

parser = OptionParser()
parser.add_option("-b", "--branch", dest="git_branch", default='development',
                  help="Enter a branch to clone")

parser.add_option("-g", "--giturl", dest="git_url", default='github.ibm.com',
                  help="Enter a GIT URL")

parser.add_option("-k", "--keyfile", dest="keyfile", default='$HOME/gittoken',
                  help="Enter GIT Token Keyfile")

parser.add_option("-d", "--dir", dest="temp_dir", default='/tmp/git',
                  help="Enter location of the temp dir")

(options, args) = parser.parse_args()

#Key Access Key
key_file = open(options.keyfile)
auth_key = key_file.readline().strip()

# Download all cookbooks from a GIT repo on a specific BRANCH
if not options.temp_dir:
    repo_base_dir = tempfile.mkdtemp()
else:
    repo_base_dir = options.temp_dir

print('-----------------------------------------------------------------------')
print('GIT URL  - ' + options.git_url)
print('BRANCH   - ' + options.git_branch)
print('TEMP DIR - ' + repo_base_dir)
print('GIT KEY  - ' + options.keyfile)
print('-----------------------------------------------------------------------')

repos = get_repos(options.git_url, 'OpenContent', '(cookbook_|camc_)', auth_key)
clone_repos(repos, auth_key, repo_base_dir, options.git_branch)

# Aggregate Metadata

if os.path.isdir(options.temp_dir):
    repo_metadata = RepositoryMetadata(options.temp_dir)

    repo_metadata.write_components_json(options.temp_dir + os.sep + 'components.json')
    repo_metadata.write_attributes_json(options.temp_dir + os.sep + 'attributes.json')
    repo_metadata.write_recipes_json(options.temp_dir + os.sep + 'recipes.json')
    repo_metadata.write_metadata_json(options.temp_dir + os.sep + 'cookbook_metadata.json')

    print '-----------------------------------------------------------------------'
    print 'Created - ' + options.temp_dir + os.sep + 'components.json'
    print 'Created - ' + options.temp_dir + os.sep + 'attributes.json'
    print 'Created - ' + options.temp_dir + os.sep + 'recipes.json'
    print 'Created - ' + options.temp_dir + os.sep + 'cookbook_metadata.json'

    sys.exit(0)
else:
    print "ERROR: Output path does not exist: " + temp_dir
    sys.exit(1)
