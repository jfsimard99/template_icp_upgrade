# Copyright IBM Corp. 2017, 2018
#
# Script to destroy AWS VMs created by TravisCI build engine during continuos builds
require 'aws-sdk'

# How old (in seconds) are VMs expected to be before killing them
MAX_OLD = 10_800
TERMINATED = 48

def terminate_old(i)
  # p i.id
  # p i.state.name
  # p i.state.code
  # p i.instance_type
  # p i.launch_time.utc
  return if i.state.code == TERMINATED # skip instances already terminated
  return if i.launch_time.utc > (Time.now - MAX_OLD).utc # Only process instances older then MAX_OLD seconds
  p "Killing instance #{i.id} launched at: #{i.launch_time.utc}"
  i.terminate
end

# If AWS env variables are not set we will gracefully end the script
%w{AWS_ACCESS_KEY_ID AWS_ACCESS_KEY_SECRET}.each do |env|
    unless ENV.key?(env)
        p "Expecting #{env} to be set"
        exit 0
    end
end

# ec2 = Aws::EC2::Resource.new(region: 'us-east-1')
ec2 = Aws::EC2::Resource.new

# Delete the test-kitchen VMs (spun up from cookbook testing)
ec2.instances(filters: [{ name: 'tag:created-by', values: ['test-kitchen'] }]).each do |i|
      terminate_old(i)
end

# Delete the CAMContent VMs (spun up from template testing)
ec2.instances(filters: [{ name: 'tag:Name', values: ['camcontent-*'] }]).each do |i|
  terminate_old(i)
end
