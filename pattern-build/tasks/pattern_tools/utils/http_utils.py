# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================
import httplib2
import json

from utils import logger


LOG = logger.get_logger(__name__)


def call_http(req_method, req_url, req_header=None, req_body=None):
    h = httplib2.Http()
    LOG.debug('Making http request: %s %s %s\n\t%s'
              % (req_url, req_method, req_header, req_body))
    resp, cont = h.request(req_url,
                           req_method,
                           headers=req_header,
                           body=req_body)
    LOG.debug('Reponse = %s' % resp)   
 
    if resp['status'] != '200':
        LOG.debug("http request returned status: %s" % resp['status'])
        return (resp['status'], None)

    try:
        data = json.loads(cont)
    except TypeError:
        # Running this in Python3
        # httplib2 returns byte objects
        data = json.loads(cont.decode())
    return (resp['status'], data)
