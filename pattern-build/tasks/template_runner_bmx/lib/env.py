# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================


import os

CATALOG_HOST = ''
IAAS_HOST = ''
TENANT_HOST = ''
DASHBOARD = ''
AUTH_HOST = ''

def set_env(environment):
    global CATALOG_HOST
    global IAAS_HOST
    global TENANT_HOST
    global DASHBOARD
    global AUTH_HOST

    stage1 = ''
    if os.getenv('STAGE1', None):
        stage1 = '.' + os.environ['STAGE1']

    AUTH_HOST = 'https://api%s.ng.bluemix.net' % stage1

    if environment == 'prod':
        CATALOG_HOST = 'https://cam-proxy-ng.ng.bluemix.net/cam/catalog/api/v1/'
        IAAS_HOST = 'https://cam-proxy-ng.ng.bluemix.net/cam/api/v1'
        TENANT_HOST = 'https://cam-proxy-ng.ng.bluemix.net/cam/tenant/api/v1'
        DASHBOARD = 'https://cam-proxy-ng.ng.bluemix.net/cam/ui/dashboard'
    else:
        CATALOG_HOST = 'https://cam-proxy-%s%s.ng.bluemix.net/cam/catalog/api/v1/' % (environment, stage1)
        IAAS_HOST = 'https://cam-proxy-%s%s.ng.bluemix.net/cam/api/v1/' % (environment, stage1)
        TENANT_HOST = 'https://cam-tenant-api-%s%s.ng.bluemix.net/api/v1' % (environment, stage1)
        DASHBOARD = 'https://cam-proxy-%s%s.ng.bluemix.net/cam/ui/dashboard' % (environment, stage1)
