require 'json'
require './tasks/utils.rb'

namespace :validate_file_struct do

  desc 'validate cookbook file structure'
  task :cookbooks do
    validate_file_struct('tasks/file_struct_configs/cookbooks.json')
  end


  desc 'validate template file structure'
  task :templates do
    validate_file_struct('tasks/file_struct_configs/templates.json')
  end


  ## Validates pattern file structure with matches validate_file_struct.json:
  #  - Check if folder structure matches expected json format
  #  - Check if required files exist in their appropriate dir
  #  - Check if unwanted files do not exist in a particular dir
  def validate_file_struct(config_file)
    log "Validating pattern file structure using #{config_file}"
    base_file_path = Dir.pwd
    log_raise_error("Config file: #{config_file} does not exist") \
      unless File.exist?(config_file)
    content = JSON.parse(File.read(config_file))
    flatten_hash = flatten_file_struct_hash(content)

    #Iterate flatten hash
    flatten_hash.each do |key, value|
      key_arr = key.split('.')
      pattern_file_path = base_file_path
      #Build file-path
      key_arr.each do |x|
        next if x.eql?('files') || x.eql?('mandatory') || x.eql?('unwanted')
        pattern_file_path = pattern_file_path + '/' + x
        if pattern_file_path.include?('<cookbook_name>')
          actual_file_path = base_file_path + '/chef/cookbooks/'
          cookbook_name = find_folder_name(actual_file_path)
          if cookbook_name.to_s.strip.empty?
            log_raise_error('No cookbook found under ' + pattern_file_path)
          end
          pattern_file_path.gsub!('<cookbook_name>', cookbook_name)
        elsif pattern_file_path.include?('<provider_name>')
          provider_file_path = base_file_path + '/resources/'
          provider_name = find_folder_name(provider_file_path)
          if provider_name.to_s.strip.empty?
            log_raise_error('No orchestration provider in ' + pattern_file_path)
          end
          pattern_file_path.gsub!('<provider_name>', provider_name)
        end
      end
      #Check if its a directory
      log_raise_error("Directory not found: #{pattern_file_path}") \
        unless pattern_file_path.include?('**') || Dir.exist?(pattern_file_path)

      # pattern_file_path could be a pattern itself, Glob it and iterate
      Dir.glob(pattern_file_path, File::FNM_DOTMATCH).select do |d|
        next unless File.directory?(d)

        #Loop through all files in directory, construct an array
        files_arr = []
        Dir.glob(d + '/*', File::FNM_DOTMATCH).select do |f|
          if File.file?(f)
            files_arr << File.basename(f)
          elsif File.directory?(f)
            dirname = File.basename(f)
            next if dirname == '.' || dirname == '..' # skip
            files_arr << dirname+"/"
          end
        end

        log_raise_error("No files found in: #{d} Expecting files matching: #{value}") \
          if files_arr.empty?
        #Check if files really exist matching the pattern from flatten_hash {"key" => "value" }

        value.each do |x|
          pattern = Regexp.new(x).freeze

          if key.include?('mandatory')
            #Fail if required files doesnt exist
            log_raise_error("Missing required files: #{x} in #{d}") \
              unless files_arr.find { |e| pattern =~ e }
          elsif key.include?('unwanted')
            #Fail if these files exists
            log_raise_error("unwanted files found: #{x} in #{d}. These files should not exist") \
              if files_arr.find { |e| pattern =~ e }
          end

        end
      end
    end
    log "Validation of #{Dir.pwd} file structure completed successfully"
  end

  desc 'check if every recipe contains a ChefSpec named: <recipe_name>_spec.rb'
  task :chef_spec_exists do
    sub_folder_path = '/chef/cookbooks/'
    cookbook_folder = Dir.pwd + sub_folder_path
    cookbook_name = find_folder_name(cookbook_folder)
    recipes_folder = Dir.pwd + sub_folder_path + cookbook_name + '/recipes'
    chef_spec_folder = Dir.pwd + sub_folder_path + cookbook_name + '/spec/recipes'
    count = 0
    unless Dir.exist?(chef_spec_folder)
      log_raise_error('ChefSpec folder: ' + chef_spec_folder + ' doesnt exist')
    end
    if Dir.exist?(recipes_folder)
      Dir.glob(recipes_folder + '/*').select do |f|
        next unless File.file?(f)
        count += 1
        file_name = File.basename(f, '.*')
        spec_file_name = file_name + '_spec.rb'
        chefspec_full_path = chef_spec_folder + '/' + spec_file_name
        unless File.file?(chefspec_full_path)
          log_raise_error('No matching ChefSpec found for ' + f + '. There must be a unit test in ' + chefspec_full_path)
        end
      end
    end
    log 'Scanned ' + count.to_s + ' files in ' + recipes_folder + ' ChefSpec found for every recipe. '
  end
end

def flatten_file_struct_hash(content, recursive_key = "")
  content.each_with_object({}) do |(k, v), ret|
    key = recursive_key + k.to_s
    if v.is_a? Hash
      ret.merge! flatten_file_struct_hash(v, key + '.')
    else
      ret[key] = v
    end
  end
end

def find_folder_name(base_folder)
  sub_folder_name = ''
  log_raise_error("Directory: #{base_folder} does not exist") \
    unless Dir.exist?(base_folder)
  folder_arr = Dir.entries(base_folder)
  folder_arr.each do |x|
    unless x.eql?('.') || x.eql?('..')
      sub_folder_name = x
    end
  end
  sub_folder_name
end
