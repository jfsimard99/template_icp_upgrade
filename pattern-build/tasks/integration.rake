# Copyright IBM Corp. 2017, 2018
namespace :integration do
  def randompass
    (0...12).map { (65 + rand(26)).chr }.join.downcase
  end

  # generate random strings as passwords for chef-vault jsons 
  def generate_random_passwords
    require 'erubis'
    # find .json.erb under test/integration
    Dir['test/integration/default/data*bag*/**/*.json.erb'].each do |template|
      words = File.foreach(template).grep(/randomstring/i).map { |l| l.split('<%=')[1].split('%>')[0].strip }
      parole = Hash[words.collect { |v| [v, randompass] }].each_with_object({}) { |p, k| k[p[0].to_sym] = p[1] }
      jtmpl = Erubis::Eruby.new(File.read(template))

      p "Generating random passwords in #{template}"
      File.open(File.join(File.dirname(template),
                          File.basename(template, 
                                        File.extname(template))), "w+") do |f|
        f.write(jtmpl.result(parole))
      end
      jtmpl = nil
    end
  end

  # task for random password generation before running integration tests 
  desc 'generate random passwords before integration tests'
  task :passwords do
    generate_random_passwords
  end

  # Utility intended to run integration tests in parallel using kitchen
  desc 'run kitchen test on all VMs in parallel'
  task :parallel_run do
    # Run "kitchen test" only when:
    # - this is a PR to development
    # or:
    # - if no TravisCI var is present - ie we are running in a development box
    next if ENV['TRAVIS_PULL_REQUEST'] == 'false'
    next if ENV['SKIP_INTEGRATION_TEST'] == 'true'
    next unless ENV['TRAVIS_BRANCH'] == 'development' || ENV['TRAVIS_BRANCH'].nil?

    generate_random_passwords

    require 'kitchen'
    Kitchen.logger = Kitchen.default_file_logger(ENV['DEBUG']=='true'? :debug : :info)

    # Use the TEST_CLOUD provided via travis env or run with all clouds (default)
    clouds = ENV['TEST_CLOUD'] ? ENV['TEST_CLOUD'].downcase.split(' ') : %w{sl aws vmw}

    if File.file?("./.kitchen.sl.yml")
      # For SL tests replace DC with one in the list bellow
      dclist=%w{dal05 dal06 dal09 dal10 hou02 mon01 sjc01 sea01 tor01 wdc01 wdc04}
      cfg = YAML.load_file "./.kitchen.sl.yml"
      cfg["driver"]["datacenter"] = dclist.sample
      File.open("./.kitchen.sl.yml", 'w') { |f| YAML.dump(cfg, f) }
    end

    cloud_instances = []
    clouds.each do |c|
      if File.file?("./.kitchen.#{c}.yml")
        cloud_instances.concat(Kitchen::Config.new(loader: Kitchen::Loader::YAML
                          .new(project_config: "./.kitchen.#{c}.yml")).instances)
      end
    end

    begin
      threads = []
      cloud_instances.each { |i| threads << Thread.new { i.test(:passing) } }
      threads.map(&:join)
    rescue
      # TODO: print VM details left up for debbuging if kitchen fail
      p "Error executing test kitchen"
      exit 1
    end
  end

  # Utility intended for developers to run locally/in build engin to 
  # run integration tests using kitchen
  desc 'run kitchen test'
  task :run do
    # Run "kitchen test" only when:
    # - this is a PR to development
    # or:
    # - if no TravisCI var is present - ie we are running in a development box
    next if ENV['TRAVIS_PULL_REQUEST'] == 'false'
    next if ENV['SKIP_INTEGRATION_TEST'] == 'true'
    next unless ENV['TRAVIS_BRANCH'] == 'development' || ENV['TRAVIS_BRANCH'].nil?

    generate_random_passwords

    require 'kitchen'
    Kitchen.logger = Kitchen.default_file_logger
    @loader = Kitchen::Loader::YAML.new(project_config: './.kitchen.yml')
    config = Kitchen::Config.new(loader: @loader)
    config.instances.each do |instance|
      instance.test(:always)
    end
  end
end
