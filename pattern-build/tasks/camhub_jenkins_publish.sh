#!/bin/bash
#
# Copyright : IBM Corporation 2017, 2017
#
set -o errexit
set -o pipefail
set -o nounset

if [ "${DOCKER_REGISTRY:-}" ] && [ "${DOCKER_REGISTRY_USER:-}" ] && [ "${DOCKER_REGISTRY_PASS:-}" ] && [ "${ARCHIVE_PASSWORD:-}" ]; then
  rm -f build_env_vars*
  # curl -O -u ${DOCKER_REGISTRY_USER}:${DOCKER_REGISTRY_PASS} https://${DOCKER_REGISTRY}/artifactory/orpheus-local-generic/opencontent/labs/build_env_vars.gpg
  curl -O -H "X-JFrog-Art-Api:${DOCKER_REGISTRY_PASS}" https://${DOCKER_REGISTRY}/artifactory/orpheus-local-generic/opencontent/labs/build_env_vars.gpg
  ls -la
  echo $ARCHIVE_PASSWORD | gpg --passphrase-fd 0 --always-trust --no-tty build_env_vars.gpg 
  . ./build_env_vars
  rm -f build_env_vars*
else
    echo "Missing one of more environment variables: DOCKER_REGISTRY, DOCKER_REGISTRY_USER, DOCKER_REGISTRY_PASS, ARCHIVE_PASSWORD"
    exit 1
fi

echo $PWD

if [[ $PWD == *"cookbook"* ]]; then
  # at the moment, Jenkins workspace isn't including the cookbook name. 
  # cookbook repo (publish to CAMHub & sync dev/test environments)
  # With the move to Jenkins, we will no longer before a sync to the dev/test environments. Instead 
  # will publish on a daily basis the cookbooks to all of the environments. 
  # rake publish_cookbook 
  # rake camhub:publish 
  echo "In the cookbook repo path"
  repo_name=basename `git rev-parse --show-toplevel`
  echo "repo_name is: $repo_name"
else
  # not a cookbook repo -- just publish
  echo "In the not a cookbook repo leg"
  #rake camhub:publish
  repo_name=basename `git rev-parse --show-toplevel`
  echo "repo_name is: $repo_name"
fi
