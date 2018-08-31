# Copyright IBM Corp. 2017, 2018
require './tasks/utils.rb'

def get_hcl_files(path)
  Dir.glob(path + '/**/*.hcl').each do |f|
    yield f
  end
end

def get_tf_files(path)
  Dir.glob(path + '/**/*.tf').each do |f|
    yield f
  end
end

def install_python_deps
  sh "pip install pyhcl --user" # Python HCL parser
  true # return
end

# Hashicorp Configuration Language (HCL)
desc 'Lint all HCL/TF files'
task :hcl_lint do
  count = 0
  path_dir = Dir.pwd
  prereqs_installed = false # track whether we install python preqs yet
  files_to_check = []
  get_hcl_files(path_dir) { |f| files_to_check << f } # all HCL files
  get_tf_files(path_dir) { |f| files_to_check << f } # all TF files
  files_to_check.each do |path|
    next if File.directory?(path)
    next if File.zero?(path)
    install_python_deps unless prereqs_installed
    prereqs_installed = true
    count += 1
    # Run pyhcl parser for the file
    `python -c \"exec(\\\"import hcl\\nwith open('#{path}','r') as fp: obj = hcl.load(fp)\\\")\"`
    next if $CHILD_STATUS == 0
    msg = "Error parsing hcl/tf: #{path}"
    log msg, 31
    raise msg
  end
  if count == 0
    log "No HCL/TF files found"
  elsif count > 0
    log "Linting of " + count.to_s + " hcl/tf files successful"
  end
end
