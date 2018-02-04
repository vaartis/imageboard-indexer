class Tbib
	include RethinkDB::Shortcuts

	def initialize()
		@conn = r.connect(:host => $config.server_ip, :port => $config.server_port)
		$log.log 'connected to database!'
		@conn.use($config.database)
		@mutex = Mutex.new
		if !r.table_list.run(@conn).include?($config.table)
			r.table_create($config.table).run(@conn)
			$log.log "Created table #{$config.table} at #{$config.db}."
		else
			$log.log "Table #{$config.table} already exists."
		end
	rescue => e
		$log.fatal("Could not connect to database on #{$config.server_ip}:#{$config.server_port}!")
		$log.fatal(e)
		exit 1
	end

	def start!
		url2 = "https://tbib.org/index.php?page=dapi&s=post&q=index&tags=#{$config.tags.join('+')}"
		$log.log "Connecting to tbib..."
		xml = open(url2).read
		c = Nokogiri.XML(xml).xpath('//posts').first['count'].to_i
		$log.log "Total number of images is: #{c}"
		if c == 0
			$log.error 'No results.'
			exit 0
		end
		images = []
		procs = []
		(0..(c/100 + (c%100 == 0 ? 0 : 1))).to_a.each do |pid|
			procs << proc {
				Thread.new do
					url = "https://tbib.org/index.php?page=dapi&s=post&q=index&tags=#{$config.tags.join('+')}&json=1&pid=#{pid}"
					j = JSON.parse(open(url).read)
					@mutex.synchronize do
						images += j
					end
				end
			}
		end
		ol = procs.length.to_f
		while !procs.empty?
			$log.progress "Downloading images...", 1.0 - procs.length.to_f/ol
			b = procs.shift(8)
			b.each_with_index { |d, i| b[i] = d.call }
			b.each { |d| d.join }
			sleep 1
		end
		$log.progress "Done.", 1.0
		puts ''

		$log.log "Number of images looted: #{images.length}"

		r.table($config.table).insert(images.inject([]) do |sum, x|
			sum << {
				'id' => x['id'],
				'height' => x['height'],
				'width' => x['width'],
				'score' => x['score'],
				'name' => x['image'],
				'extension' => x['image'].split('.').last,
				'originalPost' => "https://tbib.org/index.php?page=post&s=view&id=#{x['id']}",
				'tags' => x['tags'].split(' '),
				'md5' => x['hash'],
				'metadataOnly' => true,
				'originalImage' => "https://tbib.org//images/#{x['directory']}/#{x['image']}?#{x['id']}",
				'originalThumbnail' => "https://tbib.org/thumbnails/#{x['directory']}/thumbnail_#{x['image']}?#{x['id']}"
			}
		end).run(@conn)

		$log.log 'Done.'
	end
end