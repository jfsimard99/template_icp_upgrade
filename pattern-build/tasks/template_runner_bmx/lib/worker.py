# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import time
import sys
from logger import TestLogger
from iaas import AuthException
from iaas import IaaS


_WORKER_TIME_SEC = 60*60 # 1-hour

def life_cycle_stack(stack_name,template, parameters, camVariables, delete_failed_deployment, delete=True, statsd=None):
    '''
    Deploy the template and wait until it finishes successfully.
    Destroy the stack after the deployment finished.
    '''
    iaas = IaaS()
    result={}
    result['name'] = stack_name
    stack = None
    logger = TestLogger(__name__)
    delete_deployment = True
    if not delete:
        delete_deployment = False

    try:
        stack = iaas.deploy(stack_name,template, parameters, camVariables)
        iaas.waitForSuccess(stack, _WORKER_TIME_SEC)
    except AuthException, ex:
        logger.warning('Authentication Error, re-authenticating\n%s' %ex)
        stack = None
        raise ex
    except:
        ex = sys.exc_info()[0]
        logger.exception('Failed to deploy the template: stack name: %s' % (stack_name))
        result['deploy_error'] = ex
        if not delete_failed_deployment:
            delete_deployment = False # keep the failed deployments for debugging
    finally:
        if (stack is not None) and delete_deployment:
            try:
                time.sleep(60)
                iaas.destroy(stack)
                iaas.waitForSuccess(stack, _WORKER_TIME_SEC) # wait for destroy to be completed
                iaas.delete(stack)
            except AuthException, ex:
                logger.warning('Authentication Error, re-authenticating\n%s' %ex)
                raise ex
            except:
                ex = sys.exc_info()[0]
                logger.exception('Failed to delete/destroy the template %s; stack name: %s' % (stack.get('name'), stack_name))
                result['destroy_error'] = ex
    return result
