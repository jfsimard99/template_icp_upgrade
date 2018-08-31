# Copyright IBM Corp. 2017, 2018
#
# Script to destroy SL VMs created by TravisCI build engine during continuos builds
require 'softlayer_api'
require 'vine'

# How old (in seconds) are VMs expected to be before killing them
MAX_OLD = 10_800

# If SL env variables are not set we will gracefully end the script
%w{softlayer_username softlayer_api_key}.each do |env|
    unless ENV.key?(env)
        p "Expecting #{env} to be set"
        exit 0
    end
end 

client = SoftLayer::Client.new(
                               :timeout => 120,
                               :username => ENV['softlayer_username'],
                               :api_key => ENV['softlayer_api_key']
)
account_service = client['Account']
mask = 'mask[id,fullyQualifiedDomainName,primaryIpAddress,createDate,tagReferences[tag[name]],billingItem[orderItem[description,order[userRecord[username],id]]]]'

tag_filter = SoftLayer::ObjectFilter.new
tag_filter.set_criteria_for_key_path('virtualGuests.tagReferences.tag.name', 
                                     'operation' => 'in',
                                     'options' => [{ 'name' => 'data', 'value' => ['continuousbuilds', 'travis'] }])
vms_by_tag = account_service.object_mask(mask).object_filter(tag_filter).getVirtualGuests

hostname_filter = SoftLayer::ObjectFilter.new
hostname_filter.set_criteria_for_key_path('virtualGuests.hostname',  
                                          'operation' => '^= travisci')
vms_by_hostname = account_service.object_mask(mask).object_filter(hostname_filter).getVirtualGuests

hostname_filter = SoftLayer::ObjectFilter.new
hostname_filter.set_criteria_for_key_path('virtualGuests.hostname',
                                          'operation' => '^= camcontent')
vms_by_hostname_camc = account_service.object_mask(mask).object_filter(hostname_filter).getVirtualGuests

(vms_by_tag + vms_by_hostname + vms_by_hostname_camc).each do |vm|
    creator = vm.access('billingItem.orderItem.order.userRecord.username')
    next unless creator == ENV['softlayer_username']
    puts "Check if VM with hostname: #{vm.access('fullyQualifiedDomainName')} is older then #{MAX_OLD} seconds"
    # Skip VM if it's newer then 3 hours
    next if Time.parse(vm.access('createDate')).utc > (Time.now - MAX_OLD).utc

    begin
        item = client[:Virtual_Guest].object_mask("mask[billingItem[id]]").object_with_id(vm.access('id')).getObject
    rescue XMLRPC::FaultException
       item = false
    end
    if item && item['billingItem']
      begin client[:Billing_Item].object_with_id(item['billingItem']['id']).cancelService
            puts "Destroying VM with id: #{vm.access('id')} and hostname: #{vm.access('fullyQualifiedDomainName')}"
      rescue
            puts "ERROR: VM with id: #{vm.access('id')} and hostname: #{vm.access('fullyQualifiedDomainName')} cancellation could not be processed. Please contact support." 
      end
    else
       puts "VM already destroyed id: #{vm.access('id')} and hostname: #{vm.access('fullyQualifiedDomainName')}"
    end
end
