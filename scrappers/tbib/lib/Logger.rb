class Logger
	def initialize() @l = 0 end

	def fatal(t) puts("[  #{'fatal'.red}  ] #{Time.now.asctime} : #{t}") end

	def error(t) puts("[  #{'error'.cyan}  ] #{Time.now.asctime} : #{t}") end

	def log(t) puts("[   #{'log  '.green} ] #{Time.now.asctime} : #{t}") end

	def warn(t) puts("[  #{'warning'.yellow}] #{Time.now.asctime} : #{t}") end

	def progress(t, per)
		print ' ' * @l + "\r"
		a = "[#{'progress'.blue} ] #{Time.now.asctime} : #{t} [#{'█' * (per*10).to_i}]#{(per*100).to_i}%\r"
		@l = a.length
		print a
	end
end