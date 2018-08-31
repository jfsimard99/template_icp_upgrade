import os

ENV = 'local'
CAM_URL = ''
AUTH_HOST = ''
CATALOG_HOST = ''
IAAS_HOST = ''
TENANT_HOST = ''

def set_env(vm_url, cam_port, env):

    global ENV
    global CAM_URL
    global AUTH_HOST
    global CATALOG_HOST
    global IAAS_HOST
    global TENANT_HOST

    # CAM_URL = 'https://' + os.environ['VM_URL'] + ':' + os.environ['CAM_PORT']
    ENV = env
    CAM_URL = 'https://' + vm_url + ':' + cam_port
    AUTH_HOST = CAM_URL + '/cam/v1/auth/identitytoken'
    CATALOG_HOST = CAM_URL + '/cam/catalog/api/v1/'
    IAAS_HOST = CAM_URL + '/cam/api/v1/'
    TENANT_HOST = CAM_URL + '/cam/tenant/api/v1'
