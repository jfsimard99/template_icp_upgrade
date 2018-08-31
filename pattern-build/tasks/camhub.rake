# Copyright IBM Corp. 2017, 2018

namespace :camhub do

  require 'fileutils'
  require 'git'       # https://github.com/schacon/ruby-git
  require 'octokit'   # https://github.com/octokit/octokit.rb
  require 'English'   # For Rubocop $CHILD_STATUS whining
  require './tasks/utils.rb'

  # Rake task that publishes git respository to CAMHub
  desc 'publishes git repository to CAMHub'
  task :publish => [:verify_license_file] do
    log "CAMHub:publish starting."

    options = load_config('.camhub.yml')
    # determine which branch, and verify its configuration
    branch = verify_branch(options['cam_hub'])

    camhub_host = options['cam_hub'][branch]['hostname'].strip
    camhub_org = options['cam_hub'][branch]['org_name'].strip
    master_publish = options['cam_hub'][branch]['master_publish']
    publish_branch = options['cam_hub'][branch]['publish_branch']
    # fetch the camhub access_token from the environment settings
    camhub_access_token = ENV.fetch(camhub_host.tr('.', '_').upcase+"_ACCESS_TOKEN").strip

    repo_name = current_repo_name
    git_tag = calc_git_tag(options['git_tag'])

    log "Publishing repository #{camhub_org}/#{repo_name} #{publish_branch} with tag: #{git_tag} to #{camhub_host}..."

    # Create the repo repository (or just get the details if it already exists)
    camhub_repo_sawyer = create_remote_repo(
      camhub_host, camhub_access_token, camhub_org,
      repo_name, options['repo_options'])

    # create temporary staging directory, and perform clone/update operations
    Dir.mktmpdir(repo_name) do |staging_dir|
      clone_remote_repo(camhub_repo_sawyer.clone_url, camhub_access_token, staging_dir)
      stage_files(staging_dir, options['excludes'])
      commit_tag_push(
        staging_dir, git_tag,
        "Automated CAMHub::publish on #{Time.new.getutc}", master_publish, publish_branch)
    end
    log "CAMHub:publish done."
  end # end task :publish

  # verifies that the branch is defined in '.camhub.yml'.  Raises error if not.
  # @param camhub_options The 'cam_hub' options section from .camhub.yml
  def verify_branch(camhub_options)
    require './tasks/utils.rb'

    current_branch = my_branch # my_branch() from utils.rb
    unless camhub_options[current_branch]
      msg = "I don't think you really want me to push branch '#{current_branch}'"\
        " to CAMHub!  If you really want to do this then configure the 'cam_hub'"\
        " section in .camhub.yml for this branch."
      log(msg, 31)
      raise msg
    end
    current_branch # return
  end # end: verify_branch

  # Returns the git-tag to use for the push to CAMHub
  # @param git_tag_opts [Hash] The 'git_tag' options
  # @return [String] the git_tag (may be nil)

  def calc_git_tag(git_tag_opts)
    git_tag = nil
    if git_tag_opts && git_tag_opts['ruby_eval']
      # log "Evaluating for git-tag: #{git_tag_opts['ruby_eval']}"
      git_tag = instance_eval(git_tag_opts['ruby_eval']).strip
    else
      log("No git_tag configuration defined.", 33)
    end

    # Enforcing semantic versioning if the option is enabled
    # see: http://semver.org/
    if git_tag_opts && (git_tag_opts['enforce_semver'].nil? || git_tag_opts['enforce_semver'])
      if git_tag.nil? || git_tag.empty?
        msg = "git_tag/enforce_semver: git-tag is nil or empty."
        log msg, 31
        raise msg
      end

      # Let GEM::Version test the tag (raises Error is not formatted correctly)
      Gem::Version.new(git_tag)
    end
    git_tag # return
  end

  # Returns the V.R of the git tag
  # Input the V.R.M tag

  def calc_vr_tag(in_vrm_tag)
    vr_tag = in_vrm_tag.split('.').take(2).join('.')
    log "Here is the VR tag : " + vr_tag
    vr_tag # return the VR tag to be used
  end

  # Create the remote repository if it does not already exist, no-op otherwise.
  #
  # @param host [String] CAMHub hostname
  # @param token [String] CAMHub access token
  # @param org [String] CAMHub organization name
  # @param repo [String] Git repository name
  # @param repo_options GitHub/GHE repository options
  # @return [Sawyer::Resource] Repository info for the repository
  # @see https://developer.github.com/v3/repos/#create

  def create_remote_repo(host, token, org, repo, repo_options)
    client = create_camhub_client(host, token)
    # create the repository if it doesn't already exist
    log "Checking existing repo in #{org}..."
    unless client.repository?(org + "/" + repo)
      repo_options[:organization] = org
      log "Repo does not exist #{org}/#{repo}, creating with options: #{repo_options}..."
      client.create_repository(repo, repo_options)
      log("New #{org}/#{repo} repository created.")
    end

    log "Fetching repository details..."
    client.repository(org + "/" + repo) # return
  end # end create_remote_repo


  # Creates the Octokit client to CAMHub/GitHub
  #
  # @param camhub_host [String] The hostname for CAMHub (ie: github.com)
  # @param camhub_access_token [String] The OAuth token for CAMHub
  # @return [Octokit::Client] Octokit client to CAMHub

  def create_camhub_client(camhub_host, camhub_access_token)
    Octokit.reset!

    unless "github.com".casecmp(camhub_host) == 0
      # GitHub Enterprise support
      Octokit.configure do |c|
        c.api_endpoint = "https://#{camhub_host}/api/v3/"
      end
    end

    client = Octokit::Client.new(:access_token => camhub_access_token)
    log "Logging into #{camhub_host}..."
    log "Logged in as: "+client.login
    client # return
  end # end create_camhub_client

  # Stage files into the local target repository directory
  # WARNING: This function deletes contents of target_dir
  #
  # @param target_dir [String] Should be a local CAMHub clone
  # @param excludes [List] Exclusion list for '--exclude' TAR options

  def stage_files(target_dir, excludes)
    # Wipe the staging directory, only leaving the .git/ directory
    Dir.chdir(target_dir) do
      files_to_delete = Dir.glob("*", File::FNM_DOTMATCH).reject do |file|
        file.match '^(\.|\.\.|\.git)$' # reject: ., .., .git
      end
      FileUtils.rm_r files_to_delete # delete all files not rejected
    end

    # always want the .gitignore (if it exists)
    if File.file?('.gitignore')
      FileUtils.cp('.gitignore', target_dir)
      open(File.join(target_dir, '.gitignore'), 'a') do |f|
        f.puts ".gitignore" # ensure this entry is in .gitignore
      end
    end

    # add required exclusion entries so that these files never make it into CAMHub
    # Do NOT add additional entries here, use .camhub.yml `excludes` list instead
    excludes << ".gitignore" << ".camhub.yml" << ".travis.yml" << ".gitattributes"

    # use tar/untar [with exclusion lists] to copy files to the target_dir
    tar_excludes = ""
    excludes.each { |exclude| tar_excludes << " --exclude='#{exclude}'" } if excludes
    `tar --exclude-vcs #{tar_excludes} -cf - . | tar -C #{target_dir} -xf -`
    raise "!!! Failed to TAR/UNTAR repository." unless $CHILD_STATUS == 0
  end # end stage_files

  # Commit, Tag, and Push staged repository to CAMHub
  # @param local_repo_dir [String] the local repo directory ready to push to CAMHub
  # @param tag [String] Tag string for the push.  May be nil or blank.
  # @param msg [String] The git commit message
  # @param version_update Boolean to indicate if the version should be update based on the content of git

  def commit_tag_push(local_repo_dir, tag, msg, version_update, determine_branch)
    g = Git.open(local_repo_dir)
    g.config('user.name', 'CAMHub PublishBot') # commits from this non-existent user
    g.config('user.email', 'octravis@us.ibm.com') # added for Jenkins issue2071
    g.add(:all=>true)
    if version_update && version_update == true
      begin
        current_tags = g.tags
        current_tag = if current_tags.nil? || current_tags.empty?
                        "0.0.0"
                      else
                        current_tags = current_tags.sort_by { |v| Gem::Version.new(v.name) }
                        current_tags[(current_tags.length - 1)].name
                      end
      rescue Git::GitExecuteError
        current_tag = "0.0.0"
      end
      the_version = version_calculator(current_tag, tag)
      the_vr_version = calc_vr_tag(the_version)
      log "Current Tag " + current_tag + ", Development Version : " + tag + ", calculate new: " + the_version + ", the VR version: " + the_vr_version
      update_metadata_files(local_repo_dir, the_version, tag)
      update_catalog_files(local_repo_dir, the_version)
    else
      the_version = tag
    end # Force version update based on the git version, and new version
    branch_name = if determine_branch && determine_branch == "VERSION"
        if determine_branch == "VERSION"
           "v"+the_version
        else
           "determine_branch"
        end
                  else
       "master"
                  end
    # Need to determine if the branch exists
    begin
      g.branch(branch_name).checkout
    rescue Git::GitExecuteError
      log "branch already exists"
    end
    begin
      log "Committing changes as user '#{g.config('user.name')}'..."
      g.commit_all(msg)
      begin
        log "Delete the existing tag: " + the_vr_version
        g.delete_tag(the_vr_version) unless the_vr_version.to_s.blank?
        tagbranch=':refs/tags/'+the_vr_version
        g.push('origin', tagbranch)
      rescue Git::GitExecuteError => te
        log(te.message, 31)
        log "No git tag to remove"
      end # rescue
      g.add_tag(the_version) unless the_version.to_s.blank?
      g.add_tag(the_vr_version) unless the_vr_version.to_s.blank?
      log "Pushing updates..."
      g.push('origin', branch_name, :tags => !the_version.to_s.blank?)
    rescue Git::GitExecuteError => e
      if e.message.include? 'nothing to commit'
        log("There are no changes.  Leaving target repository unmodified.", 33)
        return # explicity return, treat as no-op / OK
      end
      log(e.message, 31)
      raise # re-raise original exception
    end # end rescue
  end # end commit_tag_push

  #Rake Task that Verifies whether any License File is Present or Not
  task :verify_license_file do
    next unless File.exist?('.camhub.yml') # skip if not enabled for camhub publishing
    unless File.exist?('LICENSE') || File.exist?('LICENSE.txt') || File.exist?('LICENSE.md')
	    msg = "camhub:verify_license_file: LICENSE not found.  Ensure LICENSE exists before enabling CAMHub publishing."
	    log(msg, 31)
	    raise msg
    end
    log "camhub:verify_license_file: OK"
  end # :verify_license_file

  # Rake task that verifies that feature branches have different tags than
  # the development branch.  If they are the same, would be considered a build error
  desc 'Verifies the CAMHub publishing tag'
  task :verify_tag => [:verify_license_file] do
    require './tasks/utils.rb'

    if run_version_checks?
      if File.exist?('.camhub.yml')
        current_tag = calc_git_tag(load_config('.camhub.yml')['git_tag'])
        orig_tag = nil
        # clone repo (if necessary) and run within
        with_repo_clone('development') do
          # inside development branch
          begin
            orig_tag = calc_git_tag(load_config('.camhub.yml')['git_tag'])
          rescue Errno::ENOENT
            log "'development' branch does not contain '.camhub.yml', ignoring...", 33
          end
        end # with_repo_clone

        log "Old version: #{orig_tag}"
        log "New version: #{current_tag}"
        if current_tag && orig_tag && current_tag == orig_tag
          msg = "!!! '.camhub.yml' options for 'git_tag' results in same value "\
            "(#{orig_tag}) as in the 'development' branch. "\
            " Ensure that the version number for your feature branch "\
            "is different."
          log(msg, 31)
          raise msg
        end # if tags same
      end # .camhub.yml exist?
    end # if run_version_checks?
  end # :verify_tag


  # Invokes Pattern-Manager's 'upload/chef/git_hub' API
  # @param public_ip [String] the IP address for Pattern-Manager microservice
  # @param camhub_host [String] CAMHub hostname or IP
  # @param camhub_org [String] CAMHub organization name
  # @param camhub_access_token [String] CAMHub authentication token
  def pm_upload_chef_github(public_ip, pm_auth_token, camhub_host, camhub_org, camhub_access_token)
    require 'net/http'
    require 'uri'

    log "Invoking pattern-manager API at #{public_ip}, to sync with #{camhub_org} "\
        "at #{camhub_host}..."

    uri = URI.parse("https://#{public_ip}:5443/v1/upload/chef/git_hub")
    request = Net::HTTP::Post.new(uri.request_uri, 'Content-Type' => 'text/json')
    request.add_field('Authorization', "Bearer #{pm_auth_token}")
    request.body =
      { "authorization" => { "personal_access_token" => camhub_access_token },
        "github_hostname" => camhub_host,
        "org" => camhub_org,
        "repos" => "cookbook_.*" }.to_json

    response = Net::HTTP.start(
      uri.host, uri.port,
      :read_timeout => 240, # in seconds
      :use_ssl => uri.scheme == 'https',
      :verify_mode => OpenSSL::SSL::VERIFY_NONE) do |https|
        https.request(request)
    end

    if response.code.to_i < 200 || response.code.to_i > 299
      msg = "!!!Bad response #{response.code}!  #{response.body.gsub(/\\n/, "\n")}"
      log(msg, 31)
      raise msg
    end

    log "Success #{response.code} #{response.body.gsub(/\\n/, "\n")}"
  end


  # Loads the environs.yml from Artifactory

  def load_environs_conf(artifactory_host, artifactory_user, artifactory_token, archive_password)
    log "Loading environs.yml configuration from #{artifactory_host}..."
    # load the environs.yml config file from artifactory
    environs = nil
    Dir.mktmpdir('environs') do |temp_dir|
      # download and decrypt GPG
      fetch_remote_file_url(
        File.join(temp_dir, 'environs.yml.gpg'),
        "https://#{artifactory_host}/artifactory/orpheus-local-generic/opencontent/labs/environs.yml.gpg",
        artifactory_user, artifactory_token, archive_password)

      environs = load_config(File.join(temp_dir, 'environs.yml')) # load config
    end

    environs # return
  end


  # Rake task to syncrhonize the development/test environment(s) with the content
  # published in CAMHub
  desc 'Synchronization development/test environments with CAMHub'
  task :env_cookbook_sync do

    options = load_config('.camhub.yml') # .camhub.yml config
    # determine which branch, and verify its configuration
    branch = verify_branch(options['cam_hub'])

    camhub_host = options['cam_hub'][branch]['hostname'].strip
    camhub_org = options['cam_hub'][branch]['org_name'].strip
    # fetch the camhub access_token from the environment settings
    camhub_access_token = ENV.fetch(camhub_host.tr('.', '_').upcase+"_ACCESS_TOKEN").strip

    # load the environs.yml file from artifactory
    environs = load_environs_conf(
      ENV.fetch('DOCKER_REGISTRY'),
      ENV.fetch('DOCKER_REGISTRY_USER'),
      ENV.fetch('DOCKER_REGISTRY_PASS'),
      ENV.fetch('ARCHIVE_PASSWORD')
    )

    if environs && environs[branch]
      environs[branch].each do |env, value|
        log "Sync'ing #{branch} environment #{env} ..."
        # call pattern-manager to load cookbooks
        pm_upload_chef_github(
          value['ip_addr'],
          value['pm_auth_token'],
          camhub_host,
          camhub_org,
          camhub_access_token)
      end # environs each
    end # end if environs[branch] exists
  end # :env_cookbook_sync

end # end :camhub
