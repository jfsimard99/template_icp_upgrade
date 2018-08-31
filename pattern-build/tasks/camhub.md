Table of Contents
=================

* [camhub rake tasks](#camhub-rake-tasks)
   * [publish task](#publish-task)
      * [Overview](#overview)
      * [Usage](#usage)
         * [.camhub.yml Example](#camhubyml-example)
      * [Architecture &amp; Design](#architecture--design)
      * [Example output](#example-output)
   * [verify_tag](#verify_tag)
      * [Overview](#overview-1)
      * [Usage](#usage-1)
      * [Architecture &amp; Design](#architecture--design-1)
      * [Example output](#example-output-1)
   * [env_cookbook_sync](#env_cookbook_sync)
      * [Overview](#overview-2)
      * [Usage](#usage-2)
      * [Architecture &amp; Design](#architecture--design-2)
      * [Example output](#example-output-2)

# `camhub` rake tasks

Documenation for the rake build tasks provided in the `camhub` namespace.  See `.camhub.rake` for the code.

## `publish` task

### Overview
`camhub:publish` rake task will publish the current git repository into the remote CAMHub organization on a GitHub server (either github.com, or IBM Whitewater GHE).  For more information on CAMHub, see the [design document](https://github.ibm.com/Orpheus/Roadmap-Automation-Content/wiki/IBM-Marketplace-Integration-&-CAM-HUB).

The intended use case is that content developed within IBM's GitHub Enterprise (GHE), after being fully tested, is published to the external CAMHub github organization for usage by end customers.

Normal developers are not expected to run this task manually, aside from testing against their own personal GitHub organizations.  **The intention is that this task is only ever executed by build automation (ex: TravisCI, Jenkins).  Developers should never push to the 'official' CAMHub directly.**

### Usage

1. The git repository being built must have the `.camhub.yml` configuration file, in the root directory.  The file controls the CAMHub publishing process.  See the example of the configuration file below.
1. Environment variables that must be set.  These settings should be secured by the build server.
  * `<camhub_server_hostname>_ACCESS_TOKEN` -- The security [access token](https://github.com/settings/tokens) for the user account publishing to CAMHub. **Note**: the CAMHub/GitHub server hostname is defined in the `.camhub.yml` configuration in the repository, in the `cam_hub` section of the configuration file.  Examples:
    * `GITHUB_IBM_COM_ACCESS_TOKEN` -- when testing against IBM GHE
    * `GITHUB_COM_ACCESS_TOKEN` -- against the official CAMHub hosted on github.com
1. Add a hook to the build process to initiate the `camhub:publish` rake task after all tests have successfully been done.  **Note:** The publishing should be done at merge time, into the branches defined in the `.camhub.yml` file: for example, the `development`, `test` and `master` branches.
  * Using TravisCI:

  ```yaml
  after_success:
    - if [[ "$TRAVIS_PULL_REQUEST" = "false" ]] && [[ ( "$TRAVIS_BRANCH" = "development" )  || ( "$TRAVIS_BRANCH" = "test" ) || ( "$TRAVIS_BRANCH" = "master" ) ]];
       then ./tasks/camhub_publish.sh;
      fi

  ```
  **Note**: TravisCI's `after_success` block runs only if the earlier build steps completed successfully.  Major drawbacks to using TravisCI, and reasons to move to Jenkis:
      1. the publishing step is not be run independently of any other build/testing steps.
      1. If the TravisCI `after_success` block fails: the build is still considered *successful* by Travis.


#### `.camhub.yml` Example

```yaml
# Configuration file for CAMHub publishing
# @see: https://github.ibm.com/OpenContent/pattern-build/blob/development/tasks/camhub.md

# The CAMHub/GitHub server & organization details (per branch)
cam_hub:
  development: # publishing target for the `development` branch
    hostname: github.ibm.com   # CAMHub/GitHub hostname
    org_name: CAMHub-Development    # CAMHub organization name

  test: # publishing target for the `test` branch
    hostname: github.ibm.com   # CAMHub/GitHub hostname
    org_name: CAMHub-Test    # CAMHub organization name

DISABLED In the builds, we are switching the publish to master thru another mechanism...
  master: # publishing target for the `master` branch
    hostname: github.com   # CAMHub/GitHub hostname
    org_name: IBM-CAMHub    # CAMHub organization name

# repo_options:
#   Repository options when creating the CAMHub git repo
#   see: https://developer.github.com/v3/repos/#create
# All keys must be Ruby Symbols (start with ':')
repo_options:
  :private: true         # Should be a private reopsitory?
  :has_issues: false     # Enable GitHub Issues on the repo?
  :has_wiki: false       # Enable GitHub Wikis on the repo?
  :has_downloads: false  # Enable GitHub Downloads on the repo?
  :auto_init: true       # Automatically initialize the repo? Should stay 'true'

# git_tag:
#   Specifies how the git tag should be calculated
#   If this is not specified, then pushes to CAMHub will NOT be tagged!!
git_tag:
  # ruby_eval: Ruby snippet that is `eval()` to calculate the semver number
  # Examples:
  #  ruby_eval: "'0.0.1'"  # fixed version number (must be changed on each push)

  # For cookbooks, use the semver from the cookbook's `metadata.rb` file
  ruby_eval: "`find . -name 'metadata.rb' -type f | xargs grep ^version | awk -F \"'\" '{print $2}'`"

  # Enforce semantic versioning naming scheme
  # Default is true
  # @see: http://semver.org/
  enforce_semver: true

# excludes:
#   Prevent pushing files from the source repository into CAMHub.  Used to
#   keep test-cases and other internal files from being published externally.

#   Each item in the list results in a `tar --exclude=<pattern>`
#   See: http://www.hep.by/gnu/tar/exclude.html#SEC108
excludes:
  - "*/.kitchen/*"
  - .kitchen*.yml
  - Berksfile*
  - "*/test/*"
  - "*/spec/*"
  - resources/*
  - doc/*
  - chefignore
  - travis_wait*.log

```

### Architecture & Design

Operations that `camhub:publish` performs:

  1. Loads and parses the `.camhub.yml` configuration file for the repository
  1. Verifies that the current branch is defined in `.camhub.yml`, to designate which CAMHub/GitHub organization to publish to.  If the branch is not defined in `.camhyub.yml` the publish operation will fail immediately.
  1. Optionally calculates the git-tag (version) for the commit/push to CAMHub.  The `git_tag` settings in `.camhub.yml` define how the git-tag value is computed.  If the section is not defined in `.camhyub.yml` then the publish operation will not include a git tag.
  1. Connects to CAMHub and verifies the existence of the remote repository.  If the repository does not exist in CAMHub, the remote repository is created & initialied based on the `repo_options` settings defined in `.camhub.yml`.
  1. Creates a temporary staging directory, clones the CAMHub repository locally into that directory.  Within the directory:
    * Deletes the contents of the staging directory, leaving only the `.git` directory.  The purpose is to ensure file deletions / renames and similar operations are reflected in the target repository correctly.
    * Copies the source's `.gitignore` file into the staging directory
    * Modifies the `.gitignore` file and adds entries related to the build process itself: `.gitignore`, `.travis.yml`, and the `.camhub.yml` files: These files should not be pushed to CAMHub for any repository.
    * Leveraging the `excludes` settings from `.camhub.yml`, runs a TAR/UNTAR operation to copy files from the source/build directory into the staging directory.  This is especially useful to strip out content from the source repository that should not be published into CAMHub:
      * Test cases
      * Internal documentation & build related information
      * Any automatically created content from running integration tests or other remnants from the build process itself
  1. Runs GIT **Commit / Tag / Push** commands in the staged repository to pushlish the build into CAMHub.
    * **Note**: failues such as 'tag already exists' should NEVER be forced.  Instead fix the source repository in GHE and then rerun the `camhub:publish` task against the new codebase.

### Example output

```
2017-03-24 23:24:11 UTC: CAMHub:publish starting.
2017-03-24 23:24:11 UTC: Evaluating for git-tag: `find . -name 'metadata.rb' -type f | xargs grep ^version | awk -F "'" '{print $2}'`
2017-03-24 23:24:11 UTC: Publishing repository CAMHub-Test/dummy_reference_pattern_rake with tag: 0.1.1 to CAMHub at github.ibm.com...
2017-03-24 23:24:11 UTC: Logging into github.ibm.com...
2017-03-24 23:24:12 UTC: Logged in as: octravis
2017-03-24 23:24:12 UTC: Checking existing repo in CAMHub...
2017-03-24 23:24:12 UTC: Repo does not exist CAMHub-Test/dummy_reference_pattern_rake, creating with options: {:private=>true, :has_issues=>false, :has_wiki=>false, :has_downloads=>false, :auto_init=>true, :organization=>"CAMHub-Test"}...
2017-03-24 23:24:13 UTC: New CAMHub-Test/dummy_reference_pattern_rake repository created.
2017-03-24 23:24:13 UTC: Fetching repository details...
2017-03-24 23:24:13 UTC: Cloning repo CAMHub-Test/dummy_reference_pattern_rake locally to /tmp/dummy_reference_pattern_rake20170324-3686-dulqyb...
Cloning into '/tmp/dummy_reference_pattern_rake20170324-3686-dulqyb'...
remote: Counting objects: 3, done.
remote: Total 3 (delta 0), reused 0 (delta 0), pack-reused 0
Unpacking objects: 100% (3/3), done.
Checking connectivity... done.
2017-03-24 23:24:14 UTC: Cloned.  Validating...
Checking object directories: 100% (256/256), done.
2017-03-24 23:24:14 UTC: Verified.  Compacting...
Counting objects: 3, done.
Writing objects: 100% (3/3), done.
Total 3 (delta 0), reused 0 (delta 0)
2017-03-24 23:24:14 UTC: Compacted.
2017-03-24 23:24:14 UTC: Committing changes as user 'CAMHub PublishBot'...
2017-03-24 23:24:14 UTC: Pushing updates to CAMHub...
2017-03-24 23:24:22 UTC: CAMHub:publish done.
```

## `verify_tag`

### Overview
Rake task that verifies that the feature branch's git_tag resolves to a different value than the `development` branch resolves to.

Intended use case is to execute this task during the build step, tp ensure the build fails before reaching the CAMHub publishing step.

### Usage
`$ rake camhub:verify_tag`
### Architecture & Design
Operations that `camhub:verify_tag` performs:

  1. If there is no `.camhub.yml`, there is nothing to verify (success).  Publishing to CAMHub will not be performed regardless.
  1. If the current branch is either `development`, `test`, or `master` there is nothing to verify (success)
  1. Otherwise (we running in a feature branch), the current `.camhub.yml`'s `git_tag` block is evaluated to determine what the current feature branch's version resolves to.  The value is then compared to the `development` branch.
    * If the `git_tag` is `nil`: SUCCESS
    * If the values are different: SUCCESS
    * If the values are the same: FAIL build

### Example output
Successful execution:
  ```
  $ rake camhub:verify_tag
  $
  ```

Failure execution:

  ```
  $ rake camhub:verify_tag
  2017-04-13 22:07:05 UTC: Evaluating for git-tag: '0.0.1'
  2017-04-13 22:07:05 UTC: Evaluating for git-tag: '0.0.1'
  2017-04-13 22:07:05 UTC: !!!CAMHub options for `git_tag` results in same value (0.0.1) as in the `development` branch.  Ensure that the version number for your feature branch (123) is different.
  rake aborted!
  !!!CAMHub options for `git_tag` results in same value (0.0.1) as in the `development` branch.  Ensure that the version number for your feature branch (123) is different.
  /home/bgehman/git/Enterprise_Middleware/tasks/camhub.rake:274:in `block (2 levels) in <top (required)>'
  Tasks: TOP => camhub:verify_tag
  (See full trace by running task with --trace)

  $ echo $?
  1
  $
```

## `env_cookbook_sync`

### Overview

Synchronizes the various internal dev/test environments to the cookbooks published in CAMHub. **Note**: this rake task is intended to be executed by TravisCI build processes after a cookbook update has been published to CAMHub.

Current environments, see: [environs.yml](https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/labs/environs.yml) for the official list.

| branch | CAMHub host | CAMHub Org | pattern-manager host | PM public IP | PM private IP |
| ---- | ---- | ---- | ---- | ---- | ---- |
| development | github.ibm.com | CAMHub-Development | sl-DEVENV-01 | 169.44.68.154 | 10.155.99.23 |
| development | github.ibm.com | CAMHub-Development | aws-DEVENV-01 | 52.207.229.177 | n/a |
| test | github.ibm.com |CAMHub-Test | sl-TESTENV-01 | 169.53.243.182 | 10.98.30.224 |
| test | github.ibm.com |CAMHub-Test | aws-TESTENV-01 | 54.146.47.38 | n/a |
| master | github.com |IBM-CAMHub | sl-DEMOENV-01 | 169.53.243.171 | 10.98.30.221 |
| master | github.com |IBM-CAMHub | aws-DEMOENV-01 | 54.91.243.199 | n/a |

Example environs.yml:

```yaml
development:
  SL-DEVENV-01:
      ip_addr: 169.44.68.154
  AWS-DEVENV-01:
      ip_addr: 52.207.229.177

test:
  SL-TESTENV-01:
      ip_addr: 169.53.243.182
  AWS-TESTENV-01:
      ip_addr: 54.146.47.38

master:
  SL-DEMOENV-01:
      ip_addr: 169.53.243.171
  AWS-DEMOENV-01:
      ip_addr: 54.91.243.199
```

### Usage

Requires `<camhub_server_hostname>_ACCESS_TOKEN` environment variable set for pattern-manager authentication to CAMHub.

`$ rake camhub:env_cookbook_sync`

**Note:** Command is not intended to be run manually, but instead via TravisCI processes.

### Architecture & Design

The task performs the following actions:
  1. Loads and parses the `.camhub.yml` (included in the root directory of the git-repo)
  1. pulls the CAMHub hostname & organization name from the `.camhub.yml` for the branch being built.
  1. loads the `environs.yml` config file from pattern-build repository, see: [environs.yml](https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/labs/environs.yml)
  1. depending on the branch published to CAMHub, a lookup is made into `environs.yml` for the mapping of all environments that should be refreshed.
  1. Invokes calls to all Pattern-Manager microservices registered for the branch, to syncrhonize the chef-server in those environments to the environment-specific CAMHub

### Example output

```
** Invoke camhub:env_cookbook_sync (first_time)
** Execute camhub:env_cookbook_sync
2017-04-26 14:14:11 UTC: Sync'ing development environment cam-DEVENV-01 ...
2017-04-26 14:14:11 UTC: Invoking pattern-manager API at 169.44.68.154, to sync with CAMHub-Development at github.ibm.com...
2017-04-26 14:14:31 UTC: Success 200 {
  "output": "Uploading db2            [0.1.12]\nUploading ibm_cloud_utils [0.1.14]\nUploading ihs            [0.1.12]\nUploading im             [0.1.9]\nUploading linux          [0.1.12]\nUploading wasnd          [0.1.4]\nUploading wmq            [0.1.10]\nUploaded all cookbooks.No roles specified (or no_roles.json) in /tmp/tmpuaEPcb/cookbook_ibm_im_multios/chef/roles/"
}
```
