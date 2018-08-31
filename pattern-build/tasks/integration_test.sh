#!/bin/bash
#
# Copyright : IBM Corporation 2017, 2017
#
# Get script commit id as version
set -o errexit
set -o pipefail

codepath=$(pwd)
version=`cd pattern-build && git log --stat -1 --pretty=format:"%H" tasks/integration_test.sh|head -1|awk '{print $1}'`

# Run SL reaper
slreaper(){
  eval "$(/opt/chefdk/bin/chef shell-init bash)"
  /opt/chefdk/embedded/bin/gem install softlayer_api
  /opt/chefdk/embedded/bin/gem install vine
  ruby ${codepath}/tasks/slreaper.rb
}

awsreaper(){
  eval "$(/opt/chefdk/bin/chef shell-init bash)"
  /opt/chefdk/embedded/bin/gem install aws-sdk
  ruby ${codepath}/tasks/awsreaper.rb
}

vmreaper(){
  eval "$(/opt/chefdk/bin/chef shell-init bash)"
  /opt/chefdk/embedded/bin/gem install rbvmomi
  ruby ${codepath}/tasks/vmreaper.rb
}

# Diagnose kitchen
diagnose(){
  # Diagnose for debugging
  echo "Running integration script version: ${version}"

  if [ "${DEBUG}" == "true" ]; then
    echo 'show databags'
    echo 'show environment'
    export|sort|grep -vi pass;
    gem env;
    gem list;
    chef --version;
    inspec version;
    kitchen diagnose --all;
  fi
}

# Make sure we have all kitchen-drivers before running other kitchen commands
kitchen_setup(){
    sudo apt-get install -y build-essential g++ gcc make
    eval "$(/opt/chefdk/bin/chef shell-init bash)"
    /opt/chefdk/embedded/bin/gem install kitchen-softlayer -v 1.0.0
    /opt/chefdk/embedded/bin/gem install kitchen-ec2
    /opt/chefdk/embedded/bin/gem install chef-provisioning-vsphere
}

# get build variables into  our build env
get_build_env(){
  if [ "${DOCKER_REGISTRY:-}" ] && [ "${DOCKER_REGISTRY_PASS:-}" ]; then
    cd ${HOME}
    rm -f ${HOME}/build_env_vars
    curl -O -H "X-JFrog-Art-Api:${DOCKER_REGISTRY_PASS}" https://${DOCKER_REGISTRY}/artifactory/orpheus-local-generic/opencontent/labs/build_env_vars.gpg
    echo $ARCHIVE_PASSWORD | gpg --passphrase-fd 0 --always-trust build_env_vars.gpg
    . ${HOME}/build_env_vars
  else
    echo "No Artifactory credentials set!"
    exit 11
  fi
}

# Get TravisCI ssh keys from artifactory
get_travis_keys() {
  if [ "${DOCKER_REGISTRY:-}" ] && [ "${DOCKER_REGISTRY_PASS:-}" ]; then
    cd ${HOME}
    sudo apt-get install -y unzip openssh-client
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
    curl -O -H "X-JFrog-Art-Api:${DOCKER_REGISTRY_PASS}" https://${DOCKER_REGISTRY}/artifactory/orpheus-local-generic/opencontent/labs/FRA/travisci_rsa_id.zip
    unzip -qo -P ${ARCHIVE_PASSWORD} travisci_rsa_id.zip -d ~/.ssh
    chmod 600 ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa.pub
    if [ "${DEBUG}" == "true" ]; then
      cat ~/.ssh/id_rsa.pub;
    fi
  else
    echo "No Artifactory credentials set!"
    exit 11
  fi
}

# Check what cloud to use for integration tests (TEST_CLOUD):
# SL - CAM Softlayer
# AWS - CAM AWS
# ALL - force to run for all above
if [ "$TRAVIS_PULL_REQUEST" != "false" ] && [ "$TRAVIS_BRANCH" == "development" ]; then
  # Set up the environment and keys
  get_build_env
  get_travis_keys
  kitchen_setup

  # reap old VMs
  echo "*************************************************************************"
  echo "Reaping old VMs"
  echo "*************************************************************************"
  slreaper
  awsreaper
  vmreaper


  cd ${codepath}
  # Generate random passords for chef-vault tests
  rake integration:passwords
  diagnose

  echo "*************************************************************************"
  echo "Integration testing START"
  echo "*************************************************************************"
  # run kitchen in parallel for several backends
  rake integration:parallel_run
  rc=$?;

  if [ ${rc} -ne 0 ]; then
    # create an error file and exit clean
    # travis will watch for that error file to mark the build as broken
    echo "*************************************************************************"
    echo "Integration testing FAILED"
    echo "*************************************************************************"
    touch /tmp/ocbuilderror
    exit 0
  else
    echo "*************************************************************************"
    echo "Integration testing SUCCESS"
    echo "*************************************************************************"
  fi
fi
