require 'rspec/core/rake_task'

desc 'Run all style checks'
task :style => ["style:ruby", "style:chef"]

namespace :style do
  require "cookstyle"
  require 'rubocop/rake_task'
  require 'foodcritic'

  # Ruby style checks with RuboCop
  desc 'Run Ruby style checks'
  RuboCop::RakeTask.new(:ruby) do |t|
    t.options = ["--fail-fast", "-D"] # Inspect files in order of modification
    #    time and stop after the first file
    #    containing offenses.
    # t.fail_on_error = false # uncomment to ignore violations
  end

  # Chef style checks with FoodCritic
  desc 'Run Chef style checks'
  FoodCritic::Rake::LintTask.new(:chef) do |t|
    t.options = {
      cookbook_paths: 'chef/cookbooks',
      tags: %w(~FC014 ~FC069 ~FC072 ~FC075 ~FC078),
      fail_tags: ['any'] }
  end
end # :style
