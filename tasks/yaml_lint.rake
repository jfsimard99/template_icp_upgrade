require './tasks/utils.rb'

desc 'Validates all yaml files'
task :yaml_lint do
  require 'yaml'

  count = 0
  path_dir = Dir.pwd
  Dir.glob(path_dir + '/**/*.{yml,yaml}', File::FNM_DOTMATCH) do |path|
    unless File.directory?(path)
      count += 1
      begin
        YAML.load_file(path)
      rescue
        log_raise_error("Error loading yaml: " + path)
      end
    end
  end
  if count == 0
    log("No yml/yaml files found", 33)
  elsif count > 0
    log "Linting of " + count.to_s + " yml/yaml files successful"
  end
end
