# Copyright IBM Corp. 2017, 2018

desc 'Validates metadata.rb in the cookbook'
task :metadata_lint do
  metadata_path = ''
  Dir.glob(Dir.pwd + '/**/metadata.rb') do |path|
    metadata_path = path
  end
  parent_dir = File.dirname(metadata_path)
  cookbook_name = File.basename(parent_dir)
  git_timestamp = `echo "$(git log -1 --format="%ad" -- #{metadata_path})"`
  git_values = git_timestamp.split(' ')
  commit_year = git_values[4]
  if commit_year.nil? || commit_year.empty?
    #new file use the current year
    commit_year = Time.new.year
  end
  expected_metadata = { "name" => "'#{cookbook_name}'", "license" => /'Copyright IBM Corp. ([0-9]{4}, )#{commit_year}'/, "maintainer" => "'IBM Corp'", "maintainer_email" => "''" }
  actual_metadata = {}
  File.open(metadata_path, 'r') do |file|
    file.each_line do |line|
      line_data = line.split(' ', 2)
      verify_line_data(line_data)
      actual_metadata[line_data[0]] = line_data[1]
    end
  end
  expected_metadata.each do |key, value|
    unless actual_metadata.key?(key)
      raise "metadata.rb missing expected #{key}: #{expected_metadata[key]}"
    end
    actual_val_strip = actual_metadata[key].strip
    if key == "license"
      #Regex match requires special handling
      unless value =~ actual_metadata['license']
        raise "expected #{key}: #{expected_metadata[key]} found #{actual_metadata[key]}"
      end
    else
      unless value.eql?(actual_val_strip)
        raise "expected  #{key}: #{expected_metadata[key]} found #{actual_metadata[key]}"
      end
    end
  end # expected_metadata

  puts "metadata.rb validation completed successfully"
end # :metadata_lint

def verify_line_data(line_data)
  return unless line_data[0] == 'supports'
  # ensure that 'supports' version format is valid
  # see: https://docs.chef.io/config_rb_metadata.html
  supports_value_version = line_data[1].split(',', 2)[1]
  raise "invalid format for 'supports': #{supports_value_version}" if supports_value_version && supports_value_version !~ /(<|<=|=|>=|~>|>) [0-9]+.[0-9]+/
end # verify_line_data
