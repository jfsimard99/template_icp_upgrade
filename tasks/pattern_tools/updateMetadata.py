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

import repotools
import chef_repo
import json

from optparse import OptionParser
from chef_repo import RepositoryMetadata

# Process command line parameters

parser = OptionParser()
parser.add_option("-b", "--branch", dest="branch", default='landscaper-dev-env',
                  help="Source GIT Branch for Metadata", metavar="BRANCH")

parser.add_option("-g", "--git", dest="git", default='github.ibm.com',
                  help="Location of the GIT Repository", metavar="FILE")

(options, args) = parser.parse_args()


# Generate RepositoryMetadata Class

if os.path.isdir(options.out_dir):
    repo_metadata = RepositoryMetadata(options.base_dir)

    repo_metadata.write_components_json(options.out_dir + os.sep + 'components.json')
    repo_metadata.write_attributes_json(options.out_dir + os.sep + 'attributes.json')
    repo_metadata.write_recipes_json(options.out_dir + os.sep + 'recipes.json')

    sys.exit(0)
else:
    print "ERROR: Output path does not exist: " + out_dir
    sys.exit(1)
    
