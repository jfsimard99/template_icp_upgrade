# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================
import re
import subprocess

from retrying import retry

from utils import logger

LOG = logger.get_logger(__name__)

CFG_COMMANDS_SECTION = 'commands'
CFG_COMMANDS_RETRY_ATTEMPTS = 'retry_attempts'
CFG_COMMANDS_RETRY_ATTEMPTS_DEFAULT = 20
CFG_COMMANDS_RETRY_WAIT_MSEC = 'retry_wait_msec'
CFG_COMMANDS_RETRY_WAIT_MSEC_DEFAULT = 10000

CONNECTION_FAILURES = ["EHOSTUNREACH",
                       "Could not resolve host",
                       "No route to host",
                       "Connection refused",
                       "Authentication failed for user",
                       "ConnectionTimeout"]


def run_cmd(cmd):
    LOG.debug('Executing cmd --> %s' % cmd)
    pipes = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, shell=True)
    r_stdout, r_stderr = pipes.communicate()
    rc = pipes.returncode
    r_stdout = r_stdout.strip()
    r_stderr = r_stderr.strip()
    LOG.debug("cmd results: rc = %s\n\tstdout -->%s\n\tstderr -->%s"
              % (rc, logger.fmt_output(r_stdout), logger.fmt_output(r_stderr)))
    return (rc, r_stdout, r_stderr)


def retryable_cmd(cmd, retry_if_contains=None, attempts=None, wait=None):
    # TODO(jecarey): should it separate contains check and should it add rc?
    if not retry_if_contains:
        retry_if_contains = CONNECTION_FAILURES

    if not attempts:
        attempts = int(config.get_option(
                       CFG_COMMANDS_SECTION,
                       CFG_COMMANDS_RETRY_ATTEMPTS,
                       CFG_COMMANDS_RETRY_ATTEMPTS_DEFAULT))
    if not wait:
        wait = int(config.get_option(
                       CFG_COMMANDS_SECTION,
                       CFG_COMMANDS_RETRY_WAIT_MSEC,
                       CFG_COMMANDS_RETRY_WAIT_MSEC_DEFAULT))

    def _retry_on_error(result):
        _, r_stdout, r_stderr = result
        output = r_stdout + '\n' + r_stderr
        found = any(phrase in output
                    for phrase in retry_if_contains)
        if found:
            LOG.debug('+++ Retrying command')
        return found

    @retry(retry_on_result=_retry_on_error,
           stop_max_attempt_number=attempts,
           wait_fixed=wait)
    def _try_command(cmd):
        return run_cmd(cmd)

    return _try_command(cmd)


def get_failures(raw_output, ignore_regex_list=None, fail_regex_list=None):
    failing_lines = []
    for line in raw_output.split('\n'):
        if ignore_regex_list and any(re.search(ignore_regex, line)
                                     for ignore_regex in ignore_regex_list):
            continue
        if fail_regex_list and any(re.search(fail_regex, line)
                                   for fail_regex in fail_regex_list):
            failing_lines.append(line)
    return failing_lines
