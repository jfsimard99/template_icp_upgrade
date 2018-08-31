require './tasks/utils.rb'

desc 'Validates all json files'
task :json_lint do
  count = 0
  path_dir = Dir.pwd
  Dir.glob(path_dir + '/**/*.json') do |path|
    unless File.directory?(path)
      count += 1
      begin
        JSON.parse(File.read(path))
      rescue
        log_raise_error("Error loading json: " + path)
      end
    end
  end
  if count == 0
    log("No json files found", 33)
  elsif count > 0
    log "Linting of " + count.to_s + " json files successful"
  end
end
