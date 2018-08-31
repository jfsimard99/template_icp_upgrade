Rake.add_rakelib 'tasks'

# Rake task that allows you to debug rake tasks (via irb console)
# Run: `rake debug` to launch
task :debug do
  require 'irb'
  ARGV.clear
  IRB.start
end

# Default rake task (build for cookbooks)
desc 'Default build tasks for cookbook repositories'
task :default => [:style, :yaml_lint, :json_lint, :metadata_lint,
                  :invoke_all_static_rules, 'doc:verify_readme',
                  'doc:verify_readme_synced', 'validate_file_struct:cookbooks',
                  'version:verify', 'metadata:validate', 'metadata:verify_meta', 'metadata:verify_chefmeta',
                  'camhub:verify_license_file', :spec]

# base task for terraform projects (modules, templates, etc)
task :template_modules => [:yaml_lint, :json_lint, :hcl_lint, :invoke_all_static_rules, 'camhub:verify_tag']
# There is an HCL parse problem, which does not allow valid json : https://github.com/hashicorp/hcl/issues/234
task :template_modules_skip_hcl => [:yaml_lint, :json_lint, :invoke_all_static_rules, 'camhub:verify_tag']

desc 'Default build tasks for template repositories'
task :templates => [:template_modules, 'validate_file_struct:templates', 'orpheus:test_modified_templates']

# Cookbook Publishing and Test Environment setup
desc 'Publish and sync cookbooks to Test environemtns - Travis Only'
task :publish_cookbook => ['camhub:publish', 'camhub:env_cookbook_sync']

desc 'Generates all cookbook metadata files'
task :metadata_generate => ['metadata:validate', 'metadata:chefmeta',
                            'metadata:meta', 'doc:readme']

# task to build the pattern_build project itself
task :pattern_build => ['style:ruby', :yaml_lint, :json_lint, :invoke_all_static_rules]
