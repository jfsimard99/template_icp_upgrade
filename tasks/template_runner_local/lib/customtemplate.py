import os
from lib.logger import TestLogger
import urllib2
import hcl
import json


class CustomTemplate:
    def __init__(self):
        self.logger = TestLogger(__name__)

    def download_template(self):
        '''
        Test starter packs Bring Your Own Template Terraform file downloaded  from git repo.
        '''

        own_template_folder = os.path.join(os.environ['CATALOG_HOME'])
        if not os.path.exists(own_template_folder):
            os.makedirs(own_template_folder)
        os.chdir(os.path.join(os.getcwd(), os.environ['CATALOG_HOME']))
        self.logger.info("created %s " % own_template_folder)
        try:
            url = os.environ['GIT_TERRAFORM_TEMPLATE_FILE_URL']
            data = url.split('/')[-1]
            file_name = data.split('?')[0]
            # Creation of directory by template name
            file_name_without_extension = file_name.split('.')[0]
            self.logger.info("Downloading %s... " % file_name_without_extension)
            template_name = "custom_template_"+file_name_without_extension
            if not os.path.exists(template_name):
                os.makedirs(template_name)
            os.chdir(os.path.join(os.getcwd(), template_name))
            self.logger.info("created %s current path %s" % (template_name, os.getcwd()))
            u = urllib2.urlopen(url)
            f = open(file_name, 'wb')
            meta = u.info()
            file_size = int(meta.getheaders("Content-Length")[0])
            self.logger.info("Downloading File: %s Bytes: %s" % (file_name, file_size))
            file_size_dl = 0
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break
                file_size_dl += len(buffer)
                f.write(buffer)
            f.close()
        except:
            self.logger.exception("Failed to download terraform template file : %s" % file_name)

        if os.stat(file_name).st_size != 0:
            if file_name.endswith('.tf'):
                self._convert_hcl_to_json(file_name)
            elif file_name.endswith('.json'):
                self.logger.info("Downloaded terraform template file in JSON format : %s" % file_name)
            else:
                self.logger.warning("Unsupported file format : %s" % file_name)
        else:
            self.logger.exception("Downloaded file is empty %s " % file_name)

    def _convert_hcl_to_json(self, file_name):
        """
        Method to convert file HCL to JSON format.
        """
        try:
            with open(file_name, 'rb') as outfile:
                json_object = hcl.dumps(hcl.load(outfile))
                outfile.close()
                self._create_json_file(json_object, file_name)
                os.remove(file_name)  # Remove .tf file
        except:
            self.logger.exception("Failed to Convert file %s from HCL to JSON format." % file_name)

    def _create_json_file(self, json_data, file_name):
        """
        Method to create Final custom Template in JSON format  
        """
        try:
            with open("template.json", 'wb') as fd:
                template_data = json.loads(json_data)
                self.logger.info("Template Provider: %s" % (template_data["provider"].keys()[0]))
                self.template = self._get_base_template()
                data = self.template
                data["name"] = "custom_template_"+file_name
                data["manifest"]["template_provider"] = template_data["provider"].keys()[0]
                data["manifest"]["template"]["templateData"] = template_data
                json.dump(data, fd)
                fd.close()
            self.logger.info("Custom template file created in JSON format.")
            self._generate_variable_file(template_data)
        except:
            self.logger.exception("Failed to create custom template file in JSON format")

    def _generate_variable_file(self, template_data):
        """
        Read variables from custom template and create variables.json file.   
        """
        try:
            default_values = {"default": "", "description": "", "hidden": "false", "immutable": "false", "label": "",
                              "name": "", "required": "false", "secured": "false", "type": "string", "value": ""}
            vars_dict = template_data["variable"]
            var_list_of_dict = []
            for key, value in vars_dict.iteritems():
                if not var_list_of_dict:
                    final_variable = default_values.copy()
                    final_variable.update(value)
                    final_variable["label"] = key
                    final_variable["name"] = key
                    var_list_of_dict = [final_variable]
                else:
                    final_variable = default_values.copy()
                    final_variable.update(value)
                    final_variable["label"] = key
                    final_variable["name"] = key
                    var_list_of_dict.append(final_variable)
            with open("variables.json", "wb") as fd:
                json.dump(var_list_of_dict, fd)
                fd.close()
                self.logger.info("Successfully created variable.json file.")
        except:
            self.logger.exception("Failed to create Variables.json file.")

    def _get_base_template(self):
        """ 
        Read base template from local folder.
        """
        try:
            with open("../../custom_base_template/base_template.json") as json_data:
                data = json.load(json_data)
                json_data.close()
                self.logger.info("Successfully read base template: base_template.json")
            return data
        except:
            self.logger.exception("Failed to read base template: base_template.json")
