# coding: utf-8
require "bundler"

Bundler.setup(:default)

require "sinatra/base"
require "sinatra/reloader"
require "sinatra/streaming"

require "json"

require "rethinkdb"
include RethinkDB::Shortcuts


class Indexer < Sinatra::Base
  set server: 'thin'

  helpers Sinatra::Streaming

  set :root, __dir__ + "/.."
  set :views, __dir__ + "/../html"
  set :stream_connections, []

  def initialize
    @conn = r.connect()
    @conn.use("imageboard_indexer")

    Thread.new do
      loop do
        settings.stream_connections.each do |conn|
          conn << "data: test data \n\n"
        end
        sleep 3
      end
    end

    super
  end

  get "/" do
    slim :index
  end

  get "/get_images", provides: "text/json" do
    offset = params.fetch(:offset, 0)
    limit = params.fetch(:limit, 25)

    r.table("safebooru").limit(limit).skip(offset).run(@conn).to_a.to_json
  end

  get "/new_images", provides: "text/event-stream" do
    stream :keep_open do |out|
      settings.stream_connections << out

      out.callback do
        settings.stream_connections.delete(out)
      end
    end
  end
end

Indexer.run!
