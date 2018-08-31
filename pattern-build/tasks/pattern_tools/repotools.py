# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import sys
import os
import logging
import glob


def get_repo_root(repo_type, current_dir='none'):

    """

    get_repo_root will return the root directory of the current 
    repository. The location of the repository is determined by the 
    relative location of known directories based on the repository 
    type. The repo_type parameter determines the common known relative 
    directory that determines the Repository Root for any given directory.

    :param str repo_type: Content type of the repository.

    :param str current_dir: The base directory, if empty, set to the cwd.

    """

    repo_types=[['chef','chef' + os.sep + 'cookbooks']]
    repo_dir=""

    #Processing Parameters

    for type, dir in repo_types:
        if repo_type == type:
            repo_dir = dir
            break

    if not repo_dir:
        logging.debug('%s is not a valid repository type.', repo_type )
        return (1, 'Invalid Repository Type')

    if current_dir == 'none':
        current_dir = os.getcwd()
    else:
        if not os.path.isdir(current_dir):
            logging.debug('%s is not a valid directory.', current_dir)
            return (1, 'Invalid source directory')

    # Find Repository Root

    found_repo = False
    dir_name = current_dir
    while dir_name:

        if os.path.isdir(os.path.normpath(dir_name) + os.sep + repo_dir):
#    	    logging.info('Found a valid repository root %s.', dir_name )
    	    found_repo = True
    	    break
        else:
            last_dir = os.path.basename(os.path.normpath(dir_name))
            dir_name = dir_name[:-(len(last_dir)+1)]

    if not found_repo:
        logging.debug('No valid repository found in the path of ', current_dir)
        return (1, 'No valid directory path found')
    else:
        return (0, dir_name)


def get_cookbook_roots(repo_root):

    """

    get_cookbook_roots will return a list of cookbook roots from a repository.

    :param str repo_root: The root directory of the repository.

    """

    cookbook_roots = []

    for cookbook_root in glob.glob(repo_root + os.sep + 'chef' + os.sep 
                                   + 'cookbooks' + os.sep + '*'):
        if os.path.isdir(cookbook_root):
            cookbook_roots.append(cookbook_root)
    return(cookbook_roots)

def get_chef_internal(cookbook_repo_root):

    """

    get_chef_internal will return the full file path of the internal.rb
    file

    :param str repo_root: The root directory of the repository.

    """

    return (os.path.normpath(cookbook_repo_root) + os.sep + 'attributes'
                                                 + os.sep + 'internal.rb')

def get_chef_default(cookbook_repo_root):

    """

    get_chef_default will return the fully file path of the default.rb
    file.

    :param str repo_root: The root directory of the repository.

    """

    return (os.path.normpath(cookbook_repo_root) + os.sep + 'attributes'
                                                 + os.sep + 'default.rb')

def get_chef_metadata(cookbook_repo_root):

    """

    get_chef_metadata will return the fully file path of the 
    metadata.rb file.

    :param str repo_root: The root directory of the repository.

    """

    return (os.path.normpath(cookbook_repo_root) + os.sep + 'metadata.rb')

def get_chef_recipes(cookbook_repo_root):

    """

    get_chef_recipes will return a dictionary of the file path of all chef
    recipes.

    :param str repo_root: The root directory of the repository.

    """

    return (glob.glob(cookbook_repo_root + os.sep + 'recipes' 
                                         + os.sep + '*.rb'))

def get_chef_roles(repo_root):

    """

    get_chef_recipes will return a dictionary of the file path of all chef
    recipes.

    :param str repo_root: The root directory of the repository.

    """

    return (glob.glob(repo_root + os.sep + 'chef' + os.sep + 'roles' 
                                + os.sep + '*.json'))
