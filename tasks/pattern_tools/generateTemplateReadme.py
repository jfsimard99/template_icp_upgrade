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

from chef_repo import RepositoryMetadata
from git_helper import LocalGitClone
from git_helper import get_repos
from git_helper import clone_repos

from optparse import OptionParser
from heat_templates import TemplateRepository

# Process command line parameters

parser = OptionParser()
parser.add_option("-d", "--dir", dest="base_dir", default='.',
                  help="Base directory for the template root, defaults to current directory", metavar="FILE")

parser.add_option("-c", "--chef", dest="download_chef", default='true',
                  help="Enter true or false on whether to download Chef Cookbooks. Set to false if already downloaded.")

parser.add_option("-b", "--branch", dest="git_branch", default='development',
                  help="Enter a branch to clone.")

parser.add_option("-g", "--giturl", dest="git_url", default='github.ibm.com',
                  help="Enter a GIT URL.")

parser.add_option("-k", "--keyfile", dest="keyfile", default='$HOME/gittoken',
                  help="Enter GIT Token Keyfile.")

parser.add_option("-t", "--temp", dest="temp_dir", default='/tmp/chef',
                  help="Enter location of the temp dir to download chef cookbooks.")

(options, args) = parser.parse_args()

if options.download_chef == 'true':
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
    repo_metadata.write_metadata_json(options.temp_dir + os.sep + 'cookbook_metadata.json')

    print '-----------------------------------------------------------------------'
    print 'Created - ' + options.temp_dir + os.sep + 'components.json'
    print 'Created - ' + options.temp_dir + os.sep + 'cookbook_metadata.json'

else:
    print "ERROR: Temporary Chef path does not exist: " + temp_dir
    sys.exit(1)

# Generate Repository Class
template_repo = TemplateRepository(options.base_dir, options.temp_dir + os.sep + 'components.json', options.temp_dir + os.sep + 'cookbook_metadata.json')
if template_repo:
    template_repo.generate_template_readmes()
    template_repo.write_template_readmes()
    template_repo.generate_catalogs()
    template_repo.write_catalogs()
print ''
