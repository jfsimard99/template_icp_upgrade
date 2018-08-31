from __future__ import division
#! /usr/bin/env python
# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

'''
Mandatory Environment variables
-------------------------------

GITTOKEN

Notes on execution
-------------------

The test runner will only run tests which have not been run before based on the status of the
test case.

'''


import json
import os
import sys
import argparse
import hcl
import fnmatch
import time
import glob
import datetime
import math

from threading import Thread
from multiprocessing import Pool, TimeoutError, Process, Queue

import lib.local.env as env
from lib.logger import TestLogger
import lib.worker as worker


logger = TestLogger(__name__)

dir_to_cloud = {"vmware": "vsphere", "aws": "aws", "ibmcloud": "ibm"}

test_pool = 7
worker_pause = 60


# Exit Codes
EXIT_DIRECTORY_EXISTS = 2

# Test Case Status Codes
CASE_UNTESTED = "case_untested"
CASE_INPROGRESS = "case_inprogress"
CASE_SUCCESS = "case_success"
CASE_FAILURE = "case_failure"

def _run_test_case(test_cases, index):

    '''
    Run a single test case, update the status once complete.
    '''

    test_case = test_cases[index]

    # Set status to in progress
    fp = open(test_case['test_case_file'], 'w+')
    test_case['status'] = CASE_INPROGRESS
    json.dump(test_case, fp)
    fp.close()

    # Execute the test
    result = os.system(test_case['command_line'] + '1>' + test_case['log_file'] + ' 2>&1')

    if result == 0:
        fp = open(test_case['test_case_file'], 'w+')
        test_case['status'] = CASE_SUCCESS
        json.dump(test_case, fp)
        fp.close()
    else:
        fp = open(test_case['test_case_file'], 'w+')
        test_case['status'] = CASE_FAILURE
        json.dump(test_case, fp)
        fp.close()

def _generate_runnable_test_case(test_case):

    '''
    Create the run_command field for the test case in question. The values for this field
    will be pulled from the

    - test case
    - testing variables
    - environment varibales where neccessary
    '''

    # Determine connection type
    cloud_to_conn = {"vsphere": "vmware", "aws": "aws", "ibm": "ibmcloud"}
    connection = ' -' + cloud_to_conn[test_case['cloud']] + ' ' + test_case['cloud_connection']

    # Determine --delete_failed_deployments
    if test_case['delete_failed_deployments'].upper() == "TRUE":
        delete_failed_deployments = " --delete_failed_deployments"
    else:
        delete_failed_deployments = ""

    # Determine --autodestroy
    if test_case['autodestroy'].upper() == "TRUE":
        autodestroy = " --autodestroy"
    else:
        autodestroy = ""

    template_runner_command = 'template_runner_local.py'
    template_runner_template = ' -t ' + test_case['template_file']
    template_runner_stack = ' -n ' + 'camtest-' + test_case['template_name'] + '_' + test_case['cloud'] + '_' + test_case['test_case']
    template_runner_instance = ' -c ' + test_case['cam_instance']
    template_runner_connection = connection
    template_runner_branch = ' -b ' + test_case['branch']
    template_runner_delete = delete_failed_deployments
    template_runner_destroy = autodestroy
    template_runner_camvariables = ' -cv ' + os.path.split(test_case['template_file'])[0] + os.sep + 'camvariables.json'
    template_runner_override = ' -o ' + os.path.split(test_case['template_file'])[0] + os.sep + 'override_variables.json'
    template_runner_testvars = ' -tf ' + test_case['testing_variables']
    template_runner_testcase = ' -uc ' + test_case['test_case']

    command_line = 'python ' \
        + template_runner_command \
        + template_runner_template \
        + template_runner_stack \
        + template_runner_instance \
        + template_runner_connection \
        + template_runner_branch \
        + template_runner_delete \
        + template_runner_destroy \
        + template_runner_camvariables \
        + template_runner_override \
        + template_runner_testvars \
        + template_runner_testcase \

    test_case['command_line'] = command_line

    return test_case

def _generate_test_status(test_cases):

    '''
    Cycle through each test case and return the status
    '''

    result = True
    success_tests = 0
    for test_case in test_cases:

        test_name = test_case['template_name'] + '_' + test_case['cloud'] + '_' + test_case['test_case']
        fp = open(test_case['test_case_file'])
        test_case_result = json.load(fp)
        fp.close()

        logger.info('%s : %s' % (test_name, test_case_result['status']))
        if not test_case_result['status'] == CASE_SUCCESS:
            result = False
        else:
            success_tests = success_tests + 1

    logger.info('%s / %s Test cases successful' % (success_tests, len(test_cases)))

    return result


def _run_test_queue(runnable_test_cases, test_cases):
    # Cycle through job_matrix and run each job in a thread
    job_index = 1
    floor = 1
    ceiling = test_pool
    if test_pool > len(runnable_test_cases):
        ceiling = len(runnable_test_cases)

    workers = list()
    for index in range(ceiling):
        worker = Process(target=_run_test_case, args=(runnable_test_cases, index))
        worker.start()
        workers.append(worker)

    keep_trying = True
    test_indices = range(ceiling)
    while keep_trying:
        remove_indices = []
        logger.info('Currently running tests %s-%s of %s' % (str(floor), str(ceiling), str(len(runnable_test_cases))))
        time.sleep(worker_pause)
        keep_trying = False
        for index in test_indices:
            fp = open(runnable_test_cases[index]['test_case_file'])
            test_case = json.load(fp)
            fp.close()
            test_name = test_case['template_name'] + '_' + test_case['cloud'] + '_' + test_case['test_case']

            # If we're in progress, keep going. Otherwise, add the index to the list of indices to remove
            if test_case['status'] == CASE_INPROGRESS or test_case['status'] == CASE_UNTESTED:
                keep_trying = True
            else:
                remove_indices.append(index)
            logger.info('Test Case Running : %s with Status of : %s' % (test_name, test_case['status']))

        for remove_index in remove_indices:
            try:
                test_indices.remove(remove_index)
                if ceiling < len(runnable_test_cases):
                    keep_trying = True
                    worker = Process(target=_run_test_case, args=(runnable_test_cases, ceiling))
                    worker.start()
                    workers.append(worker)
                    test_indices.append(ceiling)
                    ceiling = ceiling + 1
                    floor = floor + 1
                elif floor < len(runnable_test_cases):
                    floor = floor + 1
            except ValueError:
                pass

    logger.info('No more tests in progress, waiting for all worker threads to complete')
    for worker in workers:
        worker.join()

    job_index = job_index + 1

    logger.info('Testing Complete')

    return _generate_test_status(test_cases)


def _run_test_worker_pool(runnable_test_cases, test_cases):
    # Generate Work List

    job_matrix = []

    for job_index in range(int(math.ceil(len(runnable_test_cases) / test_pool))):
        worker_matrix = []
        for worker_index in range(test_pool):
            if job_index * test_pool + worker_index < len(runnable_test_cases):
                worker_matrix.append(runnable_test_cases[(job_index * test_pool) + worker_index])
            else:
                continue
        job_matrix.append(worker_matrix)

    # Cycle through job_matrix and run each job in a thread

    job_index = 1
    for job in job_matrix:
        workers = list()
        for index in range(len(job)):
            worker = Process(target=_run_test_case, args=(job, index))
            worker.start()
            workers.append(worker)

        keep_trying = True
        while keep_trying:

            logger.info('Currently Running Job %s of %s' % (str(job_index), str(len(job_matrix))))
            time.sleep(worker_pause)
            keep_trying = False
            for index in range(len(job)):
                fp = open(job[index]['test_case_file'])
                test_case = json.load(fp)
                fp.close()
                test_name = test_case['template_name'] + '_' + test_case['cloud'] + '_' + test_case['test_case']
                if test_case['status'] == CASE_INPROGRESS:
                    keep_trying = True
                logger.info('Test Case Running : %s with Status of : %s' % (test_name, test_case['status']))

        logger.info('No more tests in progress, waiting for all worker threads to complete')
        for worker in workers:
            worker.join()

        job_index = job_index + 1

        logger.info('Testing Complete')

    return _generate_test_status(test_cases)


def main():
    '''
    Generate a library of testcases based upon a test suite.
    '''
    parser = argparse.ArgumentParser(
        description='Generate a library of testcases based upon a test suite.',
        epilog='')
    parser.add_argument(
        '-d', '--base_dir',
        type=str, required=True,
        help='Root directory for test cases.')
    parser.add_argument(
        '--use_queue', default=False, action='store_true',
        help="Use queue-based deploy rather than worker pool (default: False)")
    args = parser.parse_args()

    # Get root directory of test
    if not os.path.isdir(args.base_dir):
        sys.exit('Suite test directory path does not exist')
    else:
        base_dir = args.base_dir

    # Check environment variables
    if not os.getenv('GIT_TOKEN', None):
        sys.exit('Error: GIT_TOKEN environment variable must be set')

    # Create structure of tests to be performed

    test_cases = []
    for test_case_file in glob.glob(base_dir + os.sep + '*.json'):
        fp = open(test_case_file)
        test_case = json.load(fp)
        logger.info('Found test case:  %s with status: %s' % (os.path.basename(test_case_file).split('.')[0], test_case['status']))
        if test_case['status'] == CASE_UNTESTED or test_case['status'] == CASE_FAILURE:
            test_cases.append(test_case)
        fp.close()

    # Resolve template_runner command line
    runnable_test_cases = []
    for test_case in test_cases:
        runnable_test_case = _generate_runnable_test_case(test_case)
        runnable_test_cases.append(runnable_test_case)

    if args.use_queue:
        _run_test_queue(runnable_test_cases, test_cases)
    else:
        _run_test_worker_pool(runnable_test_cases, test_cases)


if __name__ == "__main__":
    main()
