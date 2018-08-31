import os

try:
    stage1 = ''
    if os.environ['STAGE1'] != '':
        stage1 = '.' + os.environ['STAGE1']
except:
    pass

env = '-' + os.environ['TEST_ENVIRONMENT']
if env == '-prod':
    env = ''

AUTH_HOST = 'https://api%s.ng.bluemix.net' % stage1

CATALOG_HOST = 'https://cam-proxy%s%s.ng.bluemix.net/cam/catalog/api/v1/' % (env, stage1)
IAAS_HOST = 'https://cam-proxy%s%s.ng.bluemix.net/cam/api/v1/' % (env, stage1)
TENANT_HOST = 'https://cam-tenant-api%s%s.ng.bluemix.net/api/v1' % (env, stage1)
DASHBOARD = 'https://cam-proxy%s%s.ng.bluemix.net/cam/ui/dashboard' % (env, stage1)
