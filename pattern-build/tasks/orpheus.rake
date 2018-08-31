# Copyright IBM Corp. 2017, 2018

# This collection of rake tasks are  used to integrate with the orpheus
# template catalog build/registrion processes for CAMaaS
namespace :orpheus do

  require './tasks/utils.rb'
  require 'json'
  require 'optparse'

  # Load and verify ''.camhub.yml' configuration file
  def load_camhub_config
    camhub_options = load_config('.camhub.yml')['cam_hub']

    ['development', 'test', 'master'].each do |branch_name|
      raise "Branch #{branch_name} is not defined in '.camhub.yml'" \
        unless camhub_options.key?(branch_name)
      raise "hostname missing for branch '#{branch_name}' in '.camhub.yml'" \
        unless camhub_options[branch_name].key?('hostname')
      raise "org_name missing for branch '#{branch_name}'' in '.camhub.yml'" \
        unless camhub_options[branch_name].key?('org_name')
    end
    camhub_options # return
  end

  def generate_template_environs
    raise "Repository does not have '/environments' directory!  Ensure this is a template repository."\
      unless Dir.exist?("environments")
    repo_name = current_repo_name # my repository name
    camhub_conf = load_camhub_config
    # Orpheus aaS environments
    orpheus_envs = {
      "development" => ["dallas-ys1-dev" => "https://cam-proxy-dev.stage1.ng.bluemix.net",
                        "dallas-prod-dev" => "https://cam-proxy-dev.ng.bluemix.net" ],
      "test" => ["dallas-ys1-qa" => "https://cam-proxy-qa.stage1.ng.bluemix.net",
                 "dallas-prod-qa" => "https://cam-proxy-qa.ng.bluemix.net",
                 "dallas-prod-pen" => "https://cam-proxy-pen.ng.bluemix.net" ],
      "master" => ["dallas-ys1" => "https://cam-proxy.stage1.ng.bluemix.net",
                   "dallas-camprodspace1" => "https://cam-proxy-ng.ng.bluemix.net",
                   "dallas-camprodspace2" => "https://cam-proxy-ng.ng.bluemix.net" ] }.freeze

    # Find all the camtemplate.json files in the repo
    catalog_filenames = Dir.glob("**/camtemplate\.json").sort
    catalog_filenames = catalog_filenames.map { |fn| "./#{fn}" }.compact # add "./" to the beging of each

    # switch to environments directory and create all the env JSON files
    Dir.chdir("environments") do
      FileUtils.rm Dir.glob('*.json') # delete all the JSON files here
      orpheus_envs.each do |env_type, envs|
        envs.each do |env|
          env.each do |env_name, rest_api_endpoint|
            camhub_host = camhub_conf[env_type]['hostname']
            camhub_org = camhub_conf[env_type]['org_name']

            github_repo_url = if "github.com".casecmp(camhub_host) == 0
                                 "https://api.github.com/#{camhub_org}/#{repo_name}/"
                              else # GHE support
                                 "https://#{camhub_host}/#{camhub_org}/#{repo_name}/"
                              end

            new_hash = {
              "CATALOG_REST_API_ENDPOINT" => rest_api_endpoint,
              "CATALOG_LIST" => catalog_filenames,
              "GITHUB_REPO_URL" => github_repo_url }
            File.open("#{env_name}-catalogs.json", 'w') do |f|
              f.write(JSON.pretty_generate(new_hash))
            end # File.open
          end # env.each
        end # envs.each
      end # orpheus_envs.each
    end # chdir
  end # generate_template_environs


  # Rake task that generates the orpheus template 'environment' files
  desc 'Generates template repo environment files'
  task :generate_template_environs do
    log "orpheus:generate_template_environs starting..."
    generate_template_environs
    log "orpheus:generate_template_environs done."
  end # :generate_template_environs


  # Rake task that validates the ohrpheus template 'environments' files
  desc 'Verifies template repo environment files'
  task :verify_template_environs do
    log "orpheus:verify_template_environs starting..."

    # verify that all the environments/*.json files are generated correctly
    env_files = Dir.glob("environments/*.json").sort
    verify_files_match_after_action(
      env_files, # files to check
      "!!! verify_template_environs failure: Ensure you execute 'rake orpheus:generate_template_environs'"\
        "\nand commit the modified 'environments/*.json' files generated from the process "\
        "\ninto your feature branch."
    ) do

      # run the generator tool
      generate_template_environs

      # ensure the no new files were created/deleted during the process
      new_env_files = Dir.glob("environments/*.json").sort
      unless env_files.size == new_env_files.size && env_files & new_env_files == env_files
        raise "The 'environments' filesets are different!  Ensure you execute 'rake orpheus:generate_template_environs'"\
          "\nand commit the modified 'environments/*.json' files generated from the process "\
          "\ninto your feature branch."
      end
    end # verify_files_match_after_action()

    log "orpheus:verify_template_environs done."
  end # :verify_template_environs


  # install python dependencies
  def install_template_runner_deps
    sh "pip install pyhcl --user"
    sh "pip install requests retrying --ignore-installed six --user"
  end

  # Executes the template_runner
  def template_runner(
      tf_template_file, tf_variable_file, camvariable_filename, cam_env,
      stack_name, bmx_user, bmx_org, bmx_space, cloud_type, cloud_connection,
      extra_tf_var = ''
  )

      cmd = "time python tasks/template_runner/template_runner.py "\
        "-t '#{tf_template_file}' -v '#{tf_variable_file}' #{extra_tf_var} "\
        "-e '#{cam_env}' -n '#{stack_name}' -u '#{bmx_user}' "\
        "-o '#{bmx_org}' -s '#{bmx_space}' "\
        "-#{cloud_type.downcase} '#{cloud_connection}' "\
        "--delete_failed_deployments --autodestroy"
      if camvariable_filename
        cmd += " -cv '#{camvariable_filename}'"
      end

      log "Launching template: #{tf_template_file} ..."
      sh "export PYTHONWARNINGS='ignore' && #{cmd}"
  end # :template_runner

  def template_runner_local(
      tf_template_file, tf_variable_file, camvariable_filename,
      stack_name, w3_username, cam_url, cloud_type, cloud_connection,
      git_branch, extra_tf_var = ''
  )

      cmd = "time python tasks/template_runner_local/template_runner_local.py "\
        "-t '#{tf_template_file}' -v '#{tf_variable_file}' #{extra_tf_var} "\
        "-n '#{stack_name}' -u '#{w3_username}' "\
        "-c '#{cam_url}' -b '#{git_branch}' "\
        "-#{cloud_type.downcase} '#{cloud_connection}' "\
        "--delete_failed_deployments --autodestroy"
      if camvariable_filename
        cmd += " -cv '#{camvariable_filename}'"
      end

      log "Launching template: #{tf_template_file} ..."
      log "local command: #{cmd}"
      sh "export PYTHONWARNINGS='ignore' && #{cmd}"
  end # :template_runner_local

  #Ticket 1855 - Add a new template runner to handle central varibale translations.
  #This method will not utilise tf_variable_file or extra_tf_var and add the notion
  #Of the translation file and the override file

  def template_runner_local2(
      tf_template_file, camvariable_filename,
      stack_name, w3_username, cam_url, cloud_type, cloud_connection,
      git_branch, override_filename, translation_filename
  )

      cmd = "time python tasks/template_runner_local/template_runner_local.py "\
        "-t '#{tf_template_file}' " \
        "-n '#{stack_name}' -u '#{w3_username}' "\
        "-c '#{cam_url}' -b '#{git_branch}' "\
        "-#{cloud_type.downcase} '#{cloud_connection}' "\
        "--delete_failed_deployments --autodestroy "\
        "-o '#{override_filename}' -tf '#{translation_filename}'"
      if camvariable_filename
        cmd += " -cv '#{camvariable_filename}'"
      end

      log "Launching template with Translations: #{tf_template_file} ..."
      log "local command: #{cmd}"
      sh "export PYTHONWARNINGS='ignore' && #{cmd}"
  end # :template_runner_local2

  def create_content_runtime_local(
    tf_template_file, camvariable_filename,
    stack_name, cam_url, cloud_type, cloud_connection,
    git_branch, override_filename, translation_filename
  )

     cmd = "time python tasks/template_runner_local/create_content_runtimes.py "\
      "-t '#{tf_template_file}' " \
      "-n '#{stack_name}' -pr #{cloud_type} "\
      "-c '#{cam_url}' -b '#{git_branch}' "\
      "-#{cloud_type.downcase} '#{cloud_connection}' "\
      "-o '#{override_filename}' -tf '#{translation_filename}' "\
      "--delete_failed_deployments  --use_existing"
     if camvariable_filename
       cmd += " -cv '#{camvariable_filename}'"
     end
  
     log "Launching template with Translations: #{tf_template_file} ..."
     log "local command: #{cmd}"
     sh "export PYTHONWARNINGS='ignore' && #{cmd}"
  end

  # Given a template directory, find the template and variables file and execute
  # the template against CAMaaS
  def test_tf_dir(template_dir, branch_name, environ_dir)
    template_filename, variable_filename, camvariable_filename = nil
    Dir[File.join(template_dir, '*')].each do |filename|
      log "Process filename: #{filename}"
      if filename.end_with?('.tf') && !filename.end_with?('bastionhost.tf') && !filename.end_with?('httpproxy.tf')
        log "Template filename: #{filename}"
        template_filename = filename
      elsif filename.end_with?('camvariables.json')
        camvariable_filename = filename
      end
    end

    # Needed to move the variables file out of the main directory so that
    # CAM didn't import it when creating the template
    Dir[File.join(template_dir, '..', 'build', '*')].each do |filename|
      if filename.end_with?('variables.tf')
        variable_filename = filename
      end
    end

    raise "Unable to find TF template file in #{template_dir}" unless template_filename
    #raise "Unable to find TF variables file in #{template_dir}" unless variable_filename

    cloud_type = "ibm" if template_dir.include?("ibmcloud/")
    cloud_type = "aws" if template_dir.include?("amazon/")
    cloud_type = "vmware" if template_dir.include?("vmware/")
    cloud_type = "other" if template_dir.include?("other/")
    
    #Added vmware to allow merge during power outage
    if cloud_type == "other" || cloud_type == "vmware"
      log "skipping other templates ..............."
    else
      # else
      # template_runner(
      #   template_filename, variable_filename, camvariable_filename,
      #   'qa', # see https://github.ibm.com/Orpheus/orpheus-support/issues/167
      #   Time.new.strftime("travisci-%Y%m%d-%H%M%S-#{cloud_type}-#{template_filename.split('/')[-1].split('.')[0]}"), # stack name
      #   'apikey', 'CAM Content', 'dev', # bmx_user, bmx_org, bmx_space,
      #   cloud_type,
      #   "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
      #   File.join(environ_dir, "#{branch_name}-#{cloud_type}-secretvars.tf"))
      current_branch_pr = current_branch
      log "template_runner_local................"

      log "template_filename: #{template_filename}"
      log "variable_filename: #{variable_filename}"
      log "camvariable_filename: #{camvariable_filename}"
      log "username: octravis@us.ibm.com"
      log "cam_url: 9.30.117.66"
      log "cloud_type: #{cloud_type}"
      log "Original Branch Name: #{current_branch_pr}"
      log "secrets file: #{branch_name}-#{cloud_type}-secretvars.tf"

      # Ticket 1855 - add the new templaterunner2 method if the central
      # variable translation method is used.

      template_provider = "template_runner_local"
      template_translation = ENV.fetch('TEMPLATE_TRANSLATION')
      unless template_translation.nil?
        if template_translation.casecmp("TRUE") == 0
          template_provider = "template_runner_local2"
          override_filename = File.join(template_dir, 'override_variables.json')
          translation_filename = File.join(Dir.pwd, 'tasks/template_runner_local/testing_variables.json')
        end
      end

      if template_provider == "template_runner_local2"
        template_runner_local2(
          template_filename, camvariable_filename,
          Time.new.strftime("travisci-%Y%m%d-%H%M%S-#{cloud_type}-#{template_filename.split('/')[-1].split('.')[0]}"), # stack name
          'octravis@us.ibm.com', '9.30.117.66', # W3 ID and CAM IP Address
          cloud_type,
          "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
          current_branch_pr.to_s, override_filename, translation_filename
        )
      else
        template_runner_local(
          template_filename, variable_filename, camvariable_filename,
          Time.new.strftime("travisci-%Y%m%d-%H%M%S-#{cloud_type}-#{template_filename.split('/')[-1].split('.')[0]}"), # stack name
          'octravis@us.ibm.com', '9.30.117.66', # W3 ID and CAM IP Address
          cloud_type,
          "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
          current_branch_pr.to_s,
          File.join(environ_dir, "#{branch_name}-#{cloud_type}-secretvars.tf")
        )
      end
    end
  end # test_tf_dir


  # Given a template directory, find the template and variables file and execute
  # the template against CAMaaS

  def test_cr_dir(template_dir, branch_name)
    template_filename, camvariable_filename, override_filename = nil
    Dir[File.join(template_dir, '*')].each do |filename|
      if filename.end_with?('.tf')
        template_filename = filename
      elsif filename.end_with?('camvariables.json')
        camvariable_filename = filename
      elsif filename.end_with?('override_variables.json')
        override_filename = filename
      end
    end

    if override_filename.nil?
      log "No overide_variables.json for #{template_dir}. Skipping."
      return
    end

    raise "Unable to find TF template file in #{template_dir}" unless template_filename
    #raise "Unable to find TF variables file in #{template_dir}" unless variable_filename

    translation_filename = File.join(Dir.pwd, 'tasks/template_runner_local/testing_variables.json')

    cloud_type = "ibm" if template_dir.include?("ibm/")
    cloud_type = "aws" if template_dir.include?("amazon/")
    cloud_type = "vmware" if template_dir.include?("vmware/")
    cloud_type = "other" if template_dir.include?("other/")

    #if cloud_type != "ibm"
    #  return
    #end

    if cloud_type == "other"
      log "skipping other templates ..............."
    else
      # else
      # template_runner(
      #   template_filename, variable_filename, camvariable_filename,
      #   'qa', # see https://github.ibm.com/Orpheus/orpheus-support/issues/167
      #   Time.new.strftime("travisci-%Y%m%d-%H%M%S-#{cloud_type}-#{template_filename.split('/')[-1].split('.')[0]}"), # stack name
      #   'apikey', 'CAM Content', 'dev', # bmx_user, bmx_org, bmx_space,
      #   cloud_type,
      #   "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
      #   File.join(environ_dir, "#{branch_name}-#{cloud_type}-secretvars.tf"))

      current_branch_pr = branch_name
      cam_url = ENV.fetch('cam_url')
       

      log "template_runner_local................"

      log "template_filename: #{template_filename}"
      log "camvariable_filename: #{camvariable_filename}"
      log "username: octravis@us.ibm.com"
      log "cam_url:  #{cam_url}"
      log "cloud_type: #{cloud_type}"
      log "Original Branch Name: #{current_branch_pr}"
      log "secrets file: #{branch_name}-#{cloud_type}-secretvars.tf"
      log "Override file: #{override_filename}"
      log "Translation file: #{translation_filename}"

      # abw

      create_content_runtime_local(
        template_filename, camvariable_filename,
        "camc-#{cloud_type}-octravis",
        cam_url, cloud_type,
        "#{cloud_type}.octravis", # ibmcloud.octravis or aws.octravis
        current_branch_pr.to_s, override_filename, translation_filename
      )
    end
  end # test_cr_dir


  # Download, decrypt, and unzip the secretvars into specified temp directory

  def stage_secretvars(temp_dir, artifactory_host, artifactory_user, artifactory_token, archive_password)
    gpg_abs_filename = File.join(temp_dir, 'tf-secretvars.zip.gpg')
    # download (and decrypt)
    fetch_remote_file_url(
      gpg_abs_filename,
      "https://#{artifactory_host}/artifactory/orpheus-local-generic/opencontent/labs/tf-secretvars.zip.gpg",
      artifactory_user, artifactory_token, archive_password
    )

    # unzip
    `unzip -o #{File.join(temp_dir, 'tf-secretvars.zip')} -d #{temp_dir}`
    raise "!!! Failed to unzip tf-secretvars.zip" unless $CHILD_STATUS == 0
  end # stage_secretvars

  def create_content_runtime(&closure)
    template_files = yield closure

    # filter to TF template directories
    tf_dirs = template_files.collect { |file| file.sub(/\/public\/.*$/, "/public/") }.uniq

    if tf_dirs.empty?
      log("No modified templates detected, skipping tests.", 33)
      return
    end

    # install_template_runner_deps # install deps

    current_branch = my_branch # current git-branch name
    work_queue = Queue.new
    tf_dirs.each { |tf_dir| work_queue.push(tf_dir) }
    status_map = {}
    first_error = nil
    worker_threads = (1..[15, tf_dirs.size].min).map do |thread_num| # max 15 threads
      next if first_error # quick exit if already failures
      log "Spawning worker thread ##{thread_num} in #{thread_num+1} seconds..."
      sleep(thread_num+1) # sleep thread_num seconds -- delays new threads with backoff
      Thread.new do
        begin
          log "Worker thread #{thread_num} started."
          while tf_dir = work_queue.pop(true) # rubocop:disable Lint/AssignmentInCondition
            begin
              if first_error
                log "Not running test for #{tf_dir}, due to earlier errors.", 33
                status_map[tf_dir] = "skipped"
                next
              end # if first_error

              log "Executing test_cr_dir for #{tf_dir}..."
              log "Executing test_cr_dir branch #{current_branch}..."

              test_cr_dir(tf_dir, current_branch)
              log "OK: #{tf_dir}"
              status_map[tf_dir] = "success"
            rescue StandardError => e
              log "ERROR: test_cr_dir failed for #{tf_dir}.  Cause: #{e}", 31
              first_error = e unless first_error
              status_map[tf_dir] = "fail"
            end # rescue
          end # while
        rescue ThreadError => te
          log "Worker thread ##{thread_num} terminating: #{te}" # ok / expected (lame ruby queue.pop)
        end
      end # thread
    end # worker_threads

    worker_threads.map { |t| t.join if t } # wait for all threads to complete

    # total and print a summary
    summary = Hash.new(0)
    summary['total'] = status_map.count
    status_map.each { |_k, v| summary[v] += 1 } # total up success/fail
    log "All threads done, summary: #{summary}"

    raise first_error if first_error # re-raise
  end # create_content_runtime

  def test_templates(&closure)
    #raise "Repository does not have '/environments' directory!  Ensure this is a template repository."\
    #  unless Dir.exist?("environments")

    # run closure to fetch list of templates to test
    template_files = yield closure
    # filter to TF template directories
    tf_dirs = template_files.collect { |file| file.sub(/\/terraform\/.*$/, "/terraform/") }.uniq

    if tf_dirs.empty?
      log("No modified templates detected, skipping tests.", 33)
      return
    end

    install_template_runner_deps # install deps

    # iterate through all the template directories, and launch a test for each
    Dir.mktmpdir('secret_vars') do |secret_vars_dir|
      # download and decrypt secret variables
      #stage_secretvars(
      #  secret_vars_dir,
      #  ENV.fetch('DOCKER_REGISTRY'),
      #  ENV.fetch('DOCKER_REGISTRY_USER'),
      #  ENV.fetch('DOCKER_REGISTRY_PASS'),
      #  ENV.fetch('ARCHIVE_PASSWORD')
      #)

      current_branch = my_branch # current git-branch name
      work_queue = Queue.new
      tf_dirs.each { |tf_dir| work_queue.push(tf_dir) }
      status_map = {}
      first_error = nil
      worker_threads = (1..[15, tf_dirs.size].min).map do |thread_num| # max 15 threads
        next if first_error # quick exit if already failures
        log "Spawning worker thread ##{thread_num} in #{thread_num+1} seconds..."
        sleep(thread_num+1) # sleep thread_num seconds -- delays new threads with backoff
        Thread.new do
          begin
            log "Worker thread #{thread_num} started."
            while tf_dir = work_queue.pop(true) # rubocop:disable Lint/AssignmentInCondition
              begin
                if first_error
                  log "Not running test for #{tf_dir}, due to earlier errors.", 33
                  status_map[tf_dir] = "skipped"
                  next
                end # if first_error

                log "Executing test_tf_dir for #{tf_dir}..."
                log "Executing test_tf_dir branch #{current_branch}..."
                log "Executing test_tf_dir secrets #{secret_vars_dir}..."

                test_tf_dir(tf_dir, current_branch, secret_vars_dir)
                log "OK: #{tf_dir}"
                status_map[tf_dir] = "success"
              rescue StandardError => e
                log "ERROR: test_tf_dir failed for #{tf_dir}.  Cause: #{e}", 31
                first_error = e unless first_error
                status_map[tf_dir] = "fail"
              end # rescue
            end # while
          rescue ThreadError => te
            log "Worker thread ##{thread_num} terminating: #{te}" # ok / expected (lame ruby queue.pop)
          end
        end # thread
      end # worker_threads

      worker_threads.map { |t| t.join if t } # wait for all threads to complete

      # total and print a summary
      summary = Hash.new(0)
      summary['total'] = status_map.count
      status_map.each { |_k, v| summary[v] += 1 } # total up success/fail
      log "All threads done, summary: #{summary}"

      raise first_error if first_error # re-raise
    end # mktmpdir
  end # test_templates

  # Rake task that finds modified TF templates and executes them in CAMaaS/Orpheus
  task :test_modified_templates do
    next unless ENV['TRAVIS_EVENT_TYPE'] == 'pull_request' # only in Travis PR builds
    log "orpheus:test_modified_templates starting..."

    # test templates that are modified in the pull-request branch
    test_templates do
      # --diff-filter=AMRd : Include (Added/Modified/Rename), Exclude (Deleted)
      `git diff --name-only --diff-filter=AMRd HEAD^`.split.select do |file|
         file.end_with?(".tf") && file.include?("/terraform/")
      end # split.select
    end # test_templates

    log "orpheus:test_modified_templates successful."
  end # :test_modified_templates

  # Rake task that finds ALL TF templates and executes them in CAMaaS/Orpheus
  # Requires the following environment variables to be set:
  #  For downloading tf-secretvars.zip.gpg file from Artifactory server
  #    DOCKER_REGISTRY      : OpenContent Articatory server
  #    DOCKER_REGISTRY_USER : Artifactory user account
  #    DOCKER_REGISTRY_PASS : Artifactory user's password / token
  #  For decrypting the tf-secretvars.zip.gpg file
  #    ARCHIVE_PASSWORD     : GPG decryption password
  desc 'Finds / Test all TF templates against CAMaaS'
  task :test_all_templates do
    log "orpheus:test_all_templates starting..."

    # test all templates
    test_templates do
      Dir.glob("**/terraform/**/*.tf")
    end # test_templates

    log "orpheus:test_all_templates successful."
  end # :test_modified_templates

  desc 'Create Content Runtimes - pass in CAM URL'
  task :create_content_runtimes, [:camurl] do |_t, args| 
    log "orpheus:create_content_runtimes starting..."
    camurl = args[:camurl]
    log "CAM URL is:  #{camurl}"
    ENV.store("cam_url", camurl)
    create_content_runtime do
      Dir.glob("**/content_runtime_template/**/*.tf")
    end

    log "orpheus:create_conent_runtimes successful"
  end

  # Helper task because this properly loads the python classes which don't get loaded when calling directly
  desc 'Create cloud connections on the specified CAM environment'
  task :create_cloud_connections, :camenv do |_t, args|
    log "orpheus:create_cloud_connections starting..."
    camenv = args[:camenv]
    log "CAM IP Addres:  #{camenv}"
    # Update the IP address to point to your CAM instance
    cmd = "time python tasks/template_runner_local/create_cloud_connections.py -c #{camenv}"
    log "local command: #{cmd}"
    sh "export PYTHONWARNINGS='ignore' && #{cmd}"
    log "orpheus:create_cloud_connections successful"
  end

end # :orpheus
