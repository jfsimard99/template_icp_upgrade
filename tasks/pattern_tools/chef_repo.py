# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import shutil
import os
import sys

import repotools
import metadatatools
import json

from repotools import get_chef_recipes
from repotools import get_chef_internal
from repotools import get_chef_default
from repotools import get_chef_metadata
from repotools import get_chef_roles
from repotools import get_cookbook_roots
from metadatatools import print_dictionary
from metadatatools import is_attribute_line
from metadatatools import get_chef_attribute_metadata
from metadatatools import get_chef_recipe_metadata
from metadatatools import get_chef_recipe_attributes
from metadatatools import get_chef_recipe_attributes_internal
from metadatatools import get_chef_role_metadata
from metadatatools import print_metadata_attributes
from metadatatools import print_metadata_recipes
from metadatatools import write_attributes_json
from metadatatools import write_components_json
from metadatatools import write_recipes_json
from metadatatools import validate_metadata
from metadatatools import merge_json_to_dict


class RepositoryMetadata:


    def __init__(self, repo_root):
        self.cookbooks = []
        self.attribute_files = []
        self.component_files = []
        self.recipe_files = []
        self.metadata_files = []
        self.attribute_metadata = {}
        self.component_metadata = {}
        self.recipe_metadata = {}
        self.cookbook_metadata = {}

        for cookbook_roots in os.listdir(repo_root):
            for cookbook_root in get_cookbook_roots(os.path.join(repo_root, cookbook_roots)):
                self.cookbooks.append(cookbook_root)

        # Determine metadata files

        for cookbook in self.cookbooks:
            if os.path.isfile(os.path.join(cookbook, 'attributes.json')):
                self.attribute_files.append(os.path.join(cookbook, 'attributes.json'))

        for cookbook in self.cookbooks:
            if os.path.isfile(os.path.join(cookbook, 'components.json')):
                self.component_files.append(os.path.join(cookbook, 'components.json'))

        for cookbook in self.cookbooks:
            if os.path.isfile(os.path.join(cookbook, 'recipes.json')):
                self.recipe_files.append(os.path.join(cookbook, 'recipes.json'))

        for cookbook in self.cookbooks:
            if os.path.isfile(os.path.join(cookbook, 'cookbook_metadata.json')):
                self.metadata_files.append(os.path.join(cookbook, 'cookbook_metadata.json'))

        # Aggregate metadata

        for attribute_file in self.attribute_files:
            self.attribute_metadata = merge_json_to_dict(self.attribute_metadata, attribute_file)

        for component_file in self.component_files:
            self.component_metadata = merge_json_to_dict(self.component_metadata, component_file)
        self.component_metadata = {"components": self.component_metadata}

        for recipe_file in self.recipe_files:
            self.recipe_metadata = merge_json_to_dict(self.recipe_metadata, recipe_file)

        for metadata_file in self.metadata_files:
            print metadata_file
            self.cookbook_metadata = merge_json_to_dict(self.cookbook_metadata, metadata_file)

    def write_components_json(self, file):

        component_file = open(file, "w+")
        json.dump(self.component_metadata, component_file,sort_keys=True, indent=4, separators=(',', ': '))
        component_file.close()


    def write_attributes_json(self, file):

        attribute_file = open(file, "w+")
        json.dump(self.attribute_metadata, attribute_file,sort_keys=True, indent=4, separators=(',', ': '))
        attribute_file.close()


    def write_recipes_json(self, file):

        recipe_file = open(file, "w+")
        json.dump(self.recipe_metadata, recipe_file,sort_keys=True, indent=4, separators=(',', ': '))
        recipe_file.close()

    def write_metadata_json(self, file):

        metadata_file = open(file, "w+")
        json.dump(self.cookbook_metadata, metadata_file,sort_keys=True, indent=4, separators=(',', ': '))
        metadata_file.close()

class ChefRepo:


    def __init__(self, repo_root):
        self.cookbooks = []
        for cookbook_root in get_cookbook_roots(repo_root):
            self.cookbooks.append(ChefCookbook(cookbook_root, repo_root))


class ChefCookbook:


    def __init__(self, cookbook_root, repo_root):
        self.cookbook_root = cookbook_root
        self.recipes = get_chef_recipes(cookbook_root)
        self.default = get_chef_default(cookbook_root)
        self.internal = get_chef_internal(cookbook_root)
        self.metadata = get_chef_metadata(cookbook_root)
        self.roles = get_chef_roles(repo_root)
        self.metadata_attributes, self.dynamic_attributes = get_chef_attribute_metadata(self.default)
        self.metadata_recipes = get_chef_recipe_metadata(self.recipes)
        self.metadata_roles = get_chef_role_metadata(self.roles)
        self.recipe_attributes = get_chef_recipe_attributes(self.recipes)
        self.recipe_attributes_internal = get_chef_recipe_attributes_internal(self.internal)
        self.error = 0

    def print_metadata_attributes(self):
        print_dictionary(self.metadata_attributes)

    def print_recipe_attributes(self):
        print_dictionary(self.recipe_attributes)

    def print_recipe_attributes_internal(self):
        print_dictionary(self.recipe_attributes_internal)

    def print_metadata_roles(self):
        print_dictionary(self.metadata_roles)

    def print_metadata_recipes(self):
        print_dictionary(self.metadata_recipes)

    def validate_recipe_metadata(self):
        self.error = validate_metadata(self.recipe_attributes, self.recipe_attributes_internal,
                          self.metadata_attributes, self.cookbook_root.split('/')[-1])

    def clear_metadata_file(self):
        metadata_file = open(self.metadata, "r+")

        # shutil.copyfile(self.metadata, self.metadata + '.bak')
        try:
            os.remove(self.metadata + '.bak')
        except OSError:
            pass

        trunc = 0

        for line in metadata_file.readlines():
            if is_attribute_line(line):
                print trunc
                break
            else:
                trunc = trunc + len(line)

        metadata_file.truncate(trunc)
        metadata_file.close()

    def write_metadata_file(self):

        metadata_file = open(self.metadata, "a")
        print_metadata_attributes(self.metadata_attributes, metadata_file)
        metadata_file.close()

        metadata_file = open(self.metadata, "a")
        print_metadata_recipes(self.metadata_recipes, metadata_file)
        metadata_file.close()

    def write_attribute_json(self):

        attribute_file = open(self.cookbook_root + os.sep + 'attributes.json', "w+")
        write_attributes_json(self.metadata_attributes, attribute_file)
        attribute_file.close()

    def write_components_json(self):

        component_file = open(self.cookbook_root + os.sep + 'components.json', "w+")
        write_components_json(self.metadata_roles, self.dynamic_attributes, component_file)
        component_file.close()

    def write_recipes_json(self):

        recipe_file = open(self.cookbook_root + os.sep + 'recipes.json', "w+")
        write_recipes_json(self.metadata_recipes, recipe_file)
        recipe_file.close()
