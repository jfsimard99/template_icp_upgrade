Copyright IBM Corp. 2017, 2018 

Run TF templates

1. virtualenv ./ tr
2. . ./tr/bin/activate
3. pip install -r requirements.txt
4. ./template_runner.py -t ibmcloud_content_runtime.tf -v ibmcloud_content_runtime.var -e qa -n MCCTest -ibmcloud  mariusccIBMCloud --delete_failed_deployments --autodestroy

More details for params:
```
./template_runner.py
usage: template_runner.py [-h] -t TF_TEMPLATE_FILE -v TF_VARIABLE_FILE -e
                          {dev,qa,prod} -n STACK_NAME [-u BLUEMIX_USERNAME]
                          [-o BLUEMIX_ORG_NAME] [-s BLUEMIX_SPACE_NAME]
                          (-aws AWS_CLOUD_CONNECTION | -ibmcloud IBMCLOUD_CLOUD_CONNECTION)
                          [--delete_failed_deployments] [--autodestroy]
```
