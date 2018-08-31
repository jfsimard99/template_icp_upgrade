# Copyright IBM Corp. 2017, 2018
require './tasks/utils.rb'

namespace :metadata do
  require './tasks/utils.rb'

  # Utility to run the ChefMetaData python script which will
  # generate the metadata.rb file from a cookbook.
  desc 'execute python generateChefMetaData.py to generate metadata.rb file'
  task :chefmeta do
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs
      log "Running python generateChefMetaData.py -d #{cookbook} ..."
      sh "python tasks/pattern_tools/generateChefMetaData.py -d ./chef/cookbooks/#{cookbook}"
    end # end :Dir.foreach()
  end # task :chefmeta


  # internal utility to verify that :chefmeta has been done.  Inteded to be
  # invoked during build process' validation
  task :verify_chefmeta do
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      # verify metadata.rb is correct according to generateChefMetaData
      verify_files_match_after_action(
        ["chef/cookbooks/#{cookbook}/metadata.rb"], # file to check
        "!!! verify_chefmeta failure: Ensure you execute 'rake metadata:chefmeta' "\
          "\nand commit the modified 'metadata.rb' generated from the process "\
          "\ninto your feature branch.") do

        sh "python tasks/pattern_tools/generateChefMetaData.py -d ./chef/cookbooks/#{cookbook}"
      end # verify_files_match_after_action()

    end # end :Dir.foreach()
  end


  # Utility to run the generateMetadata python script which will
  # generate the 3 json metadata files.
  desc 'execute python generateMetadata.py to generate json metadata files'
  task :meta do
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs
      log "Running python generateMetadata.py -d #{cookbook} ..."
      sh "python tasks/pattern_tools/generateMetadata.py -d ./chef/cookbooks/#{cookbook}"
    end # end :Dir.foreach()
  end # task :meta


  # internal utility to verify that :meta has been done.  Inteded to be
  # invoked during build process' validation
  task :verify_meta do
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      # verify recipes.json, attributes.json, and components.json is correct according to generateMetadata
      files_to_check = ["chef/cookbooks/#{cookbook}/recipes.json",
                        "chef/cookbooks/#{cookbook}/attributes.json",
                        "chef/cookbooks/#{cookbook}/components.json"]

      verify_files_match_after_action(
        files_to_check,
        "!!! verify_meta failure: Ensure you execute 'rake metadata:meta' "\
          "\nand commit the modified files (attributes.json, recipes.json, components.json) "\
          "\ngenerated from the process into your feature branch.") do

        # run the tool that generates the JSON metadata files
        sh "python tasks/pattern_tools/generateMetadata.py -d ./chef/cookbooks/#{cookbook}"
      end # verify_files_match_after_action()

    end # end :Dir.foreach()
  end


  # Metadata task to run the validation during build
  desc 'execute python generateMetadata.py to validate metadata'
  task :validate do
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs
      log "Running python validateMetadata.py -d #{cookbook} ..."
      sh "python tasks/pattern_tools/validateMetadata.py -d ./chef/cookbooks/#{cookbook}"
    end # end :Dir.foreach()
  end # task :validate
end # end :metadata
