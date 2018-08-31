#!/bin/bash
#
# Copyright : IBM Corporation 2017, 2017
#
set -o errexit
set -o pipefail
set -o nounset

if [ "${DOCKER_REGISTRY:-}" ] && [ "${DOCKER_REGISTRY_USER:-}" ] && [ "${DOCKER_REGISTRY_PASS:-}" ] && [ "${ARCHIVE_PASSWORD:-}" ]; then
  rm -f build_env_vars*
  curl -O -u ${DOCKER_REGISTRY_USER}:${DOCKER_REGISTRY_PASS} https://${DOCKER_REGISTRY}/artifactory/orpheus-local-generic/opencontent/labs/build_env_vars.gpg
  echo $ARCHIVE_PASSWORD | gpg --passphrase-fd 0 --always-trust build_env_vars.gpg 
  . ./build_env_vars
  rm -f build_env_vars*
else
    echo "Missing one of more environment variables: DOCKER_REGISTRY, DOCKER_REGISTRY_USER, DOCKER_REGISTRY_PASS, ARCHIVE_PASSWORD"
    exit 1
fi

if [[ $PWD == *"cookbook"* ]]; then
  # cookbook repo (publish to CAMHub & sync dev/test environments)
  rake publish_cookbook 
else
  # not a cookbook repo -- just publish
  rake camhub:publish
fi
