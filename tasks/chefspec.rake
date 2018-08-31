require './tasks/utils.rb'

# internal task to run berkshelf install
task(:berkshelf) do
  log "Executing 'berks install' to load dependencies..."
  sh "berks install"
end

desc 'Run Chefspec tests against all cookbooks'
task :spec => [:berkshelf] do # this must be called ':spec' or it will not work :/ ??
  # Find all the cookbooks, and spin an RSpec task against each
  Dir.foreach('chef/cookbooks') do |cookbook|
    next if cookbook == '.' || cookbook == '..' # skip these dirs

    log "Running chefspec tests for cookbook: #{cookbook}..."
    RSpec::Core::RakeTask.new do |rspec|
      rspec.rspec_opts = "--default-path chef/cookbooks/#{cookbook} --color --fail-fast --format documentation"
    end
  end
end
