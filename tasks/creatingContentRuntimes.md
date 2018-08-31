# Creating Content Runtime and Cloud Connections

This document outlines how you can create CAM Cloud Connections and Creating Content Runtime(s) using RAKE orpheus.rake file. 

## Requirements

- Access to https://github.ibm.com/OpenContent/advanced_content_runtime_chef
- Access to https://github.ibm.com/OpenContent/pattern-build
- Access to https://github.ibm.com/OpenContent/toolshed
- Access to the docker "devops-pipeline-image". It is recommended to use this docker image as this has the necessary software installed (i.e., chef, ruby gems and python modules).  
- IP Address for VMWare based deployments

If you need to pull the latest CAMC Docker Images from artifactory and/or Cookbooks from GITHUB.IBM.COM you will need these as well. 
- (optional) Docker Token for artifactory (https://github.ibm.com/OpenContent/infra-docker-compose/tree/development/terraform/cam#docker-login-token)
- (optional)Git Token for Content Hub

Environment Variables that will need to be set in the container

DOCKER_REGISTRY_USER=  "artifactory userid"  <br>
DOCKER_REGISTRY_PASS=  "" your artifactroy token" <br>
ARCHIVE_PASSWORD= ""password for the .gpg files".  See insert link here
TEMPLATE_TRANSLATION=True  <<used to process the override variables json file>>

## Download the Docker Image

`
docker login orpheus-local-docker.artifactory.swg-devops.com
`
```
Username (xxxx@us.ibm.com): 
Password: 
Login Succeeded
```

`
docker pull orpheus-local-docker.artifactory.swg-devops.com/opencontent/devops-pipeline-image:latest`
```
.....
.....
bbb9b15a3d84: Pull complete
d97498b4acd3: Pull complete
Digest: sha256:4916cd14807eeeb916b59593f83411c18e0816be2d970a5aa9df6d55502927d4
Status: Downloaded newer image for 
orpheus-local-docker.artifactory.swg-devops.com/opencontent/devops-pipeline-image:latest
```

## Working with the container

Determine the Image ID for orpheus-local-docker.artifactory.swg-devops.com/opencontent/devops-pipeline-image:latest.  From the command prompt, run `docker images` and find the Image ID. 

Before running `docker run`, determine how you are going to copy the repository files to the docker image.  You can either use the -v option or use the docker cp commands. 

Start the container 

`docker run` -d <docker_image_id>  -v [host directory path]:[container directory path]

example: ```docker run -d  -v /home/user/tempfiles:/src/app <docker_image_id>```

This playbook assumes that the -v option will be used. 

Download the required repositories to the host computer
- cd to [host directory path]
- git clone git@github.ibm.com:OpenContent/advanced_content_runtime_chef
- cd advanced_content_runtime_chef
- git clone git@github.ibm.com:OpenContent/pattern-build
- cp -r ./pattern-build/* .
- cp -r ./pattern-build/.rubocop.yml .

Access the container
- docker exec -it <container_id> /bin/bash
- cd /src/app/advanced_content_runtime_chef
- cd tasks/
- rake -T to verify that you see all of the rake commands. 

## Create the Cloud Connections

The cloud connections are determined by the artificatory loud_connections.zip.gpg that is in artifactory. 
2/18/2018: There will be five cloud connections. 

`rake orpheus:create_cloud_connections[cam_url]`  where URL is the IP Address of CAM. 
example:   `rake orpheus:create_cloud_connections[9.5.39.84]`

## Creating the Content Runtime

You can create any combination of the IBM, AWS or VMWare public runtimes.  The CAMC templates that are currently not supported (Other and BYOC Cloud templates)  

- Download the override_variables.json file from artifactory: 
  https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/environment_setup/content_runtimes.zip.gpg. 
 - Run gpg content_runtimes.zip.gpg and enter in the gpg password that is located in the box note. 
 - unzip the .zip file. 
 - Copy the approppriate *override_variables.json* to the corresponding advanced_content_runtime_chef/content_runtime_template/<cloud>/public>/override_variables.json directory.  These files are defaulted to the appropriate values that are used by the CAM Content team
 - Edit the override_variables.json file.  Key value pairs that you need to update: 
    - runtime_hostname.  This should be unique.
 - Save the file. 
 - If you want to create all three content runtimes, skip to the rake command below. Otherwise do the following:
   - Edit the advanced_content_runtime_chef/tasks/orpheus.rake file
   - Uncomment lines (332 - 334) and alter this code to only include the cloud providers you want to create. 
``` 
       if cloud_type != "aws"
         return
       end
```
   - Export the following variables
```
    export ARCHIVE_PASSWORD=
    export DOCKER_REGISTRY_USER=<artifactory userid>
    export DOCKER_REGISTRY_PASS=>artifactory token> 
    export TEMPLATE_TRANSLATION=TRUE
    export GIT_TOKEN=<your git token> 
```
   - Execute the `rake orpheus:create_content_runtimes[camurl]` where camurl is the IP address of CAM. 

## Update developoment drivers with the latest level of code

Once the CAMC runtime is up and running, you may decide that you want to pull down the latest PM, SWRep containers and get the latest cookbooks.  To do this you will need to execute the updateToLatestDevelopment.sh script.   This script can be found here: https://github.ibm.com/OpenContent/toolshed/tree/master/makeDevelopment along with instructions on how to run the command.  
- The `docker_register_token` is the artifactory docker token. See (https://github.ibm.com/OpenContent/infra-docker-compose/tree/development/terraform/cam#docker-login-token) for details on how to create it. 
- The `ibm_contenthub_git_access_token` is your GITHUB.IBM.COM token. 

Another option if needed is that you can update the override file to contain the 
following information: 
"docker_registry_token":"<your artifactory login token>",
  "docker_registry":"orpheus-local-docker.artifactory.swg-devops.com",
  "docker_registry_camc_pattern_manager_version":"<build you want",
  "docker_registry_camc_sw_repo_version":"build you want"

## Updating the swRepo to point to the NFS mounts. 

After you have created the content runtime(s), you need to setup the software 
repository with the binary files.  To make things easier for ourselves, we 
have three fileservers setup in each of the clouds. 

See https://github.ibm.com/OpenContent/toolshed/tree/master/setupCAMEnvironment for 
instructions on how to configure the software repository NFS mounts. 


 ## Updating Pipeline Files

When creating the pipeline, use the above instructions to create the cloud connections
and content runtimes and setup the software repository.  

The following files need to be updated for the pipeline to work properly. 

 - pattern-build/tasks/template_runner_local/testing_variables.json
    - update `"test_data": {
	    "cam_instance": "9.37.194.118",
            "content_runtime": {
                "vsphere": "5a8dee133bbd60001e727118",
                "ibm": "5a9c22a13bbd60001e727187",
                "aws": "5a90478e3bbd60001e727126"
            },` with the appropriate UUID of the CAMC runtime. 
 - pattern-build/tasks/template_runner_local//lib/iaas.py
    - update section of code that specifies the instance ids.  
    ```# 1891 - Get connection varibales from the translation file
            if translation_variables:
                instance_ids = [translation_variables['test_data']['content_runtime'][self.cloud_connection_type]]
            else:
                if 'aws' in cloud_connection['name']: #camc-aws-octravis
                    instance_ids = ['5a90478e3bbd60001e727126']    
                    print "AWS Advanced Content runtime selected"
                elif 'vmware' in cloud_connection['name']: #  camc-vmware-octravis
                    instance_ids = ['5a8dee133bbd60001e727118']  #
                    print "VMware Advanced Content runtime selected"
                elif 'ibm' in cloud_connection['name']:#  camc-ibm-octravis
                    instance_ids = ['5a9c22a13bbd60001e727187']  #
                    print "IBM Advanced Content runtime selected"
      ```
     - update orpheus.rake and around linkes lines 261, 283 and 292  make sure that the this has the correct CAM URLs for the pipeline.   THis isn't needed for content runtime creation but needed for the template pipeline. 
     ```
     log "cam_url: 9.37.194.115"
          if template_provider == "template_runner_local2"
        template_runner_local2(
          template_filename, camvariable_filename,
          Time.new.strftime("travisci-%Y%m%d-%H%M%S-#{cloud_type}-#{template_filename.split('/')[-1].split('.')[0]}"), # stack name
          'octravis@us.ibm.com', '9.37.194.115', # W3 ID and CAM IP Address
          cloud_type,
          "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
          current_branch_pr.to_s, override_filename, translation_filename
        )
      else
        template_runner_local(
          template_filename, variable_filename, camvariable_filename,
          Time.new.strftime("travisci-%Y%m%d-%H%M%S-#{cloud_type}-#{template_filename.split('/')[-1].split('.')[0]}"), # stack name
          'octravis@us.ibm.com', '9.37.194.115', # W3 ID and CAM IP Address
          cloud_type,
          "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
          current_branch_pr.to_s,
          File.join(environ_dir, "#{branch_name}-#{cloud_type}-secretvars.tf")
        )
      end
     ```       
 - https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/labs/environs.yml.gpg file
    - Update the file to include the new IP address of the CAMC runtime for the appropriate cloud. 
    - You will need to update the file back to artifactory for the pipeline to work properly. 
    - gpg -c environs.yml and enter in the passphrase

  - https://orpheus-local-docker.artifactory.swg-devops.com/artifactory/orpheus-local-generic/opencontent/labs/build_env_vars.gpg.   
    - Update the appropriate IM_REPO and SWREPO fields for each of the clouds that are being updated.
    - You will need to update the file back to artifactory for the pipeline to work properly. 
    - gpg -c build_env-vars  and enter in the passphrase   
  
VMWare
```
    export VMW_SW_REPO_ROOT="https://9.42.134.181:9999"
    export VMW_IM_REPO="https://9.42.134.181:9999/IMRepo"
```

AWS Settings
```

export AWS_SW_REPO_ROOT="https://34.227.98.246:9999"
export AWS_IM_REPO="https://34.227.98.246:9999/IMRepo"
```

IBM Cloud
```
export SL_SW_REPO_ROOT="https://169.55.14.5:9999"
export SL_IM_REPO="https://169.55.14.5:9999/IMRepo"
```

## Update cookbooks if needed
By default the cookbooks that get loaded are based on github.com so if you want a different set of cookbooks loaded you will need to do this.  For the pipeline, we 
will always pull the cookbooks from 
```
{
  "authorization": {
    "personal_access_token": "xxxxxxxxxxxx"
  },
  "source_repos": "github.ibm.com",
  "org": "CAMHub-Open-Development",
  "repos": "cookbook_.*",
  "branch": "2.0"
}
```

For production we get things from here: 
```
{
  "authorization": {
    "personal_access_token": "xxxx"
  },
  "source_repos": "github.com",
  "org": "IBM-CAMHub-Open",
  "repos": "cookbook_.*",
  "branch": "2.0"
}
```




## Updating IBM Cloud and AWS Instances with appropriate tags
On a weekly basis, the Devops team will delete virtual machines that have not been tagged to not be deleted.   If you want the runtimes to last, you will want to add the following: 

IBM Cloud
In the `Configuration Tab` Notes section, add in the following: 
```
   Usage:Infra
   Usage_desc:Chef,Content Team Development
```

In AWS, you will `Tabs` and add in the these two tags: 
```
Key: Usage       Value: Infra
Key Usage_desc   Value: Chef,Content Team Development
```

## Updating testing_variables.json file

This file is used by the template runner and typically, doesn't need to be updated.  You 
can update this section of the code if you want: 
```
	    "cam_instance": "9.37.194.115",
            "content_runtime": {
                "vsphere": "5af4951642a836001e33f2f8",
                "ibm": "5af49e8c42a836001e33f308",
                "aws": "5af49b0642a836001e33f301"
            },
```

However, if the content runtime added new parameters, you will have to update this file so 
that the code that creates the content runtime knows how to handle the new fields.   You will want to add the new variables to the global section.  Search on `encryption_passphrase` for an example of what needs to be added. 


