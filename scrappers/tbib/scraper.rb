raise 'missing gems.txt!' unless File.exist? 'gems.txt'
File.open('gems.txt', 'r').read.split("\n").each { |x| require x }
Dir['lib/*.rb'].each { |x| require_relative x }
$log = Logger.new

Config = Struct.new(:server_ip, :server_port, :save_path, :name, :database, :table, :tags) do
	def info
		ret = "\n"
		[[server_port, 'Server Port'],
		[server_ip, 'Server IP'],
		[save_path, 'Save Path'],
		[name, 'Name'],
		[database, 'Database'],
		[table, 'Table'],
		[tags, 'Tags']].each do |t|
			a = t[0]
			b = t[1]
			ret << " * #{b}: #{a.is_a?(Array) ? a.to_s : a}\n"
		end
		ret
	end

	def verify!
		marr = []
		[[server_port, 'Server Port'],
		[server_ip, 'Server IP'],
		[save_path, 'Save Path'],
		[name, 'Name'],
		[database, 'Database'],
		[table, 'Table'],
		[tags, 'Tags']].each do |t|
			if t[0].nil?
				marr << "Value '#{t[1]}' is missing from the configuration file!"
			end
		end
		marr.each { |x| $log.fatal(x) }
		exit 1 if marr.length > 0
	end
end

$config = Config.new nil, nil, nil, nil, nil

has_config = false

OptionParser.new do |ops|
	ops.banner = 'Usage: ruby scraper.rb [options]'

	ops.on('-h', '--help', 'Prints this text.') do
		puts ops
		exit 0
	end

	ops.on('-d', '--default-config', 'Outputs the default configuration sheet to stdout.') do
		puts TOML::Generator.new({
			:general => {
					:name => 'tbib-rb',
					:tags => ['dark_elf']
				},
			:rethink => {
					:address => 'localhost',
					:port => 28015,
					:db => 'imageboard_indexer',
					:table => 'tbib'
				},
			:images => {
				:path => 'images/'
			}
		}).body
		exit 0
	end

	ops.on('-cPATH', '--config=PATH', 'Specifies a configuration file the scraper should load.') do |c|
		if !File.exist? c
			$log.fatal "File '#{c}' does not exist!"
			exit 1
		end

		TOML.load_file(c).tap do |toml|
			$config.server_ip = toml['rethink']['address']
			$config.server_port = toml['rethink']['port']
			$config.save_path = toml['images']['path']
			$config.name = toml['general']['name']
			$config.database = toml['rethink']['db']
			$config.table = toml['rethink']['table']
			$config.tags = toml['general']['tags']
		end
		$config.verify!
		$log.log "Set configuration according to #{c}!"
		$log.log $config.info
		has_config = true
	end
end.parse!

unless has_config
	$log.fatal 'No configuration specified, use --help for details.'
	exit 1
end

Tbib.new.start!
