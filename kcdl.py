import click
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import itertools
import json
import os
from pathlib import Path
import shutil
import threading

from collections import namedtuple
from bs4 import BeautifulSoup
import requests

ACTIVITY_URL = 'https://classroom.kindercare.com/accounts/{}/activities'
SESSION_COOKIE_NAME = '_himama_session'
IMAGE_DIR = Path('downloads')

class Image(namedtuple('Image', ['date', 'name', 'link'])):
    """Wrapper for image objects."""

    @classmethod
    def from_json(cls, d):
        return Image(datetime.fromisoformat(d['date']), d['name'], d['link'])

    @property
    def path(self):
        return Path(IMAGE_DIR, str(self.date.year), str(self.date.month))

    @property
    def filename(self):
        return Path(self.path, self.name)

    def to_json(self):
        d = self._asdict()
        d['date'] = self.date.isoformat()
        return d


def fetch_page(page_num, account, session_value):
    """Fetches a page from the kindercare classroom app.

    The /activity page has a single table on it.  Each row is an image from an
    teacher.  This method looks at each row then finds the date, name, and
    download link of each image.

    You can use the ?page=# parameter to fetch a specific activity page.  If you
    go past the end the page has no table and just says "there are no
    activities".  This function returns an empty list if it can't find the
    table.

    Parameters:
      page_num: The page number to load, starts at 1.
      account: The account number to load
      session_value: The himama session cookie value to use for auth.

    Returns:
      A list of image objects.
    """
    params = {}
    if page_num:
        params['page'] = page_num
    cookies = {SESSION_COOKIE_NAME: session_value}
    r = requests.get(ACTIVITY_URL.format(account), cookies=cookies,
                     params=params) 
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    if not soup.table:
        # We are past the last page
        return []

    images = []
    for row in soup.table.tbody.find_all('tr'):
        cells = row.find_all('td')
        # row[1] is date, row[-1] is the link
        date = datetime.strptime(cells[1].text, '%m/%d/%y')
        link = cells[-1].a.get('href')
        name = cells[-1].a.get('download')
        images.append(Image(date, name, link))
    return images

def download_image(image, flatten=False):
    """Downloads an image.

    Images are signed aws links that can be downloaded without additional auth.
    They're valid for like 3.5 hours (lol random).

    Parameter:
      image: The Image object
      flatten: If true the image will be saved to downloads/filename.jpg.  If
          False, it's saved to a dated folder downloads/2023/01/filename.jpg.
    """
    
    r = requests.get(image.link, stream=True)
    if r.status_code != 200:
        click.echo(f"Image was not downloaded successfully {image.name}")
        return 

    path = Path(IMAGE_DIR, image.name) if flatten else image.filename
    image.path.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as out_file:
        shutil.copyfileobj(r.raw, out_file)
    os.utime(image.filename, times=(image.date.timestamp(),
                                    image.date.timestamp()))

def write_index(index_filename, images):
    """Writes out the index file for resume

    The index file is a JSON file of (slightly modified) Image objects.  This
    file can be used with the resume command.

    Parameters:
      index_filename: The filename for the index file.
      images: The list of Image object.
    """
    earliest = min([i.date.isoformat() for i in images])
    latest = max([i.date.isoformat() for i in images])
    index = {
      'earliest': earliest,
      'latest': latest,
      'images': [i.to_json() for i in images] 
    }
    with open(index_filename, 'w') as f:
        f.write(json.dumps(index))

def download_images(images, flatten, workers):
    """Downloads images in parallel.

    Image URls are signed AWS links so you can pretty much set workers as high
    as you want.  10 is usually pretty good (at that number ~1000 images takes
    a couple of minutes).

    Parameters:
        images: List of Image objects
        flatten: See download_image's flatten parameter.
        workers: Number of parallel download workers.
    """
    with click.progressbar(
            length=len(images), label=f"Downloading {len(images)} images") as pbar, ThreadPoolExecutor(max_workers = workers) as executor:
        for image in images:
            f = executor.submit(download_image, image, flatten=flatten)
            f.add_done_callback(lambda f: pbar.update(1))

@click.group()
def cli():
    pass

@cli.command()
@click.option('--start-page', default=1, type=int, help='What page number to start at')
@click.option('--end-page', default=None, type=int, help='What page number to end at')
@click.option('--account', help='The account number to fetch')
@click.option('--index-file', default=Path('index.json'),
              type=click.Path(dir_okay=False, writable=True))
@click.option('--index-only/--no-index-only', default=False, type=bool,
              help='Skips downloading images and only writes the index file')
@click.option('--session_value', help='The _himama_session value')
@click.option('--flatten/--no-flatten', default=False,
              help='Number of workers to download with')
@click.option('--workers', default=10, help='Number of workers to download with')
def download(start_page, end_page, account, index_file, index_only,
             session_value, flatten, workers):
    images = []
    for page_num in itertools.count(start_page):
        click.echo(f"Fetching images from page {page_num}")
        page_images = fetch_page(page_num, account, session_value)
        if not page_images:
          click.echo(f"Page {page_num} had no images, assuming done.")
          break
        if end_page and page_num  == end_page:
          click.echo(f"Hit end page of {end_page}")
          break
        images.extend(page_images)

    write_index(index_file, images)
    click.echo(f"Wrote index file to {index_file} with {len(images)} images")

    if index_only:
        click.echo('Skipping download due to index-only')
        return

    download_images(images, flatten, workers)

@cli.command()
@click.option('--index-file', default=Path('index.json'),
              type=click.File())
@click.option('--flatten/--no-flatten', default=False, help='Number of workers to download with')
@click.option('--workers', default=10, help='Number of workers to download with')
def resume(index_file,  flatten, workers):
    data = json.loads(index_file.read())
    images = [Image.from_json(i) for i in data['images']]
    download_images(images, flatten, workers)

if __name__ == '__main__':
    cli()
