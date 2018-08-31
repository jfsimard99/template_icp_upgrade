#! /usr/bin/env python
# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import json
import os
import sys
import argparse
import hcl
import fnmatch
import time
import re

import lib.local.env as env
from lib.logger import TestLogger
import lib.worker as worker

logger = TestLogger(__name__)

dir_to_cloud = {"vmware": "vsphere", "amazon": "aws", "aws": "aws", "ibmcloud": "ibm", "bluemix": "ibm"}

# Exit Codes
EXIT_DIRECTORY_EXISTS = 2

# Test Case Status Codes
CASE_UNTESTED = "case_untested"
CASE_INPROGRESS = "case_inprogress"
CASE_SUCCESS = "case_success"
CASE_FAILURE = "case_failure"

def _load_and_validate_suite(test_suite):

    '''
    Validate the structure of the testsuite. Return True,suite_dict if the test suite is correct, False,Error Message if the suite is invalid
    '''

    # Load file into dictionary
    suite_dict = json.load(test_suite)
    suite_name = os.path.basename(test_suite.name).split('.')[0]

    # Check to see if the correct suite name exists as a key in suite_dict
    if not suite_name in suite_dict:
        return (False, 'Test suite must match the file name, suite does not exist: ' + suite_name)

    # Check all of the correct keys exist
    keys = ['clouds', 'test_cases', 'branch', 'delete_failed_deployments', 'autodestroy', 'not_template_regex', 'template_regex']
    for key in keys:
        if not key in suite_dict[suite_name]:
            return (False, 'Key does not exist in suite file. Key name missing: ' + key)

    return (True, suite_dict[suite_name])

def _get_cloud_from_file(filename):

    '''
    Based on a full template name, return the cloud type.
    '''

    if 'starterlibrary' in filename:
        cloud_dir = filename.split('/')[-5].lower()
    else:
        cloud_dir = filename.split('/')[-3].lower()

    if cloud_dir in dir_to_cloud:
        return dir_to_cloud[cloud_dir]
    else:
        return None

def _string_in_regexs(in_string, regexs):

    '''
    Determine if a string matches a list of regexs
    '''

    for regex in regexs.split(' '):
        if regex:
            if re.search(regex, in_string):
                return True
    return False

def _get_terraform_templates(template_directory, clouds, regexs, not_regexs):

    '''
    Walk through a directory structure and return a list of .tf files so long as the cloud
    type is matched by the clouds list.
    '''

    templates = []
    for root, dirnames, filenames in os.walk(template_directory):
        for filename in fnmatch.filter(filenames, '*.tf'):
            cloud = _get_cloud_from_file(os.path.join(root, filename))
            if cloud in clouds:
                if filename.split('_')[-1] not in ["variables.tf", "output.tf", "bastionhost.tf", "httpproxy.tf"]:
                    compare_string = filename
                    if 'starterlibrary' in root:
                        compare_string = root.split('/')[-1]
                    if _string_in_regexs(compare_string, regexs) and not _string_in_regexs(compare_string, not_regexs):
                        templates.append(os.path.join(root, filename))
                        break
    return templates

def _generate_test_case(template_file, test_suite, testing_variables_file, test_branch, cam_instance):

    '''
    Create a specific test case for a specific cloud and template.
    Return as an array of dictionaries.
    '''

    cloud_type = _get_cloud_from_file(template_file)
    fp = open(testing_variables_file.name)
    testing_variables = json.load(fp)
    fp.close()

    test_cases = []
    test_case_list = []
    if not test_suite['test_cases'][cloud_type]:
        return []
    elif test_suite['test_cases'][cloud_type] == "*":
        if 'use_cases' in testing_variables['virtual_machines'][cloud_type]:
            test_case_list = testing_variables['virtual_machines'][cloud_type]['use_cases'].keys()
            test_case_list.append('default')
        else:
            test_case_list = ['default']
    else:
        for test_case in test_suite['test_cases'][cloud_type].split():
            if 'use_cases' in testing_variables['virtual_machines'][cloud_type]:
                if test_case in testing_variables['virtual_machines'][cloud_type]['use_cases'].keys() or test_case == 'default':
                    test_case_list.append(test_case)
            else:
                test_case_list = ['default']

    # Reslve the branch
    if test_branch == "None":
        branch = test_suite['branch']
    else:
        branch = test_branch

    # Resolve the cam_instance
    if cam_instance == "None":
        instance = testing_variables['test_data']['cam_instance']
    else:
        instance = cam_instance

    for test_case in test_case_list:
        test_case_dict = {}
        if 'starterlibrary' in template_file:
            template_name = template_file.split('/')[-2]
            if template_name == 'hcl':
                continue
            test_case_dict['template_name'] = template_name
        else:
            test_case_dict['template_name'] = os.path.basename(template_file).split('.')[0]
        test_case_dict['template_file'] = template_file
        test_case_dict['cloud'] = _get_cloud_from_file(template_file)
        test_case_dict['testing_variables'] = testing_variables_file.name
        test_case_dict['test_case'] = test_case
        test_case_dict['branch'] = branch
        test_case_dict['autodestroy'] = test_suite['autodestroy']
        test_case_dict['delete_failed_deployments'] = test_suite['delete_failed_deployments']
        test_case_dict['status'] = CASE_UNTESTED
        test_case_dict['cam_instance'] = instance
        test_case_dict['cloud_connection'] = testing_variables['test_data']['cloud_connection'][cloud_type]
        test_cases.append(test_case_dict)

    return test_cases

def main():
    '''
    Generate a library of testcases based upon a test suite.
    '''
    parser = argparse.ArgumentParser(
        description='Generate a library of testcases based upon a test suite.',
        epilog='')
    parser.add_argument(
        '-s', '--test_suite',
        type=argparse.FileType('r'), required=True,
        help='Test suite json file')
    parser.add_argument(
        '-tf', '--testing_variables',
        type=argparse.FileType('r'), default='testing_variables.json',
        required=False,
        help='Testing variables file')
    parser.add_argument(
        '-t', '--template_directory',
        type=str, required=True,
        help='Base directory to search for Terraform Templates')
    parser.add_argument(
        '-cl', '--clouds', nargs='+',
        type=str, required=False,
        help='List of clouds to test')
    parser.add_argument(
        '-o', '--output_dir', default='/tmp',
        type=str, required=False,
        help='Root directory for test')
    parser.add_argument(
        '-b', '--branch',
        type=str, required=False, default='None',
        help='Name of the branch to test against, default stored in the suite.')
    parser.add_argument(
        '-c', '--cam_instance',
        type=str, required=False, default='None',
        help='IP Address of CAM to test against, default stored in the testing_variables.json.')
    args = parser.parse_args()

    #Get suite_dict

    valid, result = _load_and_validate_suite(args.test_suite)
    test_suite = None
    if not valid:
        logger.exception(result)
    else:
        test_suite = result

    # Get testing_variables which will populate some default values

    testing_variables = json.load(args.testing_variables)

    # Validate template directory

    if os.path.isdir(args.template_directory):
        template_directory = args.template_directory
    else:
        logger.exception('Template path does not exist: %s ' % args.template_directory)

    # Validate Output Directory and create base suite directory

    if os.path.isdir(args.output_dir):
        output_dir = args.output_dir
    else:
        logger.exception('Output path does not exist: %s ' % args.output_dir)

    suite_name = os.path.basename(args.test_suite.name).split('.')[0]
    base_output_directory = os.path.join(output_dir, 'cam_testing', suite_name)

    if not os.path.exists( base_output_directory):
        os.makedirs(base_output_directory)
        os.makedirs(base_output_directory + os.sep + 'logs')
    else:
        logger.exception('Suite directory already exists: %s ' % base_output_directory)
        sys.exit(EXIT_DIRECTORY_EXISTS)

    # Find Terraform templates

    if args.clouds:
        clouds = args.clouds
    else:
        clouds = test_suite['clouds']

    templates = _get_terraform_templates(template_directory, clouds, test_suite['template_regex'], test_suite['not_template_regex'])

    # Generate testcases

    test_cases = []
    for template in templates:
        test_case = _generate_test_case(template, test_suite, args.testing_variables, args.branch, args.cam_instance)
        test_cases = test_cases + test_case

    # Save test case files
    logger.info('Creating Test Cases')
    for test_case in test_cases:
        filename = os.path.join(base_output_directory, test_case['template_name'] + '_' + test_case['cloud'] + '_' + test_case['test_case'] + '.json')
        test_case['test_case_file'] = filename
        test_case['log_file'] = base_output_directory + os.sep + 'logs' + os.sep + test_case['template_name'] + '_' + test_case['cloud'] + '_' + test_case['test_case'] + '.log'
        fp = open(filename, 'w')
        logger.info('Test Case Generated: %s ' % filename)
        json.dump(test_case, fp)
        fp.close()

if __name__ == "__main__":
    main()
