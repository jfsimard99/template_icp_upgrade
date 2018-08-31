## =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# ===============================================================

import sys

import repotools
import chef_repo

from optparse import OptionParser
from chef_repo import ChefRepo

# Process command line parameters

parser = OptionParser()
parser.add_option("-d", "--dir", dest="base_dir", default='.',
                  help="Base directory for the repository root, defaults to current directory", metavar="FILE")

(options, args) = parser.parse_args()

# Get base repository directory

rc,data = repotools.get_repo_root('chef', options.base_dir)

if rc != 0:
    print('ERROR:' + data)
    exit(rc)
else:
    repo_root = data
    print(data)


# Generate Repository Class

chef_repo = ChefRepo(repo_root)

errors = 0
for cookbook in chef_repo.cookbooks:
     # cookbook.print_metadata_attributes()
     cookbook.validate_recipe_metadata()
     if cookbook.error == 1:
         errors = 1

exit(errors)
