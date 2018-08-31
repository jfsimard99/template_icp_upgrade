# Copyright IBM Corp. 2017, 2018
require './tasks/utils.rb'

namespace :doc do

  # helper utility to install prerequisite gems if missing
  def install_prereq_gems
    gems = ['knife-cookbook-readme']
    gems.each do |gem|
      output = `gem list #{gem} | grep #{gem}`
      if output.lines.count == 0
        log "installing gem: #{gem}"
        sh "gem install #{gem}"
      end
    end
  end

  # Utility intended for developers to run locally to generate the README.md
  # from the metadata.rb file.  It uses the knife-cookbook-readme gem, which
  # will be automatically installed if missing
  desc 'execute knife-cookbook-readme to generate README.md'
  task :readme do
    install_prereq_gems
    # Find all the cookbooks, and spin a knife-cookbook-readme task against each
    # For usage, see: https://github.com/mlafeldt/knife-cookbook-readme
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      log "\nRunning knife-cookbook-readme for cookbook: #{cookbook}..."
      Dir.chdir("chef/cookbooks/#{cookbook}") do
        sh "knife cookbook readme from metadata.rb > README.md"
      end # end :Dir.chdir()

      # copy the README.md to root directory
      FileUtils.cp("chef/cookbooks/#{cookbook}/README.md", Dir.pwd)
    end # end :Dir.foreach()
  end # end :readme

  # Utility intended to be executed as part of build/verification process
  # to ensure the README.md is in-sync with the metadata.rb from which
  # README.md is generated (using knife-cookbook-readme gem).
  desc 'verify README.md'
  task :verify_readme do
    install_prereq_gems
    # Verify the contents of README.md
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      # verify README.md is correct
      verify_files_match_after_action(
        ["chef/cookbooks/#{cookbook}/README.md"],
        "ERROR: The README.md for cookbook '#{cookbook}' is incorrect!"\
            "\n       Please execute 'rake doc:readme' to have the README.md"\
            "\n       file automatically generated from metadata.rb."\
            "\n       Then, ensure you commit the resulting README.md to git.") do

        Dir.chdir("chef/cookbooks/#{cookbook}") do
          sh "knife cookbook readme from metadata.rb > README.md"
        end # Dir.chdir
      end # verify_files_match_after_action()

    end # end :Dir.foreach()
  end

  # Utility intended to be executed as part of build/verification process
  # to ensure the README.md in repo root is identical to the one in cookbook
  # desc 'verify README.md in repo root is identical to the one in cookbook'
  task :verify_readme_synced do

    # raise error if repo README.md is missing
    raise "Error: missing README.md for repo, please copy the one from"\
     "cookbook." unless File.file?('README.md')
    repo_readme = File.absolute_path('README.md')

    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      log "\ndoc:verify_readme_synced: Verifying README.md for cookbook: #{cookbook}..."
      Dir.chdir("chef/cookbooks/#{cookbook}") do
        # raise error if cookbook README.md is missing
        raise "Error: missing README.md for cookbook '#{cookbook}', use 'rake doc:readme'"\
            "to generate." unless File.file?('README.md')
        readme = File.absolute_path('README.md')

        # raise error if README.md are different
        raise "ERROR: The README.md for repo should be identical with the one for cookbook. Please"\
          "\n    cp #{readme} #{repo_readme}"\
          "\nthen commit it to git.\n\n" unless FileUtils.compare_file(repo_readme, readme)

        log "README.md is in sync between repo and cookbook."
      end
    end
  end

  desc 'execute yard-chef'
  task :yard do
    # Find all cookbooks, and spin a Yard task against each
    Dir.foreach('chef/cookbooks') do |cookbook|
      next if cookbook == '.' || cookbook == '..' # skip these dirs

      log "\nRunning yard-chef for cookbook: #{cookbook}..."
      Dir.chdir("chef/cookbooks/#{cookbook}") do
        sh "yardoc '**/*.rb' --no-cache --no-save --plugin chef"
      end # end chdir()
    end # end Dir.foreach()
  end # end :yard

end # end: doc
