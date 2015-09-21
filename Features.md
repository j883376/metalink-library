# Feature List #

  * Automatic generation of P2P download links for known hashes (ED2K and Magnet)
  * Automatic parsing of (multi-file) torrents, metalink templates, hash, signature and mirror list files (or URLs or text)
  * Automatic searching and hashing of local download files (MD5, SHA1, SHA256, ED2K, SHA1 chunks)
  * Convenient change\_filename() to update existing Metalink files for new releases
  * For compact library usage, array and iterator access for metalink objects is supported
  * Generate BitTorrent files (only single-file torrents for now)
  * Metalink update mode: apply options to .metalink files, hash found download files (of the new version) and generate .torrent
  * Mirror lists can be plain or HTML, absolute or relative: [ftp://mirror.org/download/](ftp://mirror.org/download/)
  * Simple command-line interface with convenient use cases for cronjobs and daemon scripts (directory watcher, ...)