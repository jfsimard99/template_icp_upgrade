# Copyright IBM Corp. 2017, 2018
require './tasks/utils.rb'

namespace :version do

  require 'English' # For Rubocop $CHILD_STATUS whining
  require './tasks/utils.rb'

  # Utility intended for developers to run locally to increment patch
  # version in metadata.rb
  desc 'increment patch version (third position in version no.) in metadata.rb'
  task :increment do
    # Find all the cookbooks, and increment version
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      puts "\nIncrement patch version for: #{cookbook}..."
      Dir.chdir("chef/cookbooks/#{cookbook}") do
        # raise error if metadata.rb is missing
        raise "Error: missing metadata.rb for cookbook '#{cookbook}'"\
            unless File.file?('metadata.rb')

        require 'chef/util/file_edit'
        require 'chef/cookbook/metadata'

        metadata = Chef::Cookbook::Metadata.new
        metadata.from_file('metadata.rb')
        p "Old version: #{metadata.version}"
        old_v = metadata.version.split('.')
        new_v = "#{old_v[0]}.#{old_v[1]}.#{old_v[2].to_i+1}"
        p "New version: #{new_v}"
        file = Chef::Util::FileEdit.new('metadata.rb')
        file.search_file_replace_line(/^version/, "version '#{new_v}'")
        file.write_file
        # We remove backups to avoid being checked into git
        File.delete('metadata.rb.old')
      end
    end
  end


  # parses the 'version' tag from a metadata.rb and return the value
  def cookbook_version_from_metadata(filename)
    version = `grep ^version '#{filename}' | awk -F "'" '{print $2}'`
    raise "!!! Failed to parse version from #{filename}" unless $CHILD_STATUS == 0
    version.strip # return
  end

  # Utility intended to be executed as part of build/verification process
  # to ensure the metadata.rb is updated when a PR to development branch is open
  desc 'make sure version is incremented versus development branch'
  task :verify do

    if run_version_checks?
      require 'chef/cookbook/metadata'

      # Verify the metadata.rb version is updated versus the origin/development
      Dir.foreach('chef/cookbooks') do |cookbook|
        next if cookbook == '.' || cookbook == '..' # skip these dirs

        log "version:verify: Verifying metadata.rb for cookbook: #{cookbook}..."

        # raise error if metadata.rb is missing
        log_raise_error("Error: missing metadata.rb for cookbook '#{cookbook}'")\
            unless File.file?("chef/cookbooks/#{cookbook}/metadata.rb")

        # Get version from local metadata.rb
        new_metadata_version = cookbook_version_from_metadata("chef/cookbooks/#{cookbook}/metadata.rb")

        # Get version from 'development' branch
        old_metadata_version = nil
        with_repo_clone('development') do
          # We are inside the 'development' branch, compute it's version
          old_metadata_version = cookbook_version_from_metadata("chef/cookbooks/#{cookbook}/metadata.rb")
        end

        log "Old version: #{old_metadata_version}"
        log "New version: #{new_metadata_version}"
        # Compare the 2 version using Gem::Version
        unless (Gem::Version.new(new_metadata_version) <=> Gem::Version.new(old_metadata_version)) > 0
          log "\nERROR: The metadata.rb for cookbook '#{cookbook}' needs a version increment!"\
              "\n       Please execute 'rake version:increment' in your branch"\
              "\n       to have the version incremented."\
              "\n       Then, ensure you commit the resulting metadata.rb to git.", 31
          raise 'error in medatada.rb'
        end
        log "metadata.rb version verification successful."
      end # foreach
    end # run_version_checks?
  end # :verify

end # :version
