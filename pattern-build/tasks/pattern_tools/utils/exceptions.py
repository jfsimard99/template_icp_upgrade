# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================
from utils import logger


LOG = logger.get_logger(__name__)


class MicroserviceException(Exception):

    def __init__(self, message, status_code, data_json=None):
        self.status_code = status_code
        self.data_json = data_json
        self.message = message


class AuthorizationException(MicroserviceException):

    def __init__(self, message, data_json=None):
        LOG.debug('AuthorizationException: %s' % message)
        super(AuthorizationException, self).__init__(message, 401,
                                                     data_json=data_json)


class BadParameterException(MicroserviceException):

    def __init__(self, message, data_json=None):
        LOG.debug('BadParameterException: %s' % message)
        super(BadParameterException, self).__init__(message, 400,
                                                    data_json=data_json)


class ExecutionException(MicroserviceException):

    def __init__(self, message, data_json=None):
        LOG.debug('ExecutionException: %s' % message)
        super(ExecutionException, self).__init__(message, 500,
                                                 data_json=data_json)


class DeprecatedAPIException(MicroserviceException):

    def __init__(self, message, data_json=None):
        LOG.debug('DeprecatedAPIException: %s' % message)
        super(DeprecatedAPIException, self).__init__(message, 501,
                                                     data_json=data_json)


class RetryableException(MicroserviceException):

    def __init__(self, message, data_json=None):
        LOG.debug('RetryableException: %s' % self.message)
        super(RetryableException, self).__init__(message, 500,
                                                 data_json=data_json)


def retry_if_retryable_exception(exc):
    return isinstance(exc, RetryableException)
