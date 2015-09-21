A script based library to create and manage Metalink download files, which contain HTTP, FTP, rsync and P2P download links for single or multiple download files.

In addition, single-file BitTorrent files can be generated as well as imported.


The Python version is generally faster than the PHP version, especially for large files.
But both versions offer exactly the same functionality, except for 32-bit limitations of PHP resulting in wrong 

&lt;size&gt;

 tags after scanning files bigger than 2 GB, which have to be manually corrected.

The library is a fork of the Metalink Editor by Hampus Wessman.

Please report bugs and feature requests in the [Issues list](http://code.google.com/p/metalink-library/issues/list).


For convenience the library provides a command-line interface.

```
Usage: metalink.py [FILE|DIRECTORY]...

Create Metalink and BitTorrent files by parsing download files.
Helper files will be searched and parsed automatically:
.metalink, .torrent, .mirrors, .md5, .sha1, .sha256 (sum, SUMS), .sig.
Glob wildcard expressions are allowed for filenames (openproj-0.9.6*).
Torrents will only be created for single files with chunks (parsed or scanned).
Chunks will only be imported from single-file torrents.


Examples:

# Parse file1, search helper files file1.* and generate file1.metalink.
# In addition, create file1.torrent (if exists, create file1.torrent.new).
metalink.py file1 --create-torrent=http://linuxtracker.org/announce.php

# Parse directory, search download and helper files *.* and generate
# *.metalink for all non-helper files bigger than 1 MB.
# First metalink file with no download file match will be the template
# for download files with no corresponding metalink file.
metalink.py directory

# Upgrade to new release with single metalink template.
metalink.py --version=1.1 file-1.0.zip.metalink file-1.1*

# Update file-1.0*.metalink files with new version number 1.1,
# parse file-1.1* and file-1.1*.torrent and generate file-1.1*.metalink.
metalink.py --version=1.1 file-1.0*.metalink

# Define URL prefix to save the original .metalink download URL:
# http://openoffice.org/url/prefix/file1.metalink
metalink.py http://openoffice.org/url/prefix/ file1


Options:
 --create-torrent=URLs  Create torrent with given tracker URLs (comma separates groups, space separates group members: "t1, t2a t2b")
 --overwrite            Overwrite existing files (otherwise append .new)
 -t, --template=FILE    Metalink template file
 --url-prefix=URL       URL prefix (where metalink should be placed online)
 -v, --verbose          Verbose output
 -V                     Show program version and exit
 -h, --help             Print this message and exit

Metalink options:
 --changelog=TEXT       Changelog
 --copyright=TEXT       Copyright
 --description=TEXT     Description
 --identity=TEXT        Identity
 --license-name=TEXT    Name of the license
 --license-url=URL      URL of the license
 --logo=URL             Logo URL
 --origin=URL           Absolute or relative URL to this metalink file (online)
 --publisher-name=TEXT  Name of the publisher
 --publisher-url=URL    URL of the publisher
 --refreshdate=DATE     RFC 822 date of refresh (for type "dynamic")
 --releasedate=DATE     RFC 822 date of release
 --screenshot=URL       Screenshot(s) URL
 --tags=TEXT            Comma-separated list of tags
 --type=TEXT            Type of this metalink file ("dynamic" or "static")
 --upgrade=TYPE         Upgrade type ("install", "uninstall, reboot, install" or "uninstall, install")
 --version=TEXT         Version of the file
```