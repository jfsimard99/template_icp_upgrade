# Copyright IBM Corp. 2017, 2018
require 'git'
require 'yaml'
require 'English' # For Rubocop $CHILD_STATUS whining
require 'json'

# Returns the current branch name
# @return [String] current branch name
def my_branch
  current_branch = ENV['TRAVIS_BRANCH']
  unless current_branch
    g = Git.open('.')
    current_branch = g.current_branch
  end
  # The ravis tag builds do not have the branch set, make it be the master
  if ENV['TRAVIS_BRANCH'] == "publish" && ENV['TRAVIS_TAG'] == "publish"
    current_branch="master" # Set the correct publishing branch to master
  end
  current_branch # return
end #: my_branch

# Returns the current branch name
# @return [String] current branch name

def current_branch
  pr_api="https://github.ibm.com/api/v3/repos/#{ENV['TRAVIS_REPO_SLUG']}/pulls/#{ENV['TRAVIS_PULL_REQUEST']}".freeze
  git_token=(ENV['GIT_TOKEN']).to_s.freeze
  header1='-H "Content-Type: application/json"'.freeze
  header2=format('"Authorization: token %s"', git_token)
  header3=format('-H %s', header2)
  log "curl -L #{header1} #{header3} #{pr_api}"
  current_branch_ref = `curl -L #{header1} #{header3} #{pr_api}`
  current_branch = JSON.parse(current_branch_ref)['head']['ref']
  current_branch
end

# Returns the current repository name
# @return [String] Current repository name

def current_repo_name
  repo_name = %x( basename `git rev-parse --show-toplevel` )
  raise "#{pwd} is not a git repository!" unless $CHILD_STATUS == 0
  repo_name.strip # return
end # end current_repo_name


# Helper utility that logs and raises an error with msg
# @param msg [String] error message

def log_raise_error(msg)
  log(msg, 31)
  raise msg
end

# Logic to determine if metadata version checks should be executed
# Two main cases:
#   1) If on developer laptop: then only run version checks against feature branches
#   2) If in Travis: then only run version checks on PR to `development` branch

def run_version_checks?
  current_branch = my_branch # current branch
  if ENV['TRAVIS_EVENT_TYPE'].nil?
    # We are on a developer box (not in Travis): only run version checks if in a feature branch
    return false if ["development", "test", "master"].include? current_branch
    return true # feature brach: run version checks
  else
    # we are in Travis, only run version checks if PR into development
    puts "*** current_branch: [#{current_branch}]"
    puts "*** TRAVIS_EVENT_TYPE nil?: [#{ENV['TRAVIS_EVENT_TYPE'].nil?}]"
    puts "*** TRAVIS_EVENT_TYPE: [#{ENV['TRAVIS_EVENT_TYPE']}]"
    puts "*** TRAVIS_BRANCH: [#{ENV['TRAVIS_BRANCH']}]"
    puts "*** TRAVIS_PULL_REQUEST: [#{ENV['TRAVIS_PULL_REQUEST']}]"
    puts "*** TRAVIS_PULL_REQUEST_BRANCH: [#{ENV['TRAVIS_PULL_REQUEST_BRANCH']}]"

    if ENV['TRAVIS_EVENT_TYPE'] == 'pull_request' && ENV['TRAVIS_BRANCH'] == 'development'
      puts "Will run version checks."
      return true # PR to Dev: run checks
    else
      puts "Not running version checks."
      return false # no checks
    end
  end
end # run_version_checks

# Utility for console logging
#
# @param msg [String] The message to log
# @option color [Integer] Console escape code to control color
# @see https://en.wikipedia.org/wiki/ANSI_escape_code#Colors

def log(msg, color = 32)
  # log message with Timestamp prefix.
  puts "\e[34m#{Thread.current.object_id}\e[0m:#{Time.new.getutc}: \e[#{color}m#{msg}\e[0m"
end # end log


# Clones a repository from CAMHub
#
# @param repo_clone_url [String] Repository clone URL
# @param access_token [String] OAuth access token to CAMHub
# @param target_dir [String]

def clone_remote_repo(repo_clone_url, access_token, target_dir)
  full_clone_url =
    repo_clone_url.sub 'https://', "https://#{access_token}:x-oauth-basic@"

  log "Cloning repo from #{repo_clone_url} locally to #{target_dir}..."
  `git clone #{full_clone_url} #{target_dir}`
  raise "!!! git-clone operation failed.  #{repo_clone_url} #{target_dir}" \
    unless $CHILD_STATUS == 0
  Dir.chdir(target_dir) do
    log "Cloned.  Validating..."
    `git fsck`
    raise "!!! git-fsck failed in #{target_dir}" unless $CHILD_STATUS == 0
    log "Verified.  Compacting..."
    `git gc --aggressive`
    raise "!!! git-gc failed in #{target_dir}" unless $CHILD_STATUS == 0
    log "Compacted."
  end
end # end: clone_remote_repo

# switches to desired branch and runs closure
# @param branch [String] The GIT branch name to switch to
# @param closure [Ruby block/closure] Code to execute while in branch

def with_branch(branch, &closure)
  g = Git.open('.')
  current_branch = g.current_branch
  begin
    # try to stsh changes (keep track if nothing stashed)
    stashed = (`git stash`.strip != "No local changes to save") # stash any uncommitted changes
    g.checkout(branch)
    return yield closure
  ensure
    g.checkout(current_branch)
    # pop stash if done prior
    `git stash pop` if stashed # unstash changes
  end
end

# runs closure within specified branch of full-clone of the repo
#  * if running locally (not in travis), no cloning is done
#  * if running in Travis, a git-clone is done, and operations performed within
#    the temporary clone'd repository
#
# Once inside the correct git-repository:
#   stashes changes, switches to desired branch, and executes the closure
# original environment is restored before returning & temporary files deleted
# @param branch [String] The GIT branch name to switch to
# @param closure [Ruby block/closure] Code to execute while in branch

def with_repo_clone(branch, &closure)
  # if running local, then we can just run the closure code as-is
  if ENV['TRAVIS_EVENT_TYPE'].nil?
    with_branch(branch) do
      return yield closure
    end
  end

  # we are in Travis (detached state) -- clone the entire repo and fetch from there
  g = Git.open('.')
  Dir.mktmpdir('temprepo') do |staging_dir|
    # clone the repo into the temporary staging directory
    clone_remote_repo(g.remotes[0].url, nil, staging_dir)
    Dir.chdir(staging_dir) do
      # switch to the staged repo, and execute closure in proper branch
      with_branch(branch) do
        return yield closure
      end
    end # chdir
  end # mktmpdir
end # with_repo_clone

# Utility that verifies
# @param filenames [List of String] List of filenames.  Relative and absolute OK
# @param error_msg [String] Error message for user if validation fails
# @param closure [Ruby block/closure] Code to execute that generates filenames

def verify_files_match_after_action(filenames, error_msg, &closure)
  require 'tempfile'
  # Make tempoary copy of specified files, and keep track in hash
  files_map = {}
  filenames.each do |filename|
    # sanity checks
    raise "!!! Do not pass the same filename more than once: #{filename}." if files_map.key?(filename)
    raise "!!! File does not exist: #{filename}. #{error_msg}" unless File.exist?(filename)

    # create Tempfile, save reference in the Map/Hash, and make a copy of the original file
    files_map[filename] = Tempfile.new(filename.split('/')[-1])
    FileUtils.copy(filename, files_map[filename].path)
  end # end for

  # Run their closure and verify the files were not modified
  begin
    yield closure # run the closure
    # verify all file contents
    filenames.each do |filename|
      next if FileUtils.identical?(filename, files_map[filename].path) # continue if files same
      system("diff -uBw #{filename} #{files_map[filename].path}")
      next if $CHILD_STATUS == 0
      diff_output = `diff -u #{filename} #{files_map[filename].path}`
      log("!!! Verification failed for #{filename}\n#{error_msg}.\n\ndiff output:\n#{diff_output}", 31)
      raise "!!! Verification failed for #{filename}: #{error_msg}."
    end # end for
  ensure
    # cleanup all tempfiles (restore original copies)
    filenames.each do |filename|
      temp_file = files_map[filename]
      FileUtils.copy(temp_file.path, filename) # restore original file
      temp_file.close
      temp_file.unlink # deletes the temp file
    end # end for
  end # end ensure
end # verify_files_match_after_action()

# Parses the '.camhub.yml' file for the repo
# @param options_filename YML Configuration filename
# @return [Hash] Parsed version of YAML document

def load_config(filename)
  return YAML.load_file(filename)
rescue StandardError => e
  log("!!! Issue reading/parsing the #{filename} file: #{e.message}", 31)
  raise
end # end load_config

# Download a file from remote URL
# @param local_filename [String] abs filename of file to write to
# @param url [String] URL of remote file
# @param user [String] basic-auth username
# @param pass [String] basic-auth password
# @param archive_password [String] optional, decrypt GPG passphrase

def fetch_remote_file_url(local_filename, url, user, pass, gpg_passphrase = Nil)
  require 'open-uri'

  File.open(local_filename, "w") do |file|
    file.write(open(url, :http_basic_authentication => [user, pass]).read)
  end

  # decrypt GPG ?
  return unless local_filename.end_with?(".gpg") && gpg_passphrase
  require 'open3'
  _stdout_str, status = Open3.capture2(
    "gpg --passphrase-fd 0 --always-trust #{local_filename}",
    :stdin_data => gpg_passphrase)
  raise "!!! Failed to decrypt #{local_filename}" unless status == 0
end # fetch_file_artifactory

# Update the version base on the previous
# @param in_current_version Current version from the destination source repository
# @param in_new_version The latest version from the source repository
# return the calculated version

def version_calculator(in_current_version, in_new_version)
  current_version = in_current_version.split('.').map(&:to_i)
  new_version = in_new_version.split('.').map(&:to_i)
  if new_version[0] == 0
    new_version = 1
  end
  if current_version.join('.') == "0.0.0"
    current_version[0] =  if new_version[0] != 0
      new_version[0]
                          else
      1
                          end
  elsif current_version[0] == new_version[0]
    if current_version[1] == new_version[1]
      current_version[2] += 1
    else
      current_version[2] = 0
      current_version[1] += 1
    end
  else
    current_version[2] = 0
    current_version[1] = 0
    current_version[0] += 1
  end
  puts current_version.join('.')
  r_version = current_version.join('.')
  r_version
end # version calculator

# Update_Files will update the metadata.rb file
# @param search_path The path to find the metadata file
# @param update_version The new version to update the file
# @param old_version The older version used for the search to find the line in the file

def update_metadata_files(search_path, update_version, old_version)
  metadata_file_paths = []
  Find.find(search_path) do |path|
    metadata_file_paths << path if path =~ /.*metadata\.rb$/
  end
  return if metadata_file_paths.empty?
  # Found a file
  data = File.read(metadata_file_paths[0])
  new_data = data.gsub("version '"+old_version+"'", "version '"+update_version+"'")
  File.open(metadata_file_paths[0], "w") do |f|
    f.write(new_data)
  end
  log metadata_file_paths[0] + " file updated with " + update_version
end

# Update catalogue files with the corresponding github version
# It is assumed that the version is 1.0, it this changes, we need to add a parameter here
# @param search_path The path to find the catalog files
# @param update_version The version which we want to update

def update_catalog_files(search_path, update_version)
  catalog_file_paths = []
  Find.find(search_path) do |path|
    catalog_file_paths << path if path =~ /.*catalog\.json$/
  end
  Find.find(search_path) do |path|
    catalog_file_paths << path if path =~ /.*camtemplate\.json$/
  end
  return unless catalog_file_paths.empty?
  catalog_file_paths.each do |catalog_file|
    # Found a file
    data = File.read(catalog_file)
    # new_data = data.gsub("version '"+old_version+"'", "version '"+update_version+"'")
    new_data = data.gsub('"description": "1.0', '"description": "' + update_version)
    new_data = new_data.gsub('"version": "1.0"', '"version": "' + + update_version + '"')
    File.open(catalog_file, "w") do |f|
      f.write(new_data)
    end # end write
    log catalog_file + " file updated with " + update_version
  end # end for
end # end method
