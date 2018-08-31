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

import json

from templatetools import get_template_roots
from templatetools import get_template_name
from templatetools import get_template_heat
from templatetools import get_template_dir
from templatetools import read_heat_template
from templatetools import get_template_data
from templatetools import create_template_readme
from templatetools import create_template_readmes
from templatetools import write_template_readmes
from templatetools import create_catalogs
from templatetools import write_catalogs

class TemplateRepository:


    def __init__(self, template_repository_root, components_file, metadata_file):
        print "--------------------------------------------------------------------------------"
        print "Initialising Templates from " + template_repository_root
        self.template_roots = get_template_roots(template_repository_root)
        print "Found " + str(len(self.template_roots)) + " Templates."
        print "--------------------------------------------------------------------------------"

        #Populate components from the components.json file.
        if os.path.isfile(components_file):
            # Read components file
            file = open(components_file)
            self.components = json.load(file)
            file.close()
        else:
            print ('Component file does not exist, exiting.')
            return None
        self.templates = []

        #Populate metadata from the metadata.json file.
        if os.path.isfile(metadata_file):
            # Read metadata file
            file = open(metadata_file)
            self.metadata = json.load(file)
            file.close()
        else:
            print ('Metadata file does not exist, exiting.')
            return None
        self.templates = []
        for template_root in self.template_roots:
            new_template = Template(template_root, self.components)
            if new_template.success:
                self.templates.append(new_template)

    def number_of_Templates(self):

        return len(self.template_roots)

    def get_template_roots(self):

        return self.template_roots

    def generate_template_readmes(self):

        for template in self.templates:
            template.generate_template_readmes(self.components, self.metadata)

    def write_template_readmes(self):

        for template in self.templates:
            template.write_template_readmes()

    def generate_catalogs(self):

        for template in self.templates:
            template.generate_catalogs(self.components, self.metadata)

    def write_catalogs(self):

        for template in self.templates:
            template.write_catalogs()

class Template:


    def __init__(self, template_root, components):
        self.template_root = template_root
        self.template_name = get_template_name(self.template_root)
        self.heat_template = get_template_heat(self.template_root, self.template_name)
        self.amazon_template_dir = get_template_dir(self.template_root, 'amazon')
        self.ibmcloud_template_dir = get_template_dir(self.template_root, 'ibmcloud')
        self.vmware_template_dir = get_template_dir(self.template_root, 'vmware')
        self.heat_dict = {}
        self.heat_metadata = {}
        self.readmes = {}
        self.success = True
        self.error = " "

        if self.heat_template:

            self.heat_dict = read_heat_template(self.heat_template)
            self.success, self.error, self.heat_metadata = get_template_data(self.heat_dict, components)

        if not self.heat_template:
            self.error = 'Skipped due to missing or incorrect HOT Template.'
            self.success = False

        spaces = ''
        offset = 40 - len(self.template_name)
        spaces += ' '*offset
        if self.success:
            print 'Template: ' + self.template_name + spaces +'SUCCESS'
        else:
            print 'Template: ' + self.template_name + spaces + 'FAILED: ' + self.error

    def generate_template_readmes(self, component_metadata, cookbook_metadata):

        self.readmes = create_template_readmes(self.heat_metadata, component_metadata, cookbook_metadata)

    def write_template_readmes(self):

        write_template_readmes(self.readmes, self.template_root)

    def generate_catalogs(self, component_metadata, cookbook_metadata):

        self.catalogs = create_catalogs(self.heat_metadata, component_metadata, cookbook_metadata, self.template_name)

    def write_catalogs(self):

        write_catalogs(self.catalogs, self.template_root)
