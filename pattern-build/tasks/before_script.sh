#!/bin/bash
#
# Copyright : IBM Corporation 2016, 2016
#
#set -o errexit ### These were moved because of an error with mongo
#set -o pipefail

# make sure we have curl available
sudo apt-get update -qq
sudo apt-get install -y curl
set -o errexit 
set -o pipefail

# Use a fixed *stable* ChefDK version to avoid surprises
CHEFDK_VERSION="3.0.4"
if [ "${DOCKER_REGISTRY:-}" ] && [ "${DOCKER_REGISTRY_PASS:-}" ]; then
    #Remove any old packages
    rm -rf /tmp/chefdk.deb
    curl  -o /tmp/chefdk.deb -H "X-JFrog-Art-Api:${DOCKER_REGISTRY_PASS}" https://${DOCKER_REGISTRY}/artifactory/orpheus-local-generic/opencontent/chef-dk/chefdk_${CHEFDK_VERSION}-1_amd64.deb 
    sudo dpkg -i /tmp/chefdk.deb
else
    echo "Missing one of more environment variables: DOCKER_REGISTRY, DOCKER_REGISTRY_PASS"
    exit 1
fi

# Diagnose for debugging
if [ "$DEBUG" == "true" ]; then
  export|sort|grep -vi pass;
  gem env;
  chef --version;
  cookstyle --verbose-version;
  foodcritic --version;
  inspec --version;
fi
