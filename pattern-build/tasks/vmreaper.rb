# Copyright IBM Corp. 2017, 2018
#
# Script to destroy VMWare VMs created by TravisCI build engine during continuos builds
require 'rbvmomi'

# How old (in seconds) are VMs expected to be before killing them
MAX_OLD = 10_800

# If VMWare env variables are not set we will gracefully end the script
%w{VMW_LOGIN_USER VMW_LOGIN_PASS VMW_LOGIN_VC}.each do |env|
    unless ENV.key?(env)
        puts "Expecting #{env} to be set"
        exit 0
    end
end

deletable_regex = /^(travisci|CAMContent).*/

vim = RbVmomi::VIM.connect(host: ENV['VMW_LOGIN_VC'], user: ENV['VMW_LOGIN_USER'], password: ENV['VMW_LOGIN_PASS'], insecure: true)
dc = vim.serviceInstance.find_datacenter || raise('datacenter not found')

dc.vmFolder.childEntity.grep(RbVmomi::VIM::Folder).find do |x|
  next unless x.name == "Content"
  x.childEntity.grep(RbVmomi::VIM::VirtualMachine).find do |vm|
    name = vm.name

    unless deletable_regex =~ name
      puts "#{name} is not deletable. Skipping."
      next
    end

    puts "#{name} is deletable. Checking age."
    current_time = vim.serviceInstance.CurrentTime
    age = current_time - vm.runtime.bootTime
    if age <= MAX_OLD
      puts "#{name} is not too old (#{age} sec). Skipping."
      next
    end

    puts "#{name} is too old (#{age} sec). Deleting."
    begin
      vm.Destroy_Task.wait_for_completion
    rescue RbVmomi::VIM::InvalidPowerState
      # Can't delete a VM if it's powered on
      vm.PowerOffVM_Task.wait_for_completion
      vm.Destroy_Task.wait_for_completion
    end
  end
end
