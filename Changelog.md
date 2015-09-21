# Version 1.1 #

  * Generate BitTorrent files (only single-file torrents for now), import chunks only from single-file .torrents.
  * Extended command-line support.
  * Import of signature files.
  * Metalink update mode: apply options to .metalink files, hash found download files (of the new version) and generate .torrent.

# Version 1.0 #

  * Parsing of (multi-file) torrents, metalink templates, hash and mirror list files (or URLs or text).
  * Mirror lists can be plain or HTML, absolute or relative: [ftp://mirror.org/download/](ftp://mirror.org/download/)
  * Automatic searching and hashing of local download files (MD5, SHA1, SHA256, ED2K, SHA1 chunks).
  * Automatic generation of P2P download links for known hashes (ED2K and Magnet).
  * Convenient change\_filename() to update existing Metalink files for new releases.
  * For compact library usage, array and iterator access for metalink objects is supported.
  * Basic command-line interface for cronjobs and daemon scripts (directory watcher, ...).