# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================


import logging
import os

class TestLogger(logging.Logger, object):
    '''
    Logger class for acceptance tests
    '''

    def __init__(self, loggerName=__name__):
        super(TestLogger, self).__init__(loggerName)

        formatter = logging.Formatter('%(asctime)s (%(thread)d) - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        self.addHandler(handler)
        self.setLevel(logging.INFO)

class ResultLogger(logging.Logger, object):
    '''
    Logger class to log results of each operation
    '''

    def __init__(self, loggerName=__name__):
        super(ResultLogger, self).__init__(loggerName)

        formatter = logging.Formatter('%(message)s')
        handler = logging.FileHandler(os.environ['RESULTS_LOG'], mode='a')
        handler.setFormatter(formatter)

        self.addHandler(handler)
        self.setLevel(logging.INFO)
