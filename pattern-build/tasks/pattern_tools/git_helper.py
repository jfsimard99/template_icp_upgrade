# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================
import atexit
import os
import re
import shutil
import tempfile

from utils import cmd_utils
from utils import exceptions
from utils import http_utils
from utils import logger


LOG = logger.get_logger(__name__)


class LocalDir(object):
    """Use a local directory instead of a git repo
    In order to allow for testing or use of a directory
    instead of an actual git repo, provide support for
    the methods needed to create, update, and get the
    file locations.
    """

    def __init__(self, local_dir):
        LOG.debug('Instead of a git repo, using local directory %s' %
                  local_dir)
        self.local_dir = local_dir

    def force_update(self):
        pass

    def update(self):
        LOG.debug('updating temp metadata - using files so nothing to update')
        return False

    def get_file_path(self, file_name):
        return os.path.join(os.sep, self.local_dir, file_name)


class LocalGitClone(object):
    """Use a git repo to get at files
    This class allows creation of a local clone,
    updating that clone, and retrieval of file locations
    in the local clone.
    """

    def __init__(self, repo_url, ssh_key_file=None, branch=None,
                 repo_base_dir=None):
        self.local_repo_name = repo_url.rpartition('/')[-1].rpartition('.')[0]
        LOG.debug('Using git repo %s' % self.local_repo_name)
        self.branch = branch
        self.repo_url = repo_url
        self.ssh_key_file = ssh_key_file
        if not repo_base_dir:
            repo_base_dir = tempfile.mkdtemp()
        self.clone_dir = os.path.join(os.sep, repo_base_dir,
                                      self.local_repo_name)
        if os.path.isdir(self.clone_dir):
            LOG.debug('Removing Directory %s' % self.clone_dir)
            shutil.rmtree(self.clone_dir)
       
        self._create_clone()
        atexit.register(self._cleanup)

    def _cleanup(self):
        try:
            if (self.repo_base_dir and os.path.exists(self.clone_dir)):
                shutil.rmtree(self.clone_dir, ignore_errors=True)
        except Exception:
            LOG.exception('Should not happen - '
                          'failed to clean up clone directory')
            pass

    def _create_clone(self):
        try:
            if self.ssh_key_file:
                key_info = 'ssh-add %s; ' % self.ssh_key_file
            else:
                key_info = ''
            if self.branch:
                branch_info = ' -b %s' % self.branch
            else:
                branch_info = ''
            check_cmd = (("ssh-agent bash -c '%s"
                          "git ls-remote %s'") %
                         (key_info, self.repo_url))
            _, r_stdout, r_stderr = cmd_utils.run_cmd(check_cmd)
            check_result = r_stdout + r_stderr
            if 'Repository not found' in check_result:
                raise exceptions.BadParameterException(
                    'Repository %s not found' % self.local_repo_name,
                    data_json={'output': check_result})

            clone_cmd = (("ssh-agent bash -c '%s"
                          "git clone%s --depth 1 %s %s'") %
                         (key_info, branch_info,
                          self.repo_url, self.clone_dir))
            cmd_utils.retryable_cmd(
                clone_cmd,
                ['Host key verification failed'],
                attempts=5, wait=10)
        except exceptions.MicroserviceException:
            raise
        except Exception:
            LOG.exception('Unable to clone repo %s -- aborting' %
                          self.local_repo_name)
            self._cleanup()
            raise
        LOG.debug('Cloned %s into %s' % (self.local_repo_name, self.clone_dir))

    def force_update(self):
        self._cleanup()
        self._create_clone()

    def update(self):
        LOG.debug('Updating temp metadata')
        if not os.path.exists(self.clone_dir):
            LOG.debug('target directory did not exist')
            self._create_clone()
            return True
        try:
            update_cmd = ("ssh-agent bash -c 'ssh-add %s; cd %s; "
                          "git remote update'" %
                          (self.ssh_key_file, self.clone_dir))
            _, r_stdout, r_stderr = cmd_utils.run_cmd(update_cmd)
            update_result = r_stdout + r_stderr
            update_result = update_result.rstrip()
            if update_result.endswith('Fetching origin'):
                LOG.debug('git remote update reported no changes')
                return False
            LOG.debug('Rebasing repository')
            rebase_cmd = ("ssh-agent bash -c 'ssh-add %s; cd %s; "
                          "git pull --rebase'" %
                          (self.ssh_key_file, self.clone_dir))
            cmd_utils.run_cmd(rebase_cmd)
        except Exception:
            LOG.exception("Unable to rebase repo -- aborting")
            raise
        LOG.debug('repository in %s is up to date' % self.clone_dir)
        return True

    def get_file_path(self, file_name):
        return os.path.join(os.sep, self.clone_dir, file_name)


GIT_REPO_URL_TEMPLATE = {'github.ibm.com': 'https://%s/api/v3/orgs/%s/repos?per_page=1000',
                         'github.com': 'https://api.%s/orgs/%s/repos?per_page=1000'}
GIT_REPO_URL_TEMPLATE_DEFAULT = 'https://api.%s/orgs/%s/repos?per_page=1000'


def get_repos(github_name, org, repo_regex, auth_key):
    req_header = {"Authorization": "token %s" %
                  auth_key}

    tmplt = GIT_REPO_URL_TEMPLATE.get(github_name,
                                      GIT_REPO_URL_TEMPLATE_DEFAULT)
    req_url = tmplt % (github_name, org)
    LOG.debug('http url: %s ' % req_url)
    status, data = http_utils.call_http('GET', req_url, req_header)
    if status != "200":
        raise exceptions.ExecutionException(
            "Unable to retrieve git repos",
            data_json={"status": status})

    try:
        repo_regex_c = re.compile(repo_regex)
    except Exception as e:
        LOG.exception('repo regex compilation failed')
        raise exceptions.BadParameterException(
            "repo regex was incorrectly specified",
            data_json={'traceback': str(e)})

    repo_clone_urls = []
    for repo_info in data:
        if repo_regex_c.match(repo_info['name']):
            repo_clone_urls.append(repo_info['clone_url'])
    return repo_clone_urls


def clone_repos(repo_list, auth, repo_dir, branch):
    result = dict()
    for repo in repo_list:
        git_access_url = ("https://%s:x-oauth-basic@%s" %
                          (auth, repo.split('//')[1]))
        print 'Downloading - ' + git_access_url + ' to ' + repo_dir
        result[repo] = LocalGitClone(git_access_url, repo_base_dir=repo_dir, branch=branch)
    return result
