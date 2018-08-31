require 'yaml'
require 'find'
require './tasks/utils.rb'

desc 'Invoke static code rules in sequence - copyright_checker, password_checker, ip_checker, mode_checker'
task :invoke_all_static_rules do
  Rake::Task[:execute_static_rules].invoke('copyright_checker', 'password_checker', 'ip_checker', 'mode_checker')
end

desc 'execute static code rules - copyright_checker, password_checker, ip_checker, mode_checker'
task :execute_static_rules, [:copyright_checker, :password_checker, :ip_checker, :mode_checker] do |_t, args|
  args.each do |_t, arg|
    content = YAML.load_file(Dir.pwd + '/tasks/static_code_analysis_rules.yaml')
    content.each do |_key, value|
      next unless value.is_a?(Hash)
      log_raise_error('Internal configuration error. Unable to find rule named:  ' + args[arg]) unless value.key?(args[arg])
      rule_content = value[args[arg]]
      if 'fail_on_no_match'.eql?(rule_content['type'])
        fail_on_no_match(rule_content, args[arg])
      elsif 'fail_on_match'.eql?(rule_content['type'])
        fail_on_match(rule_content, args[arg])
      end
    end
  end
  log 'finished executing rules'
end

def fail_on_no_match(content, rule_name)
  validate(content, rule_name)
  regex_pattern = content['content']
  error_message = content['error_message']
  path_dir = Dir.pwd
  count = 0
  glob_match = content['files']
  glob_match.each do |glob_val|
    Dir.glob(path_dir + '/**/' + glob_val) do |path|
      next if File.directory?(path)
      count+=1
      if content.key?('end_line')
        end_line = content['end_line']
        lines = File.foreach(path).first(end_line)
      else
        #Check all lines
        lines = File.foreach(path)
      end
      git_timestamp = `echo "$(git log -1 --format="%ad" -- #{path})"`
      git_values = git_timestamp.split(' ')
      commit_year = git_values[4]
      if commit_year.nil? || commit_year.empty?
        # new file use current year
        commit_year = Time.new.year
      end
      regex_pattern_new = regex_pattern.gsub '#{commit_year}', commit_year.to_s
      pattern = Regexp.new(regex_pattern_new).freeze
      unless lines.find { |e| pattern =~ e }
        puts 'executing rule :  ' + rule_name + ' file: ' + path
        raise error_message + ' in ' + path + ' matching pattern ' + regex_pattern_new
      end
    end
  end
  log 'Scanned ' + count.to_s + ' files: ' + rule_name + ' completed successfully '
end

def fail_on_match(content, rule_name)
  validate(content, rule_name)
  regex_pattern = content['content']
  error_message = content['error_message']
  path_dir = Dir.pwd
  count = 0
  exclude_array = content['exclude'] || []
  ignore_text = content['ignore_rule']
  glob_match = content['files']
  glob_match.each do |glob_val|
    Dir.glob(path_dir + '/**/' + glob_val) do |path|
      next if File.directory?(path)
      next if exclude_array.any? { |e| File.path(path).include?(e) }
      pattern = Regexp.new(regex_pattern).freeze
      count+=1
      #Check all lines
      File.foreach(path).with_index do |line, line_num|
        file_line_num = line_num + 1
        line_str_strip = line.to_s.strip
        #print line_str_strip
        if !line_str_strip.start_with?('#') && !line_str_strip.start_with?('<%#')
          if line_str_strip.end_with?(ignore_text) || line_str_strip.end_with?(ignore_text + ' %>')
            next
          end
          if line.match pattern
            puts 'executing rule :  ' + rule_name + ' file: ' + path
            raise error_message + line.strip + ' in ' + path + ' at line ' + file_line_num.to_s
          end
        end
      end
    end
  end
  log 'Scanned ' + count.to_s + ' files: ' + rule_name + ' completed successfully '
end

def validate(content, rule_name)
  return if ['content', 'files', 'error_message'].all? { |s| content.key? s }
  raise 'content, files, error_message are required fields for ' + rule_name
end
