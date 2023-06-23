# What is this thing?

The Kindercare daycare has a web app they upload images to but provide no way to
bulk download the images.  This will paginate through the list of images and
download them all so you can archive them.

I spent ~3 hours on this so YMMV on how reliable it is.  It is relatively
straight forward though.

## Setting up

Just be sure the requirements are installed.  The versions are just whatever was
available at the time so you might want to just use venv.  Also this was done
with Python 3.9.  It probably works with anything after 3.6 mostly due to the
use of format strings.

- Setup a venv via `python -m venv .`
- `. bin/activate`
- `pip3 install -r requirements.txt`

## How to run

There are two commands download and resume.

### Download

Fetches the list of all images by paginating through the kindercare classroom
application.  Writes out an index file then downloads each image.

`python kcdl.py download --account=XXXX --session_value=YYYY`

You can specify the `--index-only` flag to just write the index of images out.

### Resume

Downloads images using the index file.  The image links are signed AWS links
that are good for 3.5 hours.  The download is down with 10 parallel workers by
default.  Despite the name it doesn't partially resume downloading, it downloads
every image in the index file and overwrites any existing files already
downloaded.  It does not refetch the list from kindercare.

`python kcdl.py resume --workers=10`

## A note on incremental archival

There's no diffing or anything in here so no real support for incrementally
archiving.  The best you can do is look at the earliest/latest date in the index
file then on the classroom app go find the page number on the activities page
that you've already fetched.  You can then use `--end-page` to have the script
stop at that page and not redownload a bunch of images.

# Helpful stuff

## Where to get account number

- Login to classroom.kindercare.com
- Click Journal
- It will be the ID after /accounts/

e.g. https://classroom.kindercare.com/accounts/*######*/journal

## Where to get the session value

- Login to classroom.kindercare.com
- Open chrome network tools
- Click application
- Open cookies
- Find `_himama_session` and get the value of It

If you logout/login this value will change and probably invalidate whatever you
copied here.  Not sure how long sessions are valid for, the cookie expiration
says session in chrome but presumably it expires at some point on the
kindercare side.

# Uploading to google photos

The whole point of this was so I could upload photos to Google Photos.  The
easiest way to do this is to specify the `--flatten` flag so images are
downloaded to the `downloads` directory.  Then open `photos.google.com` and
drag and drop this folder.  Hierarchy folders can also be uploaded via drag/drop
but you have to do the month level folders so it's just more annoying.
