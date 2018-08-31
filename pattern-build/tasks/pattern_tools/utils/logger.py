# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================
import json
import logging
import os
import re
import threading

#from flask import g

from utils import environment as env


FLASK_LOG = os.path.join(os.sep,
                         os.getenv(env.LOG_PATH, env.LOG_PATH_DEFAULT),
                         'aggregateGITMetadata.log')
logging.basicConfig(filename=FLASK_LOG,
                    format=('%(request_id)-32s '
                            '%(asctime)-15s %(levelname)-8s %(message)s'),
                    level=logging.DEBUG)

# TODO(jecarey) could look explicitly for DEBUG, WARN, etc.
LOG_INFO_REGEX = (r'^(NIAR)?[0-9a-fA-F]+ +\d{4}-\d{2}-\d{2} '
                  r'\d{2}:\d{2}:\d{2},\d{3} \S+.*')
LOG_INFO_PAT = re.compile(LOG_INFO_REGEX)


def get_request_id():
    try:
        req_id = g.pm_req_id
    except Exception:
        try:
            req_id = 'NIAR%s' % str(threading.current_thread().ident)
        except Exception:
            req_id = 'NIAR0000'
    return req_id


class RequestIdAdapter(logging.LoggerAdapter):

    def process(self, msg, kwargs):
        extra = {'request_id': get_request_id()}
        extra.update(self.extra)
        if 'extra' in kwargs:
            extra.update(kwargs.pop('extra'))
        extra['extra_keys'] = list(sorted(extra.keys()))
        kwargs['extra'] = extra
        return msg, kwargs


def get_logger(mod_name):
    return RequestIdAdapter(logging.getLogger(mod_name), {})


LOG = get_logger(__name__)


def fmt_output(in_output, new_line=True):
    if not in_output or not in_output.strip():
        return " --- Empty ---"
    if new_line:
        fmt_str = "\n\t%s"
    else:
        fmt_str = "%s"
    return fmt_str % (in_output.replace('\n', '\n\t'))


def fmt_json(in_json):
    return fmt_output(json.dumps(in_json, sort_keys=True, indent=2))


def load_log(log_filters=None, log_pruners=None):
    log = []
    log_filters = log_filters if log_filters else []
    log_pruners = log_pruners if log_pruners else []
    with open(FLASK_LOG, 'r') as log_file:
        log_entry = {'tds': None, 'body': ''}
        for line in log_file:
            if LOG_INFO_PAT.match(line):
                if log_entry['tds']:
                    filter_entry = False
                    for log_filter in log_filters:
                        filter_entry = log_filter(log_entry)
                        if filter_entry:
                            break
                    if not filter_entry:
                        for pruner in log_pruners:
                            pruner(log_entry)
                        log.append(log_entry)
                info = line.split()
                log_entry = {'request_id': info[0],
                             'tds': "%s %s" % (info[1], info[2]),
                             'level': info[3]}
                if len(info) > 4:
                    log_entry['body'] = ' '.join(info[4:])
                else:
                    log_entry['body'] = ''
            else:
                log_entry['body'] += line
    return log
