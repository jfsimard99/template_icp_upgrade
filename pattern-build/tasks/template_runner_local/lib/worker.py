# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import json
import time
import os
import sys
from threading import Thread
from datetime import datetime, timedelta
from random import randrange

#import lib.catalog as catalog
from lib.iaas import IaaS
import lib.stats as stats
from lib.logger import TestLogger, ResultLogger
from lib.iaas import AuthException

#TIMEOUT FOR Template 240 Mins
_10_MINUTES = 14400


class MonitorWorker(Thread):
    '''
    Monitor thread that collects the statistics from all the deployment workers and generates a file
    '''

    def __init__(self, workers, report_file):
        super(MonitorWorker, self).__init__()
        timestamp = datetime.now()
        self.start_time =  datetime.strftime(timestamp, '%H-%M-%S')
        self.end_time = None
        self.thread_name = "MonitorWorker"
        if type(workers) == list:
            self.workers = workers[::]
        else:
            self.workers = [workers]
        self.report_file = report_file
        self.collection_interval = float(os.environ['STAT_COLLECTION_INTERVAL'])
        self.logger = TestLogger(__name__)

    def addWorkers(self, workers):
        if type(workers) == list:
            self.workers += workers
        else:
            self.workers.append(workers)

    def run(self):
        while self.check_active(self.workers):
            # Make sure thread doesn't die
            try:
                self.monitor()
                # sleep before monitoring the workers again
                time.sleep(self.collection_interval)
            except Exception, e:
                self.logger.error(e)

        # retrieve the stats one more time after all the workers are done
        timestamp = datetime.now()
        self.end_time =  datetime.strftime(timestamp, '%H-%M-%S')

        self.monitor()

    def check_active(self, workers):
        for worker in workers:
            if worker.isAlive():
                return True
        return False

    def monitor(self):
        worker_results = []
        for worker in self.workers:
            worker_results += worker.getStats()
        stats.dump(worker_results, self.report_file, start_time=self.start_time, end_time=self.end_time)

class CleanWorker(Thread):
    '''
    Cleaning thread that loops through all the instances given to it and deletes them.
    '''

    def __init__(self, thread_number, instances, prefix='StressTest'):
        super(CleanWorker, self).__init__()
        self.thread_number = thread_number
        self.instances = instances
        self.iaas = IaaS()
        self.logger = TestLogger(__name__)
        self.prefix = prefix

    def run(self):
        for stack in self.instances:
            if stack['name'].startswith(self.prefix):
                try:
                    self.logger.info('Destroying %s' %stack['name'])
                    self.iaas.destroy(stack)
                    self.iaas.waitForSuccess(stack, _10_MINUTES)
                    self.logger.info('Successfully destroyed %s' %stack['name'])

                    self.logger.info('Deleting %s' %stack['name'])
                    self.iaas.delete(stack)
                    self.logger.info('Successfully deleted %s' %stack['name'])
                except:
                    self.logger.exception('Failed to delete/destroy stack %s' %stack['name'])

class StressWorker(Thread):
    '''
    Deployment thread that loops through all the templates from the local catalog and
    runs the life cycle tests for each template found.
    '''

    def __init__(self, thread_number, duration=None, statsd=None, random_delete=False):
        super(StressWorker, self).__init__()
        self.thread_number = thread_number
        self.thread_name = "StressWorker(%s)" % thread_number
        self.duration = duration
        self.statsd = statsd
        self.random_delete = random_delete
        self.stats = []
        self.iaas = IaaS()
        self.die = False
        self.logger = ResultLogger(__name__)

    def getStats(self):
        '''
        Retrieves the statistics
        '''
        return self.stats

    def _push_stats(self, result):
        '''
        Push the statistics to the statsd server
        '''
        if not result['deploy_error']:
            self.statsd.incr('ops.deploy.success')
            self.statsd.timing('ops.deploy', result['deploy_duration'].total_seconds() * 1000)
        else:
            self.statsd.incr('ops.deploy.failed')

        if 'destroy_error' in result:
            if not result['destroy_error']:
                self.statsd.incr('ops.destroy.success')
                self.statsd.timing('ops.destroy', result['destroy_duration'].total_seconds() * 1000)
            else:
                self.statsd.incr('ops.destroy.failed')

    def kill(self):
        self.die = True

    def _endLoop(self):
        if not self.duration:
            return self.die
        return datetime.now() - self.start >= timedelta(seconds=self.duration * 60 * 60) or self.die

    def run(self):
        self.start = datetime.now()
        to_be_deleted = True
        while not self._endLoop():
            # loop through all the templates from the local catalog
            template_names = catalog.get_local_templates()
            for template_name in template_names:
                if self._endLoop():
                    break

                [template, variables] = catalog.get_local_template(template_name)
                #
                # test the template life cycle: deploy, retrieve the details and destroy.
                #
                timestamp = time.time()
                stack_name = "StressTest%s_%s_%s" % (self.thread_number, template['name'].replace(" ", "_"), timestamp)
                if self.random_delete:
                    to_be_deleted = bool(randrange(0,2))
                try:
                    result = life_cycle_stack(self.iaas, stack_name, 'development', template_name, template, variables, False, delete=to_be_deleted)
                    result['stack_name'] = stack_name
                    self.stats.append(result)

                    if self.statsd:
                        self._push_stats(result)

                    if not result['deploy_error']:
                        self.logger.info('%s, Deploy, %s, %s, %s, N/A' %
                            (self.thread_number, result['deploy_start_time'], result['deploy_end_time'], result['deploy_duration']))
                    else:
                        self.logger.info('%s, Deploy, %s, N/A, N/A, %s' %
                            (self.thread_number, result['deploy_start_time'], result['deploy_error']))

                    if 'destroy_error' in result:
                        if not result['destroy_error']:
                            self.logger.info('%s, Destroy/Delete, %s, %s, %s, N/A' %
                                (self.thread_number, result['destroy_start_time'], result['destroy_end_time'], result['destroy_duration']))
                        else:
                            self.logger.info('%s, Destroy/Delete, %s, N/A, N/A, %s' %
                                (self.thread_number, result['destroy_start_time'], result['destroy_error']))

                except AuthException:
                    self.iaas = IaaS()

def life_cycle_stack(iaas, stack_name, git_branch, template_path, template, parameters, camVariables, delete_failed_deployment, delete=True, template_id=None, use_case='default'):

    '''
    Deploy the template and wait until it finishes successfully.
    Destroy the stack after the deployment finished.
    '''
    iaas = IaaS()
    result = {}
    result['name'] = stack_name
    stack = None
    logger = TestLogger(__name__)
    delete_deployment = True
    delete_template = True

    if not delete:
        delete_deployment = False
    if template_id:
        delete_template = False

    try:
        start_time = datetime.now()
        result['deploy_start_time'] = datetime.strftime(start_time, '%Y-%m-%d %H:%M:%S')
        logger.info('stack-name: %s' %stack_name)
        logger.info('delete_failed_deployment: %s' %delete_failed_deployment)
        logger.info('autoDestroy: %s' %delete)
        logger.info('delete Deployment: %s' %delete_deployment)
        logger.info('delete_template: %s' %delete_template)
        #logger.info('template: %s' %template)
        #logger.info('parameters: %s' %parameters)
        #logger.info('camVariables: %s' %camVariables)

        if not template_id:
            if 'starterlibrary' in template_path:
                template_path = '/'.join(template_path.split('/')[3:-1])
                template_id = iaas.import_template(
                    'github',
                    'https://github.ibm.com/Orpheus/starterlibrary',
                    template_path,
                    git_branch,
                    os.environ['GIT_TOKEN'])
            else:
                template_name = 'template_%s' % template_path.split('/')[-1][0:-3]
                template_path = '/%s' % '/'.join(template_path.split('/')[-3:-1])

                template_id = iaas.import_template(
                    'github',
                    'https://github.ibm.com/OpenContent/%s' % template_name,
                    template_path,
                    git_branch,
                    os.environ['GIT_TOKEN'])

        stack = iaas.deploy(stack_name, template_id, template, parameters, camVariables, use_case=use_case)
        iaas.waitForSuccess(stack, _10_MINUTES)

        # Will no longer delete the template after a successful deployment. CAM changed code to not
        # allow instances to be deleted if the template was destroyed.  CAM 2.1.0.2
        #if delete_template:
        #    iaas.delete_template(template_id)
        #    # Set to None after delete so we don't run the code in finally
        #    template_id = None

        end_time = datetime.now()
        result['deploy_duration'] = (end_time - start_time)
        result['deploy_end_time'] = datetime.strftime(end_time, '%Y-%m-%d %H:%M:%S')
        #result['deploy_error'] = None
    except AuthException, ex:
        logger.warning('Authentication Error, re-authenticating\n%s' %ex)
        stack = None
        raise ex
    except:
        ex = sys.exc_info()[0]
        logger.exception('Failed to deploy the template: stack name: %s' % (stack_name))
        result['deploy_error'] = ex
        if not delete_failed_deployment:
            delete_deployment = False  # keep the failed deployments for debugging
    finally:
        if (stack is not None) and delete_deployment:
            try:
                time.sleep(60)
                start_time = datetime.now()
                # result['destroy_start_time'] = datetime.strftime(start_time, '%Y-%m-%d %H:%M:%S')
                iaas.destroy(stack)
                iaas.waitForSuccess(stack, _10_MINUTES)  # wait for destroy to be completed
                iaas.delete(stack)
                # end_time = datetime.now()
                # result['destroy_duration'] = (end_time - start_time)
                # result['destroy_end_time'] = datetime.strftime(end_time, '%Y-%m-%d %H:%M:%S')
                # result['destroy_error'] = None
            except AuthException, ex:
                logger.warning('Authentication Error, re-authenticating\n%s' % ex)
                raise ex
            except:
                ex = sys.exc_info()[0]
                logger.exception('Failed to delete/destroy the template %s; stack name: %s' % (stack.get('name'), stack_name))
                result['destroy_error'] = ex
        if template_id and delete_template:
            try:
                iaas.delete_template(template_id)
            except AuthException, ex:
                logger.warning('Authentication Error, re-authenticating\n%s' % ex)
                raise ex
            except:
                ex = sys.exc_info()[0]
                logger.exception('Failed to delete the template %s' % template_id)
                result['destroy_error'] = ex
    return result


def get_cr_templates(provider):
    """Returns list of content runtime templates"""
    iaas = IaaS()
    templates = iaas.get_templates()
    template_json = templates.json()
    content_runtimes = []
    for template in template_json:
        if template['type'].lower() == 'contentruntime' and provider in template['name'].lower():
            content_runtimes.append(template)
    return content_runtimes


def delete_cr_templates(provider):
    iaas = IaaS()
    templates = get_cr_templates(provider)
    for template in templates:
        iaas.delete_template(template['id'])


def import_cr_template(github_hostname, github_repo_url, github_path, github_branch, github_token, type=None):
    iaas = IaaS()
    return iaas.import_template(github_hostname, github_repo_url, github_path, github_branch, github_token, type)


def create_cc(provider, request_data):
    iaas = IaaS()
    result = {}
    result['name'] = "cloud-connection"
    stack = None
    logger = TestLogger(__name__)
    delete_deployment = True
    use_case='default'

    cloud_connections_reponse = iaas.get_cloud_connections()
    cloud_connections_json = cloud_connections_reponse.json()

    cloud_found=0
    for cloud_connection in cloud_connections_json:
        if cloud_connection['name'] == request_data['name']:
            cloud_found = 1
        else:
            continue
            cloud_found = 0

    if cloud_found == 0:
        logger.info("Cloud Connection does NOT exist creating.....")
        iaas.create_cloud_connection(provider, request_data)
    else:
        logger.info("Cloud Connection DOES exist moving on.....")
