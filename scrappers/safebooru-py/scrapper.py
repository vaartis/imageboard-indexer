"""
This is a reference implementation of a scrapper, it implements
all the options and should be referenced when unsure about the implentation
of your own scrapper.
"""

import asyncio
import aiohttp
import untangle
import json
import toml

from os.path import splitext, realpath, dirname, join as path_join, isfile, basename
from os import mkdir, listdir
from shutil import copy
from tempfile import NamedTemporaryFile

from concurrent.futures import ThreadPoolExecutor, CancelledError

import rethinkdb as r
r.set_loop_type('asyncio')

import logging
logging.getLogger().setLevel(logging.INFO)

import argparse
epilog_string="""\
Safebooru has a hard limit of 8 connections per IP. Threading
needs to be configured depending on your needs. You want to
set 'other.pages-thread-limit' to limit the pages fetching and
'other.images-thread-limit' to limit the image downloading in your 'config.toml'. The
default is 5 connections for pages and 3 for images.
"""
parser = argparse.ArgumentParser(epilog=epilog_string)
parser.add_argument("-d", "--default-config",
                    help="Dump the default config to stdout and exit",
                    action="store_true",)
parser.add_argument("-c", "--config", help="Specify the config file to use")
args = parser.parse_args()

def merge_dict(d1, d2):
    """
    Modifies d1 in-place to contain values from d2.  If any value
    in d1 is a dictionary (or dict-like), *and* the corresponding
    value in d2 is also a dictionary, then merge them in-place.
    """
    import collections # requires Python 2.7

    for k,v2 in d2.items():
        v1 = d1.get(k) # returns None if v1 has no value for this key
        if ( isinstance(v1, collections.Mapping) and
             isinstance(v2, collections.Mapping) ):
            merge_dict(v1, v2)
        else:
            d1[k] = v2

"""
The following is a configuration interface, it has default
values and uses those from config if there is one
"""

current_dir = dirname(realpath(__file__))

default_config = {
    "general": {
        "name": "safebooru-py",
        "tags": [],
        "blacklisted-tags": [],
        "start": f"python \"{realpath(__file__)}\""
    },
    "rethink": {
        "db": "imageboard_indexer",
        "address": "localhost",
        "port": 28015,
        "table": "safebooru"
    },
    "images": {
        "save-path": path_join(current_dir, "images"),
        "ignore-extensions": ["webm"],
        "metadata-only": False
    }, "other": {
        "pages-thread-limit": 5,
        "images-thread-limit": 3
    }
}

if args.default_config:
    print(toml.dumps(default_config))
    exit()

if args.config:
    config_path = args.config
else:
    config_path = path_join(current_dir, 'config.toml')
config = default_config

if isfile(config_path):
    merge_dict(config, toml.load(config_path))

try:
    mkdir(config["images"]["save-path"])
except FileExistsError:
    pass

if config["images"]["metadata-only"]:
    logging.info("Metadata-only mode enabled, not downloading images")

async def _load_images_impl(conn, cl_session, pages_semaphore, images_semaphore, page):
    """
    The actual implementation of downloading images,
    all parameters are provided by the `load_images` function

    :param conn: Rethinkdb connection
    :param cl_session: aiohttp client session
    :param pages_semaphore: The semaphore to limit simultanious downloads
    :param images_semaphore: The semaphore to limit image downloads
    :param page: A page to download
    """

    async with pages_semaphore:
        async with cl_session.get("https://safebooru.org/index.php",
                                  params={"page": "dapi", "s": "post", "q": "index", "pid": page, "json": 1}) as resp:
            json_resp = json.loads(await resp.text())

            async def _process_the_image(pst):
                image_link = f"https://safebooru.org/images/{pst['directory']}/{pst['image']}"
                image_path = path_join(config['images']['save-path'], pst['image'])

                result = {
                    "id": int(pst['id']),
                    "height": int(pst['height']),
                    "width": int(pst['width']),
                    "score": int(pst['score']),
                    "name": pst["image"],
                    "extension": splitext(pst["image"])[1],
                    "originalPost": f"https://safebooru.org/index.php?page=post&s=view&id={pst['id']}",
                    "tags": pst["tags"].split(" "),
                    "md5": pst["hash"]
                }

                if config["images"]["metadata-only"]:
                    result["metadataOnly"] = True
                    result["originalImage"] = image_link
                    result["originalThumbnail"] = f"https://safebooru.org/thumbnails/{pst['directory']}/thumbnail_{pst['image']}"

                if result["extension"][1:] not in config["images"]["ignore-extensions"]:
                    # Only download images if not in metadata-only mode
                    if not config["images"]["metadata-only"]:
                        if not isfile(image_path):
                            async with images_semaphore:
                                async with cl_session.get(image_link) as image_resp:
                                    with NamedTemporaryFile() as f:
                                        img_data = await image_resp.read()
                                        f.write(img_data)
                                        copy(f.name, image_path)
                    return result
                else:
                    return None


            logging.info(f"Page {page} started")

            posts_for_db = filter(lambda x: x is not None, await asyncio.gather(*[_process_the_image(j) for j in json_resp]))
            await r.table(config["rethink"]["table"]).insert(posts_for_db, conflict="update").run(conn)

            logging.info(f"Page {page} done")

async def load_images(conn, cl_session):
    """
    This function merely counts the number of pages and
    passes it to the `_load_images_imp`, which does the actual downloading.

    :param conn: RethinkDB connection
    :param cl_session: aiohttp client session
    """

    per_page = 100

    async with cl_session.get("https://safebooru.org/index.php",
                              params={"page": "dapi", "s": "post", "q": "index", "limit": 1,
                                      "tags": " ".join(config["general"]["tags"]) + " ".join(map(lambda x: "-" + x, config["general"]["blacklisted-tags"])) }) as resp:
        resp_text = await resp.text()

        total_images = int(untangle.parse(resp_text).children[0]['count'])
        last_page = int(total_images / per_page)

        pages_sem = asyncio.Semaphore(config["other"]["pages-thread-limit"])
        images_sem = asyncio.Semaphore(config["other"]["images-thread-limit"])

        tasks = []
        for pg in range(1, last_page):
            tasks.append(asyncio.ensure_future(_load_images_impl(conn, cl_session, pages_semaphore=pages_sem, images_semaphore=images_sem, page=pg)))

        await asyncio.gather(*tasks)


async def main():
    conn = await r.connect(host=config["rethink"]["address"], port=config["rethink"]["port"])

    # Create the database if it doesn't exist
    if config["rethink"]["db"] not in await r.db_list().run(conn):
        await r.db_create(config["rethink"]["db"]).run(conn)

    conn.use(config["rethink"]["db"])

    # Create a table if it doesn't exist
    if config["rethink"]["table"] not in await r.table_list().run(conn):
        await r.table_create(config["rethink"]["table"]).run(conn)

    # Create the scrapper_info table if it doesn't exist, setting name
    # as a primary key
    if "scrappers_info" not in await r.table_list().run(conn):
        await r.table_create("scrappers_info", primary_key="name").run(conn)

    # Insert or update information about the scrapper
    await r.table("scrappers_info").insert({
            "name": config["general"]["name"],
            "table": config["rethink"]["table"],
            "imagesPath": config["images"]["save-path"],
            "start": config["general"]["start"],
            "log": "stdout"
        }, conflict="update").run(conn)

    async with aiohttp.ClientSession() as cl_session:
        await load_images(conn, cl_session)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
