#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
#
#    Copyright (c) 2007-2009 René Leonhardt, Germany.
#    Copyright (c) 2007 Hampus Wessman, Sweden.
#
#    Website: http://code.google.com/p/metalink-library/
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 2.1 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program; if not, write to the Free Software Foundation,
#    Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import binascii, datetime, glob, math, os, re, sys, time, urllib, urlparse, xml.dom
from xml.dom.minidom import parse, Node
from xml.sax.saxutils import escape


# Globals
current_version = "1.2"
generator="Metalink Library %s" % current_version
fs_encoding = sys.getfilesystemencoding()
preference_ed2k = "95"
verbose = None
# Command-line options
_opts = {}


def usage_and_exit(error_msg=None, options=''):
    progname = os.path.basename(sys.argv[0])

    stream = error_msg and sys.stderr or sys.stdout
    if error_msg:
        print >> stream, "ERROR: %s\n" % error_msg

    print >> stream, "Metalink Library %s by Rene Leonhardt and Hampus Wessman" % current_version
    if error_msg is False: sys.exit()

    params = [progname] * 14
    params.append(options and "\n\nOptions:\n" + options or '')

    print >> stream, """
Usage: %s [FILE|DIRECTORY]...

Create Metalink and BitTorrent files by parsing download files and mirror URLs.
Helper files will be searched and parsed automatically:
.metalink, .torrent, .mirrors, .md5, .sha1, .sha256 (sum, SUMS), .sig.
Glob wildcard expressions are allowed for filenames (openproj-1.4*).
Torrents will only be created for single files with chunks (parsed or scanned).
Chunks will only be imported from single-file torrents.
Automatic mirror parsing for SourceForge, Eclipse, MySQL and PostgreSQL URLs.


Examples:

# Parse file1, search helper files file1.* and generate file1.metalink.
# In addition, create file1.torrent (if exists, create file1.torrent.new).
%s file1 --create-torrent=http://linuxtracker.org/announce.php

# Parse directory, search download and helper files *.* and generate
# *.metalink for all non-helper files bigger than 1 MB.
# First metalink file with no download file match will be the template
# for download files with no corresponding metalink file.
%s directory

# Upgrade to new release with single metalink template.
# In addition, generate gzip compressed files to save server bandwidth.
%s --version=1.1 file-1.0.zip.metalink file-1.1* --compress-gzip

# Update file-1.0*.metalink files with new version number 1.1,
# parse file-1.1* and file-1.1*.torrent and generate file-1.1*.metalink.
%s --version=1.1 file-1.0*.metalink

# Update version number in existing SourceForge .metalink files (including filename and mirrors),
# remove hashes and P2P mirrors and create phpMyAdmin-3.1.4-*.metalink.
%s phpMyAdmin-3.1.3-*.metalink --version=3.1.4

# If the metalink files were generated without --version, you still can update the version
# information in filenames and mirrors by providing the old version number.
%s phpMyAdmin-3.1.3-*.metalink --version=3.1.4 --old-version=3.1.3

# After downloading, a BitTorrent file can easily be generated in a second command-line run:
# Parse finished download, update .metalink with hashes, piece checksums and P2P links and create .torrent.
%s openproj-1.4.zip.metalink --overwrite --create-torrent=http://example.tracker.org/announce

# Define URL prefix to save the original .metalink download URL:
# http://openoffice.org/url/prefix/file1.metalink
%s http://openoffice.org/url/prefix/ file1


# Mirror mode: create openproj-1.4.zip.metalink with all SourceForge mirrors (static list, no download).
%s --mirrors=http://downloads.sourceforge.net/openproj/openproj-1.4.zip
# Or you can even use a direct download link (without mirror selection)
%s --mirrors=http://superb-west.dl.sourceforge.net/sourceforge/openproj/openproj-1.4.zip

# Download the complete mirror list and create cdt-master-6.0.0.zip.metalink.
%s --mirrors="http://www.eclipse.org/downloads/download.php?file=/tools/cdt/releases/galileo/dist/cdt-master-6.0.0.zip"
# Also works for Eclipse links: http://www.eclipse.org/downloads/download.php?file=/technology/epp/downloads/release/galileo/R/eclipse-php-galileo-win32.zip

# Mirror files may contain preference and country values, i.e. ooop.mirrors:
http://puzzle.dl.sourceforge.net/ooop/
1 http://mesh.dl.sourceforge.net/ooop/
au ftp://optusnet.dl.sourceforge.net/sourceforge/o/oo/ooop/
be 100 http://belnet.dl.sourceforge.net/ooop/
90 br http://ufpr.dl.sourceforge.net/ooop/

# Append filename automatically to mirrors ending with / and generate several metalink files:
%s OOo_3.0.1_090128_Win32Intel_install.exe OOo_3.0.1_090128_Win32Intel_install_de.exe ooop.mirrors
# Generated: OOo_3.0.1_090128_Win32Intel_install.exe.metalink
# Generated: OOo_3.0.1_090128_Win32Intel_install_de.exe.metalink
# <url type="http" location="de" preference="1">http://mesh.dl.sourceforge.net/ooop/OOo_3.0.1_090128_Win32Intel_install.exe</url>

# Download and parse mirrors automatically, guess --filename and --filter from URL filename
%s --mirrors=http://wwwmaster.postgresql.org/download/mirrors-ftp/source/v8.4.0/postgresql-8.4.0.tar.bz2
# Generated: postgresql-8.4.0.tar.bz2.metalink
%s""" % tuple(params),
    sys.exit(error_msg and 1 or 0)

def get_first(x):
    try:
        return x[0]
    except:
        return x

def check_rfc822_date(date):
    if date.strip() != "":
        _date = re.sub(r' (\+0000|GMT|UTC?|Z)$', '', date)
        try:
            time.strptime(_date, "%a, %d %b %Y %H:%M:%S")
        except ValueError, e:
            return False
    return True

def encode_text(text, encoding='utf-8'):
    return text.decode(fs_encoding).encode(encoding)

def split_values(value_list, return_array=True, separator=',', separator2=''):
    '''Return splitted list of comma-separated value_list'''
    if not value_list or not isinstance(value_list, basestring):
        if return_array:
            return []
        return value_list
    values = []
    for value in value_list.split(separator):
        value = value.strip()
        if not value:
            continue
        if separator2:
            values.append(split_values(value, True, separator2))
        elif value not in values:
            values.append(value)
    return values

# Uses compression if available
# HINT: Use httplib2 if possible
def get_url(url):
    if not url:
        return ''

    import urllib2

    headers = {'Accept-encoding': 'gzip;q=1.0, deflate;q=0.9, identity;q=0.5', 'User-agent': 'Mozilla/5.0 (X11; U; Linux x86_64; de; rv:1.9.1) Gecko/20090701 Ubuntu/9.04 (jaunty) Firefox/3.5'}
    req = urllib2.Request(url, '', headers)

    def uncompress(page):
        content = page.read()
        info = page.info()
        encoding = info.get("Content-Encoding")
        if encoding in ('gzip', 'x-gzip', 'deflate'):
            from cStringIO import StringIO
            if encoding == 'deflate':
                import zlib
                content = StringIO(zlib.decompress(content)).read()
            else:
                import gzip
                content = gzip.GzipFile(fileobj=StringIO(content)).read()
            #info['Content-Length'] = str(len(content))
            #del info['Content-Encoding']
        return content

    try:
        f = urllib2.urlopen(req)
        return uncompress(f)
    except Exception, e: # urllib2.URLError
        print >> sys.stderr, 'Download error:', e

    return ''

def unique(seq, key=None, range=None):
    d = {}
    if key is not None:
        return [d.setdefault(e[key],range and e[range[0]:range[1]] or e) for e in seq if e[key] not in d]
    return [d.setdefault(e,e) for e in seq if e not in d]

def generate_verification_and_resources(self, add_p2p=True, protocols=[], is_child=True):
    text = ''
    indentation = is_child and '    ' or '  '

    # Verification
    if self.hashes.pieces or self.signature or self.hashes.has_one('ed2k md5 sha1 sha256'):
        text += indentation + '  <verification>' + os.linesep
        # TODO: ed2k really allowed?
        for hash, value in sorted(self.hashes.get_multiple('ed2k md5 sha1 sha256').items()):
            text += '%s    <hash type="%s">%s</hash>%s' % (indentation, hash, value.lower(), os.linesep)
        # TODO: Why len(self.pieces) > 1 ?
        if len(self.hashes.pieces):
            text += indentation + '    <pieces type="'+self.hashes.piecetype+'" length="'+self.hashes.piecelength+'">' + os.linesep
            for id, piece in enumerate(self.hashes.pieces):
                text += indentation + '      <hash piece="'+str(id)+'">'+piece+'</hash>' + os.linesep
            text += indentation + '    </pieces>' + os.linesep
        if self.signature.strip() != "":
            text += '%s    <signature type="%s">%s</signature>%s' % (indentation, self.signature_type, self.signature, os.linesep)
        text += indentation + '  </verification>' + os.linesep

    # Add missing P2P resources implicitly if hashes are available
    if add_p2p and 'ed2k' in self.hashes and self.size and getattr(self, 'filename', '') and 'ed2k' not in protocols:
        aich = 'aich' in self.hashes and ('h=' + self.hashes['aich'].upper() + '|') or ''
        url = "ed2k://|file|%s|%s|%s|%s/" % (urllib.quote(os.path.basename(self.filename)), self.size, self.hashes['ed2k'].upper(), aich)
        self.add_url(url, "ed2k", "", preference_ed2k, "", is_child)
    if add_p2p and ((self.size and getattr(self, 'filename', '')) or self.hashes.has_one('btih ed2k sha1')) and 'magnet' not in protocols:
        magnet = {}
        hashes = []
        if getattr(self, 'filename', ''): magnet['dn'] = os.path.basename(self.filename)
        if self.size: magnet['xl'] = self.size
        if 'sha1' in self.hashes: hashes.append("urn:sha1:%s" % self.hashes['sha1'].upper())
        if 'ed2k' in self.hashes:
            hashes.append("urn:ed2k:%s" % self.hashes['ed2k'].lower())
            # Another way of including the ED2K hash: hashes.append("urn:ed2khash:%s" % self.hashes['ed2k'].lower())
        # TODO: tiger-tree root hash: http://wiki.shareaza.com/static/MagnetsMakeAndUse
        # TODO: kzhash
        if magnet or hashes:
            params = urllib.urlencode(magnet)
            if hashes:
                params += (params and '&' or '') + 'xt=' + '&xt='.join(hashes)
            url = "magnet:?%s" % params
            self.add_url(url, "magnet", "", "90", "", is_child)
        if 'btih' in self.hashes:
            url = "magnet:?xt=urn:btih:%s" % self.hashes['btih'].upper()
            self.add_url(url, "magnet", "", "99", "", is_child)

    if self.resources:
        if getattr(self, 'maxconn_total', '') and "" != self.maxconn_total.strip() and "-" != self.maxconn_total.strip():
            text += indentation + '  <resources maxconnections="' + self.maxconn_total + '">' + os.linesep
        else:
            text += indentation + "  <resources>" + os.linesep
        for res in self.resources:
            details = ''
            if res.location.strip() != "":
                details += ' location="'+res.location.lower()+'"'
            if res.preference.strip() != "": details += ' preference="'+res.preference+'"'
            if res.conns.strip() != "" and res.conns.strip() != "-" : details += ' maxconnections="'+res.conns+'"'
            text += '%s    <url type="%s"%s>%s</url>%s' % (indentation, res.type, details, escape(res.url), os.linesep)
        text += indentation + '  </resources>' + os.linesep

    return text

# return 0=no valid URL, 1=URL prefix, 2=normal URL
def is_url(url):
    u = urlparse.urlparse(url, '', False)
    if not (u[0] and u[1] and u[2]):
        return 0
    _is_url = u[0] in 'http https ftp ftps'.split() and u[1] and u[2]
    if not _is_url:
        return 0
    return u[2][-1] == '/' and 1 or 2

# Create a gzip compressed file from data (use highest compression=9)
def compress_file(outfile, data, read_file=False):
    try:
        import gzip
        zfile = gzip.GzipFile(outfile, 'wb')
        if read_file:
            infile = open(data, 'rb')
            data = infile.read()
            infile.close()
        zfile.write(data)
        zfile.close()
        return True
    except:
        return False

def main(args=[]):
    global _opts, verbose
    if isinstance(args, basestring):
        args = [args]

    # Optional speed improvement
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass

    # Read arguments and options
    optParser = OptParser(['compress-gzip','Generate gzip compressed files (.metalink.gz, .torrent.gz) in addition to save server bandwidth', 'create-torrent=sURLs','Create torrent with given tracker URLs (comma separates groups, space separates group members: "t1, t2a t2b")', 'create-torrent-only=sURLs','The same as --create-torrent, but do not generate Metalink files', 'directory|d=sDIRECTORY','Use output directory (instead of input file directory or current directory)', 'filename=sTEXT','Relative file path to append to mirror list', 'filter=sTEXT','Filter mirror URLs by a search text', 'filter-regex=sTEXT','Filter mirror URLs by a regular expression', 'filter-from=sTEXT','Parse mirror urls after (and including) regular expression', 'filter-to=sTEXT','Parse mirror urls until (and including) regular expression', 'mirrors=sURL|FILE','Parse URL or file for mirrors (special support for SourceForge and Eclipse)', 'old-version=sTEXT','Old version to replace by --version (only necessary if no old version information is available)', 'overwrite','Overwrite existing files (otherwise append .new)', 'preference=sTEXT','Set default preference (1-100), extended: http=80,ftp=90,bittorrent=100', 'recursive|R-sFILE PATTERN','Parse directories recursively', 'template|t=sFILE','Metalink template file', 'url-prefix=sURL','URL prefix (where metalink should be placed online)', 'verbose|v','Verbose output', 'V','Show program version and exit', 'help|h','Print this message and exit\n\nMetalink options:',
        'changelog=sTEXT','Changelog',
        'copyright=sTEXT','Copyright',
        'description=sTEXT','Description',
        'identity=sTEXT','Identity',
        'language=sISO-CODE','ISO-639/3166 code of language (en-US)',
        'license-name=sTEXT','Name of the license',
        'license-url=sURL','URL of the license',
        'logo=sURL','Logo URL',
        'origin=sURL','Absolute or relative URL to this metalink file (online)',
        'os=sOS','Operating system ("Source", "Linux-x86", ...)',
        'publisher-name=sTEXT','Name of the publisher',
        'publisher-url=sURL','URL of the publisher',
        'refreshdate=sDATE','RFC 822 date of refresh (for type "dynamic")',
        'releasedate=sDATE','RFC 822 date of release',
        'screenshot=sURL','Screenshot(s) URL',
        'tags=sTEXT','Comma-separated list of tags',
        'type=sTEXT','Type of this metalink file ("dynamic" or "static")',
        'upgrade=sTYPE','Upgrade type ("install", "uninstall, reboot, install" or "uninstall, install")',
        'version=sTEXT','Version of the file'])
    _args = args + sys.argv[1:]
    _opts, args, stdin, errors = optParser.parse(_args)

    if _opts['verbose'] is not None:
        verbose = _opts['verbose']
    if _opts['help'] or errors:
        usage_and_exit(os.linesep.join(errors), optParser.getHelp())
    if _opts['V']:
        usage_and_exit(False)

    # Sanitize options
    # TODO: check rest of _opts
    _opts['tags'] = split_values(_opts['tags'], False)

    files = {}
    files_not_found = []
    files_skipped = []
    m = Metalink()

    _files = []
    _directories = []
    _hashes = {}
    _hashes_general = Hashes()
    _metalinks = {}
    _metalink_general = ''
    _mirrors = {}
    _mirrors_general = Mirrors()
    _signatures = {}
    _torrents = {}

    if _opts['template'] and os.path.isfile(_opts['template']):
        _files.append(_opts['template'])
    if _opts['url_prefix'] and 1 != is_url(_opts['url_prefix']):
        _opts['url_prefix'] = False
    if _opts['create_torrent_only']:
        _opts['create_torrent'] = split_values(_opts['create_torrent_only'], True, ',', ' ')
    elif _opts['create_torrent']:
        _opts['create_torrent'] = split_values(_opts['create_torrent'], True, ',', ' ')
    if _opts['mirrors'] and re.search(r'\s', _opts['mirrors']):
        _opts['mirrors'] = [_mirror for _mirror in re.split(r'\s+', _opts['mirrors']) if is_url(_mirror)]
    elif _opts['mirrors'] and not (is_url(_opts['mirrors']) or os.path.isfile(_opts['mirrors'])):
        _opts['mirrors'] = False
    if _opts['preference']:
        preferences = split_values(_opts['preference'], True, ',', '=')
        protocols = m.supported_protocols()
        p1 = [p for p in preferences if len(p) == 1 and p[0].isdigit() and 0 <= int(p[0]) <= 100]
        p2 = [p for p in preferences if len(p) == 2 and p[1].isdigit() and p[0] in protocols and 0 <= int(p[1]) <= 100]
        if p1 or p2:
            _opts['preference'] = {}
            if p1: _opts['preference'] = dict([ [p, p1[-1][0] ] for p in protocols])
            for p in p2: _opts['preference'][p[0]] = p[1]
        else:
            _opts['preference'] = False

    # Search files and url_prefix
    for arg in args:
        if os.path.isdir(arg):
            _directories.append(arg)
        elif os.path.isfile(arg):
            file = os.path.realpath(arg)
            _files.append(file)
            # Search parallel helper files
            _files.extend(m.find_helper_files(file))
        elif is_url(arg):
            if 1 == is_url(arg):
                if not _opts['url_prefix']:
                    _opts['url_prefix'] = arg
            else:
                # Add mirror
                _mirrors_general.parse('', arg)
        else:
            # Try glob expression (wildcards)
            for file in glob.glob(arg):
                if os.path.isfile(file):
                    _files.append(file)
                    # Search parallel helper files
                    _files.extend(m.find_helper_files(file))
                elif os.path.isdir(file):
                    _directories.append(arg)
            else:
                files_not_found.append(arg)
    if files_not_found:
        _set_opt('filename', files_not_found[0])

    if _opts['recursive'] and not _directories:
        _directories.append('.')

    for directory in _directories:
        for root, dirs, filenames in os.walk(os.path.realpath(directory)):
            for file in [os.path.join(root, file) for file in filenames]:
                _files.append(file)
                # Search parallel helper files
                _files.extend(m.find_helper_files(file))
            if not _opts['recursive']: break

    _files = unique(_files)

    # Categorize and filter files (hashes, mirrors, torrents, signatures)
    for file in _files:
        _file = os.path.basename(file)
        if _file.endswith('.metalink'):
            _metalinks[_file[:-9]] = file
        elif _file.endswith('.torrent'):
            _torrents[_file[:-8]] = file
        elif _file.endswith('.mirrors') or _file.lower() == 'mirrors':
            key = _file.lower() == 'mirrors' and _file or _file[:-8]
            _mirrors[key] = file
        elif m.hashes.is_hash_file(_file):
            hash_file = m.hashes.last_hash_file
            if hash_file not in _hashes:
                _hashes[hash_file] = {}
            if hash_file == _file:
                key = os.path.dirname(file)
            else:
                key = _file[len(hash_file)+1:]
            _hashes[hash_file][key] = file
        elif m.hashes.is_signature_file(_file):
            hash_file = m.hashes.last_hash_file
            if hash_file not in _signatures:
                _signatures[hash_file] = {}
            _signatures[hash_file][_file[len(hash_file)+1:]] = file
            _signatures[m.hashes.last_hash_file] = file
        elif os.stat(file).st_size > 1000000:
            files[_file] = file
        else:
            files_skipped.append(file)

    if files_skipped:
        files_skipped.sort()
        print >> sys.stderr, "Skipped the following files:\n%s" % "\n".join(files_skipped)

    # Metalink update mode
    if not files and len(_metalinks):
        if verbose is not False: print 'Metalink update mode (apply options and create torrents)'
        for filename, file in _metalinks.items():
            m = Metalink(False)
            m.load_file(file, False)

            if _opts['version']:
                new_version = _opts['version']
            else:
                new_version = m.version

            if _opts['old_version']:
                old_version = _opts['old_version']
            else:
                old_version = m.version

            if old_version and old_version != new_version:
                new_file = (os.path.dirname(file) and os.path.dirname(file) + os.sep or '') + filename.replace(old_version, new_version) + '.metalink'
            else:
                new_file = file

            # Parse mirrors before changing filename
            local_file = new_file[:-9]
            mirrors = local_file + '.mirrors'
            if os.path.isfile(mirrors):
                m.parse_mirrors(mirrors)
            elif len(_mirrors) == 1:
                m.parse_mirrors(_mirrors.values().pop())
            elif os.path.basename(local_file) in _mirrors:
                m.parse_mirrors(_mirrors[os.path.basename(local_file)])
            elif _opts['mirrors']:
                if isinstance(_opts['mirrors'], list):
                    m.parse_mirrors(data="\n".join(_opts['mirrors']))
                elif is_url(_opts['mirrors']):
                    m.parse_mirrors('', _opts['mirrors'])
                else:
                    m.parse_mirrors(_opts['mirrors'])

            if old_version != new_version:
                m.change_filename(new_version, old_version, False)

            # Parse parallel files
            torrent = local_file + '.torrent'
            if os.path.isfile(torrent):
                m.parse_torrent(torrent)
            if os.path.isfile(local_file):
                m.scan_file(local_file)

            # Force current creation date (may be overwritten by command-line option afterwards)
            m.pubdate = ''
            m.apply_command_line_options()

            if os.path.isfile(new_file) and not _opts['overwrite']:
                new_file += '.new'
            m.generate(new_file)
        return

    # Mirror update mode
    if not files and len(_metalinks) == 1 and len(_mirrors) == 1:
        files[_metalinks.keys()[0]] = _metalinks.keys()[0]

    # Filter general help files
    for filename in set(_metalinks.keys()).difference(set(files.keys())):
        # TODO: Parse general metalink only once
        _metalink_general = _metalinks.pop(filename)
        break
    if files:
        for filename in set(_mirrors.keys()).difference(set(files.keys())):
            _mirrors_general.parse(_mirrors.pop(filename))
    for filename in set(_hashes.keys()).difference(set(files.keys())):
        for file in _hashes[filename].values():
            _hashes_general.parse(file)

    # Mirror download mode
    if len(_mirrors) == 1 and not _opts['mirrors']:
        _opts['mirrors'] = _mirrors.popitem()[1]
    if not files and _opts['mirrors']:
        if not files_not_found:
            files_not_found.append('')
        for filename in files_not_found:
            if filename:
                _set_opt('filename', filename)
            if isinstance(_opts['mirrors'], list):
                m.parse_mirrors(data="\n".join(_opts['mirrors']))
            elif is_url(_opts['mirrors']):
                m.parse_mirrors('', _opts['mirrors'])
            else:
                m.parse_mirrors(_opts['mirrors'])
            local_file = m.file.mirrors.get_filename()
            if m.file.filename and not local_file:
                local_file = m.file.filename
            else:
                m.file.filename = local_file
            directory = _get_opt('directory')
            if directory:
                local_file = directory + os.sep + local_file
            torrent = local_file + '.torrent'
            if os.path.isfile(torrent):
                m.parse_torrent(torrent)
            if os.path.isfile(local_file):
                m.scan_file(local_file)
            m.generate(True)
            m.reset()
        return

    if not files:
        usage_and_exit(None, optParser.getHelp()) # 'No files to process'

    for filename, file in files.items():
        if verbose is not False: print 'Processing %s' % file
        m = Metalink()

        # Parse metalink template
        if filename in _metalinks:
            m.load_file(_metalinks[filename])
        elif _metalink_general:
            m.load_file(_metalink_general)

        # Force pubdate to be the current timestamp
        m.pubdate = ''

        # Overwrite old mirror filenames from template
        m.change_filename(filename)

        if filename in _mirrors:
            m.clear_res('http ftp https ftps')
            m.parse_mirrors(_mirrors[filename], '', '', False, True)
            # m.file.mirrors.change_filename(filename)
        elif _mirrors_general.mirrors:
            _mirrors_general.change_filename(filename)
            m.file.mirrors.add(_mirrors_general, True)
        elif _opts['mirrors']:
            if isinstance(_opts['mirrors'], list):
                m.parse_mirrors(data="\n".join(_opts['mirrors']))
            elif is_url(_opts['mirrors']):
                m.parse_mirrors('', _opts['mirrors'])
            else:
                m.parse_mirrors(_opts['mirrors'])

        # Parse torrent files
        if filename in _torrents:
            m.parse_torrent(_torrents[filename])
        elif len(_torrents) == len(files) == 1:
            m.parse_torrent(_torrents.values()[0])

        # Parse signature file
        if filename in _signatures:
            m.import_signature(_signatures[filename])

        # Parse hash files
        _hashes_general.set_file(file)
        m.file.hashes.update(_hashes_general)
        if filename in _hashes:
            m.file.hashes.files = _hashes[filename].values()
            m.file.hashes.parse_files()
        m.file.hashes.set_file(file)

        if os.path.isfile(file):
            # Scan file for remaining hashes
            m.scan_file(file)

        m.generate(True)

class Resource(object):
    def __init__(self, url, type="default", location="", preference="", conns=""):
        self.errors = []
        self.url = url
        self.location = location
        if type == "default" or type.strip() == "":
            if url.endswith(".torrent"):
                self.type = "bittorrent"
            else:
                chars = url.find(":")
                self.type = url[:chars]
        else:
            self.type = type
        self.preference = str(preference)
        if conns.strip() == "-" or conns.strip() == "":
            self.conns = "-"
        else:
            self.conns = conns

    def validate(self):
        if self.url.strip() == "":
            self.errors.append("Empty URLs are not allowed!")
        allowed_types = ["ftp", "ftps", "http", "https", "rsync", "bittorrent", "magnet", "ed2k"]
        if not self.type in allowed_types:
            self.errors.append("Invalid URL: " + self.url + '.')
        elif self.type in ['http', 'https', 'ftp', 'ftps', 'bittorrent']:
            m = re.search(r'\w+://.+\..+/.*', self.url)
            if m is None:
                self.errors.append("Invalid URL: " + self.url + '.')
        if self.location.strip() != "":
            iso_locations = ["AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "KH", "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MK", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "AN", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "SH", "KN", "LC", "PM", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SK", "SI", "SB", "SO", "ZA", "GS", "ES", "LK", "SD", "SR", "SJ", "SZ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW", "UK"]
            if not self.location.upper() in iso_locations:
                self.errors.append(self.location + " is not a valid country code.")
        if self.preference != "":
            try:
                pref = int(self.preference)
                if pref < 0 or pref > 100:
                    self.errors.append("Preference must be between 0 and 100, not " + self.preference + '.')
            except:
                self.errors.append("Preference must be a number, between 0 and 100.")
        if self.conns.strip() != "" and self.conns.strip() != "-":
            try:
                conns = int(self.conns)
                if conns < 1:
                    self.errors.append("Max connections must be at least 1, not " + self.conns + '.')
                elif conns > 20:
                    self.errors.append("You probably don't want max connections to be as high as " + self.conns + '!')
            except:
                self.errors.append("Max connections must be a positive integer, not " + self.conns + ".")
        # TODO: Validate ed2k MD4/AICH and magnet SHA1 hash
        return len(self.errors) == 0

    def __repr__(self):
        return '%s, %s, %s, %s' % (self.url, self.type, self.location, self.preference)

class Metafile(object):
    def __init__(self):
        self.hashes = Hashes()
        self.mirrors = Mirrors()
        self.reset()

    def clear_res(self, types=''):
        if not types.strip():
            self.resources = []
            self.urls = []
        else:
            _types = types.strip().split()
            self.resources = [res for res in self.resources if res.type not in _types]
            self.urls = [res.url for res in self.resources]

    def add_url(self, url, type="default", location="", preference="", conns="", add_to_child=True):
        if url not in self.urls:
            l = self.mirrors.parse_link(url, location, False, preference)
            if l:
                self.resources.append(Resource(l[0], l[1], l[2], l[3], conns))
                self.urls.append(url)
                return True
        return False

    def add_res(self, res):
        if res.url not in self.urls:
            self.resources.append(res)
            self.urls.append(res.url)
            return True
        return False

    def import_signature(self, file):
        fp = open(file, "rb")
        self.signature = fp.read()
        fp.close()
        return True

    def scan_file(self, filename, use_chunks=True, max_chunks=255, chunk_size=256, progresslistener=None):
        if verbose: print "Scanning file..."
        # Filename and size
        self.filename = os.path.basename(filename)
        if not self.hashes.filename:
            self.hashes.filename = self.filename
        size = os.stat(filename).st_size
        self.size = str(size)

        known_hashes = self.hashes.get_multiple('ed2k md5 sha1 sha256')
        # If all hashes and pieces are already known, do nothing
        if 4 == len(known_hashes) and self.hashes.pieces:
            return True

        piecelength_ed2k = 9728000
        # Force maximum size for piece checksums to 512 KiB:
        # http://en.wikipedia.org/wiki/BitTorrent_(protocol)#Creating_and_publishing_torrents
        maxlength = 524288
        # Calculate piece length
        if use_chunks:
            minlength = chunk_size*1024
            self.hashes.piecelength = 1024
            while self.hashes.piecelength < maxlength and (size / self.hashes.piecelength > max_chunks or self.hashes.piecelength <= minlength):
                self.hashes.piecelength *= 2
            if verbose: print "Using piecelength", self.hashes.piecelength, "(" + str(self.hashes.piecelength / 1024) + " KiB)"
            numpieces = size / self.hashes.piecelength
            if numpieces < 2: use_chunks = False
        hashes = {}
        # ADDED: MD4 for calculating ed2k hashes
        # TODO: AICH ed2k hashes (allow much better error recognition and repair, 180 KB pieces instead of 9500 KB)
        # Try to use hashlib
        try:
            import hashlib
            hashes['md4'] = hashlib.new('md4')
            hashes['md5'] = hashlib.md5()
            hashes['sha1'] = hashlib.sha1()
            hashes['sha256'] = hashlib.sha256()
        except:
            # Import deprecated modules
            import md5
            import sha
            # Try old MD4 lib
            try:
                import Crypto.Hash.MD4
                hashes['md4'] = Crypto.Hash.MD4.new()
            except:
                hashes['md4'] = None
            print >> sys.stderr, "Hashlib not available. No support for SHA-256%s" % (hashes['md4'] and "." or " and ED2K.")
            hashes['md5'] = md5.new()
            hashes['sha1'] = sha.new()
            hashes['sha256'] = None
        if hashes['md4']:
            md4piecehash = None
            if size > piecelength_ed2k:
                md4hash_copy = hashes['md4'].copy()
                md4piecehash = md4hash_copy.copy()
                length_ed2k = 0
        sha1hash_copy = hashes['sha1'].copy()
        piecehash = sha1hash_copy.copy()
        piecenum = 0
        length = 0

        # If some hashes are already available, do not calculate them
        if 'ed2k' in known_hashes:
            known_hashes['md4'] = known_hashes['ed2k']
            del known_hashes['ed2k']
        for hash in known_hashes.keys():
            hashes[hash] = None

        # TODO: Don't calculate pieces if already known
        self.hashes.pieces = []
        if not self.hashes.piecetype:
            self.hashes.piecetype = "sha1"

        num_reads = math.ceil(size / 4096.0)
        reads_per_progress = int(math.ceil(num_reads / 100.0))
        reads_left = reads_per_progress
        progress = 0
        fp = open(filename, "rb")
        while True:
            data = fp.read(4096)
            if data == "": break
            # Progress updating
            if progresslistener:
                reads_left -= 1
                if reads_left <= 0:
                    reads_left = reads_per_progress
                    progress += 1
                    result = progresslistener.Update(progress)
                    if get_first(result) == False:
                        if verbose: print "Cancelling scan!"
                        return False
            # Process the data
            if hashes['md5']: hashes['md5'].update(data)
            if hashes['sha1']: hashes['sha1'].update(data)
            if hashes['sha256']: hashes['sha256'].update(data)
            left = len(data)
            if hashes['md4']:
                if md4piecehash:
                    l = left
                    numbytes_ed2k = 0
                    while l > 0:
                        if length_ed2k + l <= piecelength_ed2k:
                            if numbytes_ed2k:
                                md4piecehash.update(data[numbytes_ed2k:])
                            else:
                                md4piecehash.update(data)
                            length_ed2k += l
                            l = 0
                        else:
                            numbytes_ed2k = piecelength_ed2k - length_ed2k
                            md4piecehash.update(data[:numbytes_ed2k])
                            length_ed2k = piecelength_ed2k
                            l -= numbytes_ed2k
                        if length_ed2k == piecelength_ed2k:
                            hashes['md4'].update(md4piecehash.digest())
                            md4piecehash = md4hash_copy.copy()
                            length_ed2k = 0
                else:
                    hashes['md4'].update(data)
            while use_chunks and left > 0:
                if length + left <= self.hashes.piecelength:
                    piecehash.update(data)
                    length += left
                    left = 0
                else:
                    numbytes = self.hashes.piecelength - length
                    piecehash.update(data[:numbytes])
                    length = self.hashes.piecelength
                    data = data[numbytes:]
                    left -= numbytes
                if length == self.hashes.piecelength:
                    if verbose: print "Done with piece hash", len(self.hashes.pieces)
                    self.hashes.pieces.append(piecehash.hexdigest())
                    piecehash = sha1hash_copy.copy()
                    length = 0
        if use_chunks:
            if length > 0:
                if verbose: print "Done with piece hash", len(self.hashes.pieces)
                self.hashes.pieces.append(piecehash.hexdigest())
            if verbose: print "Total number of pieces:", len(self.hashes.pieces)
        fp.close()
        if hashes['md4']:
            if md4piecehash and length_ed2k:
                hashes['md4'].update(md4piecehash.digest())
            self.hashes['ed2k'] = hashes['md4'].hexdigest()
        for hash in 'md5 sha1 sha256'.split():
            if hashes[hash]:
                self.hashes[hash] = hashes[hash].hexdigest()
        # TODO: Why len(self.pieces) < 2 ?
        if len(self.hashes.pieces) < 2: self.hashes.pieces = []
        # Convert to string
        self.hashes.piecelength = str(self.hashes.piecelength)
        if verbose: print "done"
        if progresslistener: progresslistener.Update(100)
        return True

    def validate(self):
        for url in 'screenshot logo'.split():
            if getattr(self, url).strip() != "":
                if not self.validate_url(getattr(self, url)):
                    self.errors.append("Invalid URL: " + getattr(self, url) + '.')
        if not self.resources and not self.mirrors:
            self.errors.append("You need to add at least one URL!")
        for hash, length in {'md5':32, 'sha1':40, 'sha256':64}.items():
            if hash in self.hashes:
                if re.match(r'^[0-9a-fA-F]{%d}$' % length, self.hashes[hash]) is None:
                    self.errors.append("Invalid %s hash." % hash)
        if self.size.strip() != "":
            try:
                size = int(self.size)
                if size < 0:
                    self.errors.append("File size must be at least 0, not " + self.size + '.')
            except:
                self.errors.append("File size must be an integer, not " + self.size + ".")
        if self.maxconn_total.strip() != "" and self.maxconn_total.strip() != "-":
            try:
                conns = int(self.maxconn_total)
                if conns < 1:
                    self.errors.append("Max connections must be at least 1, not " + self.maxconn_total + '.')
                elif conns > 20:
                    self.errors.append("You probably don't want max connections to be as high as " + self.maxconn_total + '!')
            except:
                self.errors.append("Max connections must be a positive integer, not " + self.maxconn_total + ".")
        if self.upgrade.strip() != "":
            if self.upgrade not in ["install", "uninstall, reboot, install", "uninstall, install"]:
                self.errors.append('Upgrade must be "install", "uninstall, reboot, install", or "uninstall, install".')
        return len(self.errors) == 0

    def validate_url(self, url):
        if url.endswith(".torrent"):
            type = "bittorrent"
        else:
            chars = url.find(":")
            type = url[:chars]
        allowed_types = ["ftp", "ftps", "http", "https", "rsync", "bittorrent", "magnet", "ed2k"]
        if not type in allowed_types:
            return False
        elif type in ['http', 'https', 'ftp', 'ftps', 'bittorrent']:
            if re.search(r'\w+://.+\..+/.*', url) is None:
                return False
        return True

    def generate_file(self, add_p2p=True):
        if self.filename.strip() != "":
            text = '    <file name="' + self.filename + '">' + os.linesep
        else:
            text = '    <file>' + os.linesep
        # File info
        # TODO: relations
        for attr in 'identity size version language os changelog description logo mimetype releasedate screenshot upgrade'.split():
            if "" != getattr(self, attr).strip():
                text += "      <%s>%s</%s>%s" % (attr, escape(getattr(self, attr)), attr, os.linesep)
        if self.tags:
            text += '      <tags>' + ','.join(unique(self.tags)) + "</tags>" + os.linesep

        # Add mirrors
        for url, type, location, preference in self.mirrors.mirrors:
            # Add filename for relative urls
            if '/' == url[-1]:
                url += os.path.basename(self.filename)
            self.add_url(url, type, location, preference)

        text += generate_verification_and_resources(self, add_p2p, self.get_protocols())

        text += '    </file>' + os.linesep
        return text

    # Return list of found resource types
    def get_protocols(self):
        found = {}
        for res in self.resources:
            if res.type not in found:
                found[res.type] = res.url
        return found

    # Call with filename or url
    def parse_torrent(self, filename='', url=''):
        torrent = Torrent(filename, url)
        torrent.parse()
        if not self.description:
            self.description = torrent.comment
        self.filename = torrent.files[0][0]
        self.size = str(torrent.files[0][1])
        if not self.hashes.filename:
            self.hashes.filename = self.filename
        self.hashes['btih'] = torrent.infohash
        self.hashes.pieces = torrent.pieces
        self.hashes.piecelength = str(torrent.piecelength)
        self.hashes.piecetype = 'sha1'
        if url and not filename:
            self.add_url(url, "bittorrent", "", "100")
        return torrent.files

    # Call with filename, url or text
    def parse_mirrors(self, filename='', url='', data='', plain=False, remove_others=False):
        if filename: filename = filename.strip()
        if url: url = url.strip()
        if filename and filename.endswith('.torrent'):
            return self.parse_torrent(filename)
        elif url and url.endswith('.torrent'):
            return self.parse_torrent('', url)
        mirrors = Mirrors(filename, url)
        mirrors.parse('', '', data, plain)
        self.mirrors.add(mirrors, remove_others)

    # Call with filename, url or text
    def parse_hashes(self, filename='', url='', data='', force_type='', filter_name=''):
        hashes = Hashes(filename, url)
        if self.filename:
            hashes.filename = self.filename
        hashes.parse('', data, force_type, filter_name)
        # TODO: Better setting of dict key
        self.hashes.filename = hashes.filename
        self.hashes.update(hashes)

    def change_filename(self, new, old='', overwrite_filename=True):
        if overwrite_filename and not old:
            old = self.filename
        if not old or not new:
            return False

        self.filename = self.filename.replace(old, new)

        self.mirrors.change_filename(new, old)

        # Clear resources containing size and hashes
        self.clear_res('ed2k magnet')
        self.hashes.init()
        self.size = ''

        old = urllib.quote(old)
        new = urllib.quote(new)

        self.urls = []
        for res in self.resources:
            res.url = res.url.replace(old, new)
            self.urls.append(res.url)

        return True

    def remove_other_mirrors(self, mirrors):
        _types = "bittorrent ed2k magnet".split()
        self.resources = [res for res in self.resources if res.type in _types or res.url in mirrors.urls]
        self.urls = [res.url for res in self.resources]
        self.mirrors.remove_other_mirrors(mirrors)

    def replace_hashes(self, hashes):
        old = hashes.filename
        hashes.filename = self.filename
        for hash, value in hashes.get_multiple('ed2k md5 sha1 sha256').items():
            self.hashes[hash] = value
        hashes.filename = old

    def get_urls(self):
        return [res.url for res in self.resources]

    def reset(self):
        """Reset mutable attributes to allow object reuse"""
        self.changelog = ""
        self.description = ""
        self.filename = ""
        self.identity = ""
        self.language = ""
        self.logo = ""
        self.maxconn_total = ""
        self.mimetype = ""
        self.os = ""
        self.releasedate = ""
        self.screenshot = ""
        self.signature = ""
        self.signature_type = ""
        self.size = ""
        self.tags = []
        self.upgrade = ""
        self.version = ""
        self.resources = []
        self.urls = []
        self.errors = []

        self.hashes.reset()
        self.mirrors.reset()

class Metalink(object):
    def __init__(self, overwrite_with_opts=True):
        self.hashes = Hashes()
        self.file = Metafile()

        self.reset(overwrite_with_opts)

    def apply_command_line_options(self):
        attrs = {}
        for opt in 'changelog copyright description filename_absolute generator identity license_name license_url logo origin pubdate publisher_name publisher_url refreshdate releasedate screenshot tags type upgrade version url_prefix os language'.split():
            if _get_opt(opt):
                attrs[opt] = _opts[opt]
        self.setattrs(attrs)

    def create_torrent(self, torrent_trackers, torrent):
        if not self.file.filename:
            return ['file name must be non-empty']
        if not self.file.size:
            return ['file size must be non-empty']
        t = Torrent(torrent)
        data = {'comment':encode_text(self.description), 'files':[[encode_text(self.file.filename), int(self.file.size)]], 'piece length':int(self.file.hashes.piecelength), 'pieces':self.file.hashes.pieces, 'trackers':torrent_trackers, 'created by':generator, 'encoding':'UTF-8'}
        return t.create(data)

    def clear_res(self, types=''):
        self.file.clear_res(types)

    def add_url(self, url, type="default", location="", preference="", conns="", add_to_child=True):
        if add_to_child:
            return self.file.add_url(url, type, location, preference, conns)
        if url not in self.urls:
            l = self.file.mirrors.parse_link(url, location, False, preference)
            if l:
                self.resources.append(Resource(l[0], l[1], l[2], l[3], conns))
                self.urls.append(url)
            return True
        return False

    def add_res(self, res):
        return self.file.add_res(res)

    def import_signature(self, file):
        return self.file.import_signature(file)

    def scan_file(self, filename, use_chunks=True, max_chunks=255, chunk_size=256, progresslistener=None):
        self.filename_absolute = filename
        return self.file.scan_file(filename, use_chunks, max_chunks, chunk_size, progresslistener)

    # TODO: get_errors() merges self errors and self.files errors
    def validate(self):
        for url in 'publisher_url license_url origin screenshot logo'.split():
            if getattr(self, url).strip() != "":
                if not self.validate_url(getattr(self, url)):
                    self.errors.append("Invalid %s%s: %s." % (url, url[-4:] != '_url' and ' URL' or '', getattr(self, url)))
        for d in 'pubdate refreshdate releasedate'.split():
            if not check_rfc822_date(getattr(self, d)):
                self.errors.append("%s must be of format RFC 822: %s" % (d, getattr(self, d)))
        if self.type.strip() != "":
            if self.type.lower() not in ["dynamic", "static"]:
                self.errors.append("Type must be either dynamic or static.")
        if self.upgrade.strip() != "":
            if self.upgrade.lower().replace(' ', '') not in ["install", "uninstall,reboot,install", "uninstall,install"]:
                self.errors.append('Upgrade must be "install", "uninstall, reboot, install", or "uninstall, install".')

        valid_files = True
        for f in self.files:
            valid_files = f.validate() and valid_files

        return valid_files and len(self.errors) == 0

    def get_errors(self):
        errors = self.errors
        for file in self.files:
            errors.extend(file.errors)
        return errors

    def validate_url(self, url):
        return self.file.validate_url(url)

    def generate(self, filename='', add_p2p=True):
        text = '<?xml version="1.0" encoding="utf-8"?>' + os.linesep
        origin = ""
        if _get_opt('url_prefix'):
            self.url_prefix = _get_opt('url_prefix')
        if self.url_prefix:
            text += '<?xml-stylesheet type="text/xsl" href="%smetalink.xsl"?>%s' % (self.url_prefix, os.linesep)
            if not self.origin:
                if filename and filename is not True:
                    metalink = os.path.basename(filename)
                else:
                    metalink = os.path.basename(self.filename_absolute)
                if not metalink and _get_opt('filename'):
                    metalink = os.path.basename(_get_opt('filename'))
                if not metalink.endswith('.metalink'):
                    metalink += '.metalink'
                self.origin = self.url_prefix + metalink
        if self.origin.strip() != "":
            origin = 'origin="'+self.origin+'" '
        pubdate = self.pubdate or time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        if 'dynamic' == self.type and self.refreshdate:
            refreshdate = '" refreshdate="' + self.refreshdate
        else:
            refreshdate = ''
        type = ""
        if self.type.strip() != "":
            type = 'type="'+self.type+'" '
        _generator = self.generator and self.generator or generator
        text += '<metalink version="3.0" ' + origin + type + 'pubdate="' + pubdate + refreshdate + '" generator="' + _generator + '" xmlns="http://www.metalinker.org/">' + os.linesep
        text += self.generate_info()
        text += "  <files>" + os.linesep
        # Add multi-file torrent information
        text += generate_verification_and_resources(self, add_p2p, [], False)
        text_start = text
        text_end = '  </files>' + os.linesep
        text_end += '</metalink>'

        text_files = ''
        for f in self.files:
            text = f.generate_file(add_p2p)
            text_files += text
            # TODO: Save separate .metalink for multi-file metalinks
        text = text_start + text_files + text_end

        try:
            data = text.encode('utf-8')
        except:
            data = text.decode('latin1').encode('utf-8')
        if filename:
            if filename is True:
                filename = (self.filename_absolute or self.file.filename or 'NEW') + '.metalink'
            elif not filename:
                filename = 'NEW.metalink'

            directory = _get_opt('directory')
            if directory:
                if not os.path.isdir(directory):
                    print >> sys.stderr, 'ERROR: output directory %s does not exist' % directory
                    return False
                filename = directory + os.sep + os.path.basename(filename)

            # Create backup
            if os.path.isfile(filename) and not _get_opt('overwrite'):
                filename += '.new'
                # os.rename(filename, filename + '.bak')

            compress_gzip = _get_opt('compress_gzip')
            if not _get_opt('create_torrent_only'):
                fp = open(filename, "wb")
                fp.write(data)
                fp.close()
                print '%s%s' % (verbose is not False and 'Generated: ' or '', filename)
                if compress_gzip:
                    if compress_file(filename + '.gz', data):
                        print '%s%s' % (verbose is not False and 'Generated: ' or '', filename + '.gz')

            create_torrent = _get_opt('create_torrent')
            if create_torrent:
                torrent = filename.endswith('.new') and filename[:-4] or filename
                torrent = (torrent.endswith('.metalink') and torrent[:-9] or torrent) + '.torrent'
                if os.path.isfile(torrent) and not _get_opt('overwrite'):
                    torrent += '.new'
                _errors = self.create_torrent(create_torrent, torrent)
                if _errors:
                    print 'ERROR while generating %s:\n%s' % (torrent, "\n".join(_errors))
                elif compress_gzip:
                        if compress_file(torrent + '.gz', torrent, True):
                            print '%s%s' % (verbose is not False and 'Generated: ' or '', torrent + '.gz')
            return True
        return data

    def generate_info(self):
        text = ""
        # Publisher info
        if self.publisher_name.strip() != "" or self.publisher_url.strip() != "":
            text += '  <publisher>' + os.linesep
            if self.publisher_name.strip() != "":
                text += '    <name>' + self.publisher_name + '</name>' + os.linesep
            if self.publisher_url.strip() != "":
                text += '    <url>' + self.publisher_url + '</url>' + os.linesep
            text += '  </publisher>' + os.linesep
        # License info
        if self.license_name.strip() != "" or self.license_url.strip() != "":
            text += '  <license>' + os.linesep
            if self.license_name.strip() != "":
                text += '    <name>' + self.license_name + '</name>' + os.linesep
            if self.license_url.strip() != "":
                text += '    <url>' + self.license_url + '</url>' + os.linesep
            text += '  </license>' + os.linesep
        # Release info
        for attr in 'identity version copyright description logo releasedate screenshot upgrade changelog'.split():
            if "" != getattr(self, attr).strip():
                text += "  <%s>%s</%s>%s" % (attr, escape(getattr(self, attr)), attr, os.linesep)
        if self.tags:
            text += '  <tags>' + ','.join(unique(self.tags)) + "</tags>" + os.linesep
        return text

    def load_file(self, filename, overwrite_with_opts=True):
        try:
            doc = parse(filename)
        except:
            raise Exception("Failed to parse metalink file! Please select a valid metalink.")
        try:
            for attr in 'origin pubdate refreshdate type'.split():
                setattr(self, attr, self.get_attribute(doc.documentElement, attr))
            publisher = self.get_tag(doc, "publisher")
            if publisher is not None:
                self.publisher_name = self.get_tagvalue(publisher, "name")
                self.publisher_url = self.get_tagvalue(publisher, "url")
            license = self.get_tag(doc, "license")
            if license is not None:
                self.license_name = self.get_tagvalue(license, "name")
                self.license_url = self.get_tagvalue(license, "url")
            for attr in 'identity version copyright description logo releasedate screenshot upgrade changelog'.split():
                setattr(self, attr, self.get_tagvalue(doc, attr))
            self.tags = split_values(self.get_tagvalue(doc, "tags"))

            files = self.get_tag(doc, "files")
            if files is None:
                raise Exception("Failed to parse metalink. Found no <files></files> tag.")
            metafiles = self.get_tag(files, "file", False)
            if metafiles is None:
                raise Exception("Failed to parse metalink. It must contain exactly one file description.")
            for index, file in enumerate(metafiles):
                if file.hasAttribute("name"): self.file.filename = file.getAttribute("name")
                for attr in 'identity size version language os changelog description logo mimetype releasedate screenshot upgrade'.split():
                    setattr(self.file, attr, self.get_tagvalue(file, attr))
                # TODO: self.file.relations = self.get_tagvalue(file, "relations")
                if self.version == "":
                    self.version = self.file.version
                self.file.tags = split_values(self.get_tagvalue(file, "tags"))
                self.file.hashes.filename = os.path.basename(self.file.filename)
                verification = self.get_tag(file, "verification")
                if verification is not None:
                    signature = self.get_tag(verification, "signature")
                    if signature is not None:
                        # TODO: Support optional file="linux.sign" attribute
                        self.file.signature = self.get_text(signature, False)
                        self.file.signature_type = self.get_attribute(signature, "type")
                    for hash in verification.getElementsByTagName("hash"):
                        # TODO: Double check can be removed
                        # TODO: Is ed2k hash really allowed? Used by Metalink Gen - http://metalink.packages.ro
                        # TODO: Support the rest of allowed hash types: md4 sha384 sha512 rmd160 tiger crc32
                        if hash in verification.childNodes:
                            if hash.hasAttribute("type"):
                                if hash.getAttribute("type").lower() in "ed2k md5 sha1 sha256".split():
                                    self.file.hashes[hash.getAttribute("type").lower()] = self.get_text(hash).lower()
                    pieces = self.get_tag(verification, "pieces")
                    if pieces is not None:
                        if pieces.hasAttribute("type") and pieces.hasAttribute("length"):
                            self.file.hashes.piecetype = pieces.getAttribute("type")
                            self.file.hashes.piecelength = pieces.getAttribute("length")
                            self.file.hashes.pieces = []
                            for hash in pieces.getElementsByTagName("hash"):
                                self.file.hashes.pieces.append(self.get_text(hash).lower())
                        else:
                            print >> sys.stderr, "Load error: missing attributes in <pieces>"
                resources = self.get_tag(file, "resources")
                num_urls = 0
                if resources is not None:
                    self.file.maxconn_total = self.get_attribute(resources, "maxconnections")
                    if self.file.maxconn_total.strip() == "": self.file.maxconn_total = "-"
                    for resource in resources.getElementsByTagName("url"):
                        type = self.get_attribute(resource, "type")
                        location = self.get_attribute(resource, "location")
                        preference = self.get_attribute(resource, "preference")
                        conns = self.get_attribute(resource, "maxconnections")
                        # TODO: Should get_text() result not be already stripped?
                        url = self.get_text(resource).strip()
                        self.add_url(url, type, location, preference, conns)
                        num_urls += 1
                if num_urls == 0:
                    raise Exception("Failed to parse metalink. Found no URLs!")
                if index < len(metafiles) - 1:
                    self.add_file()
            self.rewind()

            if overwrite_with_opts:
                self.apply_command_line_options()
        except xml.dom.DOMException, e:
            raise Exception("Failed to load metalink: " + str(e))
        finally:
            doc.unlink()

    def get_attribute(self, element, attribute):
        if element.hasAttribute(attribute):
            return element.getAttribute(attribute)
        return ""

    def get_tagvalue(self, node, tag):
        nodelist = node.getElementsByTagName(tag)
        if len(nodelist):
            return self.get_text(nodelist[0])
        return ""

    # TODO: Rename only_first if unclear
    def get_tag(self, node, tag, only_first=True):
        nodelist = node.getElementsByTagName(tag)
        if len(nodelist):
            if len(nodelist) == 1 and only_first:
                return nodelist[0]
            return nodelist
        return None

    def get_text(self, node, strip=True):
        text = ""
        for n in node.childNodes:
            if n.nodeType == Node.TEXT_NODE:
                text += n.data
        if strip:
            return text.strip()
        return text

    # Automatical string representation, i.e. "print metalink"
    def __str__(self):
        return self.generate()

    # Call with filename or url
    def parse_torrent(self, filename='', url=''):
        files = self.file.parse_torrent(filename, url)
        if not self.description:
            # Set torrent comment as description
            self.description = self.file.description
        if len(files) > 1:
            self.hashes['btih'] = self.file.hashes['btih']
            self.hashes.pieces = self.file.hashes.pieces
            self.hashes.piecelength = self.file.hashes.piecelength
            self.hashes.piecetype = self.file.hashes.piecetype
            self.file.description = ''
            self.file.hashes['btih'] = ''
            self.file.hashes.pieces = []
            if url and not filename:
                self.resources.append(self.file.resources.pop())
            current_key = self.key()
        else:
            # Remove single file description
            self.file.description = ''
        for name, size in files[1:]:
            self.add_file()
            self.file.filename = name
            self.file.size = str(size)
        if len(files) > 1:
            self.seek(current_key)

    # Call with filename, url or text
    def parse_mirrors(self, filename='', url='', data='', plain=False, remove_others=False):
        return self.file.parse_mirrors(filename, url, data, plain, remove_others)

    # Call with filename, url or text
    def parse_hashes(self, filename='', url='', data='', force_type='', filter_name=''):
        return self.file.parse_hashes(filename, url, data, force_type, filter_name)

    def setattrs(self, attrs):
        '''Set multiple attribute values.'''
        for attr, value in attrs.items():
            if hasattr(self, attr):
                setattr(self, attr, value)
            else:
                setattr(self.file, attr, value)

    def change_filename(self, new, old='', overwrite_filename=True):
        _old = old or os.path.basename(self.filename_absolute) or self.file.filename
        if _old:
            self.origin = self.origin.replace(_old, new)
        return self.file.change_filename(new, old, overwrite_filename)

    def remove_other_mirrors(self, mirrors):
        self.file.remove_other_mirrors(mirrors)

    def replace_hashes(self, hashes):
        self.file.replace_hashes(hashes)

    def is_helper_file(self, file):
        filename, extension = os.path.splitext(os.path.basename(file))

        # Skip filenames without extension
        if filename and not extension and filename.upper() in 'MD5SUMS SHA1SUMS SHA256SUMS'.split():
            return True
        if not (filename and len(extension) > 1):
            return False

        return extension[1:].lower() in 'metalink torrent mirrors md5 sha1 sha256 md5sum sha1sum sha256sum asc gpg sig'.split()

    def find_helper_files(self, file):
        files = []
        # Skip helper files
        if self.is_helper_file(file):
            return files

        for helper in 'metalink torrent mirrors'.split():
            if os.path.isfile(file + '.' + helper):
                files.append(file + '.' + helper)
        hashes = Hashes()
        hashes.find_files(file)
        files.extend(hashes.files)
        files.extend(hashes.find_signatures(file))
        return files

    def add_file(self):
        self.file = Metafile()
        self.files.append(self.file)
        self._valid = True

    def rewind(self):
        self.file = self.files[0]
        self._valid = True

    def prev(self):
        self._valid = True
        key = self.key()
        if key is not None and self.seek(key - 1):
            return self.file
        return False

    def current(self):
        if not self._valid:
            return False
        return self.file

    def key(self):
        if not self._valid:
            return None
        return self.files.index(self.file)

    def next(self):
        key = self.key()
        if key is not None and self.seek(key + 1):
            return self.file
        self._valid = False
        return False

    def end(self):
        self._valid = True
        self.file = self.files[-1]

    # Seek to metafile directly by index (or TODO: filename)
    def seek(self, key):
        try:
            self.file = self.files[key]
            return True
        except:
            return False

    def valid(self):
        return self._valid

    # Access metafile directly by index (or TODO: filename)
    def __getitem__(self, key):
        try:
            return self.files[key]
        except:
            pass

    # Remove metafile directly by index (or TODO: filename)
    def __delitem__(self, key):
        try:
            current_key = self.key()
            del self.files[key]
        except:
            return None
        if not self.files:
            self.file = Metafile()
            self.files.append(self.file)
        elif current_key == key:
            if len(self.files) > current_key:
                self.seek(current_key)
            else:
                self.end()

    def __setitem__(self, key, value):
        raise Exception("Setting metafiles is not supported.")

    # Does metafile with index exist? (or TODO: filename)
    def __contains__(self, key):
        try:
            self.files[key]
            return True
        except:
            return False

    def __iter__(self):
        return iter(self.files)

    def supported_protocols(self):
        return 'http ftp rsync bittorrent ed2k magnet'.split()

    def reset(self, overwrite_with_opts=True):
        """Reset mutable attributes to allow object reuse"""
        self.changelog = ""
        self.copyright = ""
        self.description = ""
        self.filename_absolute = ""
        self.generator = ""
        self.identity = ""
        self.license_name = ""
        self.license_url = ""
        self.logo = ""
        self.origin = ""
        self.pubdate = ""
        self.publisher_name = ""
        self.publisher_url = ""
        self.refreshdate = ""
        self.releasedate = ""
        self.screenshot = ""
        self.tags = []
        self.type = ""
        self.upgrade = ""
        self.version = ""
        self.resources = []
        self.signature = ""
        self.signature_type = ""
        self.size = ""
        self.urls = []

        self.errors = []
        self.url_prefix = ''
        self._valid = True

        self.hashes.reset()
        self.file.reset()
        # For multi-file torrent data
        self.files = [self.file]

        if overwrite_with_opts:
            self.apply_command_line_options()

class Torrent(object):
    def __init__(self, filename='', url=''):
        self.filename = filename
        self.url = url
        self.comment = ''
        self.files = []
        self.infohash = ''
        self.piecelength = 0
        self.pieces = []

    def parse(self, data=''):
        '''Main function to decode bencoded data and extract important information'''
        if not data and (self.filename or self.url):
            if self.filename:
                fp = open(self.filename, "rb")
                data = fp.read()
                fp.close()
            else:
                data = get_url(self.url)
        if not data:
            return {}
        self.data = data
        self.pos = 0
        root = self.bdecode()
        del self.data
        del self.pos

        if 'comment' in root:
            self.comment = root['comment']

        if 'info' in root and set(['pieces', 'piece length', 'name']).issubset(set(root['info'].keys())):
            info = root['info']
            name = info['name'].strip()
            if 'length' in info:
                self.files.append((name, info['length']))

            if 'files' in info:
                # Multi-file torrent: info['name'] is directory name and prefix for all file names
                name = [name]
                for f in info['files']:
                    if 'length' in f and 'path' in f:
                        self.files.append(('/'.join(name + f['path']), f['length']))

            self.piecelength = info['piece length']

            # Only decoding of single-file torrents is possible
            if len(self.files) == 1:
                self.pieces = self.decode_pieces(info['pieces'])

        return root

    def decode_pieces(self, pieces):
        if isinstance(pieces, str) and len(pieces) and len(pieces) % 20 == 0:
            def divide(seq, size):
                return [seq[i:i+size]  for i in xrange(0, len(seq), size)]
            return [binascii.hexlify(piece) for piece in divide(pieces, 20)]
        return []

    def encode_pieces(self, pieces):
        if isinstance(pieces, list) and len(pieces):
            return "".join([binascii.unhexlify(piece) for piece in pieces])
        return ''

    def create(self, data, filename=''):
        errors = []

        # Check given data
        if not 'files' in data:
            errors.append('files not found in torrent data')
        elif not isinstance(data['files'], list):
            errors.append('files must be a list of files')
        elif len(data['files']) != 1:
            errors.append('files must contain only a single file at the moment')
        else:
            for file in data['files']:
                if not isinstance(file, list) or len(file) != 2 or not isinstance(file[0], basestring) or not isinstance(file[1], (int, long)):
                    errors.append('elements of files must be a list of file data (name, size)')
                    break

        if not 'piece length' in data:
            errors.append('piece length not found in torrent data')
        elif not isinstance(data['piece length'], (int, long)) or not data['piece length']:
            errors.append('piece length must be a number')

        if not 'pieces' in data:
            errors.append('pieces not found in torrent data')
        elif not isinstance(data['pieces'], list) or not data['pieces']:
            errors.append('pieces must be a non-empty list')

        if not 'trackers' in data:
            errors.append('trackers not found in torrent data')
        elif not isinstance(data['trackers'], (basestring, list)):
            errors.append('trackers must be passed as string or list of tracker groups')
        elif isinstance(data['trackers'], basestring):
            trackers = split_values(data['trackers'], True, ',', ' ')
        else:
            trackers = data['trackers']

        if 'trackers' not in locals():
            pass
        elif not trackers:
            errors.append('list of trackers must not be empty')
        else:
            for tracker_group in trackers:
                if not isinstance(tracker_group, list) or not tracker_group:
                    errors.append('elements of trackers must be a list of tracker URLs (tracker group)')
                    break
                for tracker in tracker_group:
                    if not isinstance(tracker, basestring) or len(tracker) < 10:
                        errors.append('elements of tracker groups must be strings')
                        break

        for key in 'created by,comment'.split(','):
            if key in data and not isinstance(data[key], basestring):
                errors.append('%s must be a string' % key)

        if not filename and not self.filename:
            errors.append('no output filename given')

        if errors:
            return errors

        # Create torrent
        root = {}
        for key in 'created by,comment'.split(','):
            if key in data and len(data[key]) > 2:
                root[key] = encode_text(data[key])

        root['announce'] = trackers[0][0]
        if len(trackers) > 1 or len(trackers[0]) > 1:
            root['announce-list'] = trackers

        # At the moment only single-file torrents can be created because of missing pieces hashing for multi-file torrents
        # Multiple-file torrents may contain subdirectories (so no basename!)
        root['info'] = {}
        file = data['files'][0]
        root['info']['name'] = encode_text(os.path.basename(file[0]))
        root['info']['length'] = file[1]
        root['info']['piece length'] = data['piece length']
        root['info']['pieces'] = self.encode_pieces(data['pieces'])

        root['creation date'] = int(time.time())

        # Write file
        file = filename or self.filename
        if os.path.isfile(file) and not _get_opt('overwrite'):
            file += '.new'
        fp = open(file, "wb")
        fp.write(self.bencode(root))
        fp.close()
        print '%s%s' % (verbose is not False and 'Generated: ' or '', file)

        return errors

    def bdecode(self):
        c = self.data[self.pos]
        if 'd' == c:
            d = {}
            self.pos += 1
            while not self._is_end():
                start = self.pos + 6
                key = self._process_string()
                d[key] = self.bdecode()
                if not self.infohash and 'info' == key:
                    try:
                        import hashlib
                        hashfunc = hashlib.sha1
                    except:
                        # Import deprecated modules
                        import sha
                        hashfunc = sha.new
                    self.infohash = hashfunc(self.data[start:self.pos]).hexdigest().upper()
            self.pos += 1
            return d
        elif c == 'l':
            l = []
            self.pos += 1
            while not self._is_end():
                l.append(self.bdecode())
            self.pos += 1
            return l
        elif c == 'i':
            self.pos += 1
            pos = self.data.find('e', self.pos)
            i = int(self.data[self.pos:pos])
            self.pos = pos + 1
            return i
        if c.isdigit():
            return self._process_string()
        raise TypeError('Invalid bencoded string')

    def _process_string(self):
        pos = self.data.find(':', self.pos)
        length = int(self.data[self.pos:pos])
        self.pos = pos + 1
        text = self.data[self.pos:self.pos+length]
        self.pos += length
        return text

    def _is_end(self):
        return self.data[self.pos] == 'e'

    def bencode(self, x):
        from cStringIO import StringIO
        s = StringIO()
        self._bencode_value(x, s)
        return s.getvalue()

    def _bencode_value(self, x, s):
        t = type(x)
        if t in (int, long, bool):
            s.write('i%de' % x)
        elif isinstance(x, basestring):
            s.write('%d:%s' % (len(x), x))
        elif t in (list, tuple):
            s.write('l')
            for e in x:
                self._bencode_value(e, s)
            s.write('e')
        elif t is dict:
            s.write('d')
            keys = x.keys()
            keys.sort()
            for k in keys:
                self._bencode_value(k, s)
                self._bencode_value(x[k], s)
            s.write('e')
        else:
            raise TypeError('Unsupported data type to bencode: %s' % t.__name__)

class Mirrors(object):
    def __init__(self, filename='', url=''):
        self.locations = "af ax al dz as ad ao ai aq ag ar am aw au at az bs bh bd bb by be bz bj bm bt bo ba bw bv br io bn bg bf bi kh cm ca cv ky cf td cl cn cx cc co km cg cd ck cr ci hr cu cy cz dk dj dm do ec eg sv gq er ee et fk fo fj fi fr gf pf tf ga gm ge de gh gi gr gl gd gu gt gg gn gw gy ht hm va hn hk hu is in id ir iq ie im il it jm jp je jo kz ke ki kp kr kw kg la lv lb ls lr ly li lt lu mo mk mg mw my mv ml mt mh mq mr mu yt mx fm md mc mn me ms ma mz mm na nr np nl an nc nz ni ne ng nu nf mp no om pk pw ps pa pg py pe ph pn pl pt pr qa re ro ru rw sh kn lc pm vc ws sm st sa sn rs sc sl sg sk si sb so za gs es lk sd sr sj sz se ch sy tw tj tz th tl tg tk to tt tn tr tm tc tv ug ua ae gb us um uy uz vu ve vn vg vi wf eh ye zm zw uk".split()
        self.search_eclipse = re.compile(r'http://(?:(?:www\.)?eclipse\.org/[^/]+/download\.php\?file=([^&]+)|[^.]+\.eclipse.org(/eclipse/downloads/drops/[^/]+/)download\.php\?dropFile=([^&]+))')
        self.search_sourceforge = re.compile(r'https?://(?:downloads|(?:[^.]+)?\.?dl)\.(?:sourceforge|sf)\.net(/[^/]+/[^?]+)|https?://(?:sourceforge|sf).net/project/downloading.php\?group_id=\d+\&filename=([^&]+)')
        self.search_mysql = re.compile(r'(http://dev.mysql.com/get/Downloads/)([^/]+/)([^/]+)(?:/from/)?.*')
        self.search_link = re.compile(r'(?:(\d{1,3}|[A-Za-z]{2})\s+)?(?:(\d{1,3}|[A-Za-z]{2})\s+)?((?:(ftps?|https?|rsync|ed2k)://|(magnet):\?)[^" <>\r\n]+)')
        self.search_links = re.compile(r'(?:(\d{1,3}|[A-Za-z]{2})\s+)?(?:(\d{1,3}|[A-Za-z]{2})\s+)?((?:(?:ftps?|https?|rsync|ed2k)://|magnet:\?)[^" <>\r\n]+)')
        self.search_location = re.compile(r'(?:ftps?|https?|rsync)://([^/]*?([^./]+\.([^./]+)))/')
        self.search_btih = re.compile(r'xt=urn:btih:[a-zA-Z0-9]{32}')
        self.domains = {'postgresql.org':'at', 'tarpoon.org':'fr', 'carroll.aset.psu.edu':'us', 'yoxos.com':'de', 'ialto.org':'fr', 'linux-bg.org':'bg', 'fpt.net':'vn', 'harvard.edu':'us', 'sourceshare.org':'us', 'bevc.net':'si', 'ovh.net':'fr', 'clarkson.edu':'us', 'yousendit.com':'us', 'lunarpages.com':'us', 'kgt.org':'de', 'vt.edu':'us', 'lupaworld.com':'cn', 'pdx.edu':'us', 'mainseek.com':'pl', 'vmmatrix.net':'cn', 'mirrormax.net':'us', 'cn99.com':'cn', 'anl.gov':'us', 'mirrorservice.org':'gb', 'oleane.net':'fr', 'proxad.net':'fr', 'osuosl.org':'us', 'telia.net':'dk', 'mtu.edu':'us', 'utah.edu':'us', 'oakland.edu':'us', 'stanford.edu':'us', 'rit.edu':'us', 'calpoly.edu':'us', 'supp.name':'cz', 'wayne.edu':'us', 'tummy.com':'us', 'dotsrc.org':'dk', 'ubuntu.com':'sp', 'wmich.edu':'us', 'smenet.org':'us', 'bay13.net':'de', 'saix.net':'za', 'vlsm.org':'id', 'ac.uk':'gb', 'optus.net':'au', 'esat.net':'ie', 'unrealradio.org':'us', 'dudcore.net':'us', 'filearena.net':'au', 'ale.org':'us', 'linux.org':'se', 'ipacct.com':'bg', 'planetmirror.com':'au', 'tds.net':'us', 'ac.yu':'sp', 'stealer.net':'de', 'co.uk':'gb', 'iu.edu':'us', 'jtlnet.com':'us', 'umn.edu':'us', 'rfc822.org':'de', 'opensourcemirrors.org':'us', 'xmission.com':'us', 'xtec.net':'es', 'nullnet.org':'us', 'ubuntu-es.org':'es', 'roedu.net':'ro', 'mithril-linux.org':'jp', 'gatech.edu':'us', 'ibiblio.org':'us', 'kangaroot.net':'be', 'comactivity.net':'se', 'prolet.org':'bg', 'actuatechina.com':'cn', 'areum.biz':'kr', 'daum.net':'kr', 'daum.net':'kr', 'calvin.edu':'us', 'columbia.edu':'us', 'crazeekennee.com':'us', 'buffalo.edu':'us', 'uta.edu':'us', 'software-mirror.com':'us', 'unixheads.org':'us', 'optusnet.dl.sourceforge.net':'au', 'belnet.dl.sourceforge.net':'be', 'ufpr.dl.sourceforge.net':'br', 'puzzle.dl.sourceforge.net':'ch', 'switch.dl.sourceforge.net':'ch', 'dfn.dl.sourceforge.net':'de', 'mesh.dl.sourceforge.net':'de', 'ovh.dl.sourceforge.net':'fr', 'heanet.dl.sourceforge.net':'ie', 'garr.dl.sourceforge.net':'it', 'jaist.dl.sourceforge.net':'jp', 'surfnet.dl.sourceforge.net':'nl', 'nchc.dl.sourceforge.net':'tw', 'kent.dl.sourceforge.net':'uk', 'easynews.dl.sourceforge.net':'us', 'internap.dl.sourceforge.net':'us', 'superb-east.dl.sourceforge.net':'us', 'superb-west.dl.sourceforge.net':'us', 'umn.dl.sourceforge.net':'us'}

        self.reset(filename, url)

    def parse(self, filename='', url='', data='', plain=False):
        '''Main function to parse mirror data'''
        _filename = ''
        _url = ''
        from_url = False
        if not data and (filename or url or self.filename or self.url):
            if filename or (self.filename and not url):
                _filename = filename or self.filename
                fp = open(_filename, "rb")
                data = fp.read()
                fp.close()
            else:
                from_url = True
                _url = url and url or self.url
                data, _filename = self.parse_url(_url)
                if not re.search(r"[\n\r]", data):
                    data = get_url(data)
        if not data:
            return False

        # Filter links
        filter = _get_opt('filter')
        filter_regex = _get_opt('filter_regex')
        if filter_regex:
            filter_regex = re.compile(filter_regex)
        filter_from = _get_opt('filter_from')
        if filter_from:
            m = re.search(filter_from, data)
            if m: data = data[m.start():]
        filter_to = _get_opt('filter_to')
        if filter_to:
            m = re.search(filter_to, data)
            if m: data = data[:m.end()]

        _filename = _get_opt('filename') or _filename

        # Try to default filter by filename for URLs
        filtered = self.filter_custom or filter or filter_regex or filter_from or filter_to
        if from_url and not filtered:
            name = _filename or os.path.basename(_url)
            if '.' in name and '?' not in name and '#' not in name:
                filter = name
                filtered = True

        # Search links
        if plain:
            links = unique([self.search_link.search(line).group(1, 2, 3) for line in data.splitlines() if line.strip() and self.search_link.search(line)], 2)
        else:
            if self.search_links_custom:
                links = unique(self.search_links_custom.findall(data))
                self.search_links_custom = None
            else:
                links = unique(self.search_links.findall(data), 2)
        if self.filter_custom:
            links = [l for l in [self.filter_custom(l) for l in links] if l]
        else:
            links = [l for l in links if (not filter or filter in l[2]) and (not filter_regex or filter_regex.search(l[2]))]

        # Try to guess from URL and parsed links
        if not _filename:
            name = os.path.basename(_url)
            if name and '.' in name and '?' not in name and '#' not in name:
                for link in links:
                    if os.path.basename(self.filter_custom and link or link[2]) == name:
                        _filename = name
                        break
                # Filter afterwards
                if _filename and from_url and not filtered:
                    links = [l for l in links if os.path.basename(l[2]) == _filename]

        # Append filename
        if _filename:
            for i, link in enumerate(links):
                if link[2][-1] == '/':
                    links[i] = (link[0], link[1], link[2] + _filename)

        self.mirrors.extend([link for link in [self.parse_link(link, is_match=not self.filter_custom) for link in links] if link])
        if self.filter_custom: self.filter_custom = None
        return True

    def parse_url(self, url):
        m = self.search_eclipse.match(url)
        if m:
            group = m.groups()
            filepath = group[0] is None and ''.join(group[1:]) or group[0]
            return 'http://www.eclipse.org/downloads/download.php?file=' + filepath + '&format=xml', os.path.basename(filepath)
        m = self.search_sourceforge.match(url)
        if m:
            filepath = max(m.groups())

            # Path unknown, only filename -> download and parse URL
            if filepath[0] != '/':
                content = get_url(url)
                m = re.search('sourceforge.net(/sourceforge/[^/]+/' + re.escape(filepath) + ')', content)
                if not m:
                    return ''
                filepath = m.group(1)
            mirrors = ['http://' + mirror + filepath for mirror in self.domains.keys() if mirror.endswith('.sourceforge.net')]
            return "\n".join(mirrors), os.path.basename(filepath)
        m = self.search_mysql.match(url)
        if m:
            group = m.groups()
            filepath = ''.join(group)
            self.search_links_custom = re.compile(r'<a\s+[^>]*href="([^"]+)"')
            search_link = re.compile(r'^/get/(Downloads/[^/]+/[^/]+)/from/(.+)')
            def filter(link):
                m = search_link.search(link)
                return m and m.group(2) + m.group(1) or False
            self.filter_custom = filter
            return filepath + '/from/pick', os.path.basename(filepath)
        return url, ''

    # Return list (link, type, location, preference, language)
    def parse_link(self, link, location='', check_duplicate=True, preference='', is_match=False):
        m = self.search_link.match(is_match and link[2] or link)
        if m:
            # Check for location and preference information
            if is_match and not location: location = link[0]
            if is_match and not preference: preference = link[1]
            if location and location.isdigit() or preference and re.match('^[A-Za-z]{2}$', preference):
                location, preference = (preference, location)
            group = m.groups()
            type = group[2].endswith('.torrent') and 'bittorrent' or group[3] or group[4]
            # P2P links are not allowed to include location
            location = type not in 'bittorrent ed2k magnet'.split() and self.parse_location(group[2], location) or ''
            if group[2] in self.urls:
                if check_duplicate:
                    print >> sys.stderr, 'Duplicate mirror found:', group[2]
                    return None
            else:
                self.urls.append(group[2])
            preference = self.parse_preference(group[2], type, preference)
            return [group[2], type, location, preference]
        print >> sys.stderr, 'Invalid mirror link:', link
        return None

    # Return location if a valid 2-letter country code can be found
    def parse_location(self, link, location=''):
        if location and re.match('^[A-Za-z]{2}$', location):
            return location.lower()
        m = self.search_location.match(link)
        if m:
            group = m.groups()
            if group[2] in self.locations:
                return group[2]
            if group[1] in self.domains:
                return self.domains[group[1]]
            if group[0] in self.domains:
                return self.domains[group[0]]
            # Support ftp.us.postgresql.org style domain names
            prefix = group[0][:-(len(group[1])+1)]
            if len(group[0]) > len(group[1]) and re.search(r'(^|[^.]+\.)[a-z]{2}$', prefix) and prefix[-2:] in self.locations:
                return prefix[-2:]
            if location:
                self.domains[group[1]] = location
                return location
            if not group[0] in self.__class__.unknown_domains:
                print >> sys.stderr, 'Country unknown for:', group[0]
                self.__class__.unknown_domains.append(group[0])
        return location

    def parse_preference(self, link, type, preference=0):
        try:
            preference = int(preference)
            if 0 < preference <= 100: return str(preference)
        except:
            pass

        if _get_opt('preference', type):
            return _get_opt('preference', type)

        if 'bittorrent' == type:
            return '100'
        if 'ed2k' == type:
            return preference_ed2k
        if 'magnet' == type:
            if self.search_btih.search(link):
                return '99'
            return '90'
        if 'ftp' == type:
            return '30'
        return '10'

    def change_filename(self, new, old=''):
        if not new:
            return False

        if self.mirrors and not old:
            for url, type, location, preference in self.mirrors:
                if type not in "bittorrent ed2k magnet".split():
                    old = os.path.basename(url)
                    break

        if old: old = urllib.quote(old)
        new = urllib.quote(new)

        self.urls = []
        for mirror in self.mirrors:
            # Rename file
            if old: mirror[0] = mirror[0].replace(old, new)
            # Or append new name
            elif mirror[0][-1] == '/': mirror[0] += new
            self.urls.append(mirror[0])

        return True

    def add(self, mirrors, remove_others=False):
        if remove_others:
            self.remove_other_mirrors(mirrors)
        for mirror in mirrors.mirrors:
            if mirror[0] not in self.urls:
                self.mirrors.append(mirror)
                self.urls.append(mirror[0])

    def remove_other_mirrors(self, mirrors):
        types = "bittorrent ed2k magnet".split()
        self.mirrors = [mirror for mirror in self.mirrors if mirror[1] in types or mirror[0] in mirrors.urls]
        self.urls = [mirror[0] for mirror in self.mirrors]

    # basename of first URL, which is no P2P link
    def get_filename(self):
        p2p = 'bittorrent ed2k magnet'.split()
        for mirror in self.mirrors:
            if mirror[1] not in p2p:
                return urllib.unquote(os.path.basename(mirror[0]))
        return ''

    def reset(self, filename='', url=''):
        """Reset mutable attributes to allow object reuse"""
        self.filename = filename
        self.url = url
        self.search_links_custom = None
        self.filter_custom = None
        self.mirrors = []
        self.urls = []

    def __repr__(self):
        return "\n".join([link[0] for link in self.mirrors])

    unknown_domains = []

class Hashes(object):
    def __init__(self, filename='', url=''):
        self.search_hashes = r"^(([a-z0-9]{32,64})\s+(?:\?(AICH|BTIH|EDONKEY|SHA1|SHA256))?\*?([^\r\n]+))"
        # aich=ED2K AICH hash, btih=BitTorrent infohash (= magnet:?xt=urn:btih link)
        self.verification_hashes = 'md4 md5 sha1 sha256 sha384 sha512 rmd160 tiger crc32 btih ed2k aich'

        self.reset(filename, url)

    def init(self):
        self.pieces = []
        self.hashes = {}
        for hash in self.verification_hashes.split():
            self.hashes[hash] = {}

    def set_file(self, filename):
        if not filename.strip():
            return False
        self.filename_absolute = filename
        self.filename = os.path.basename(filename)
        for extension in 'md5sum sha1sum sha256sum md5 sha1 sha256'.split():
            if self.filename.lower().endswith('.' + extension):
                self.filename = self.filename[: - len(extension) -1]
                break
        return True

    def parse(self, filename='', data='', force_type='', filter_name=''):
        '''Main function to parse hash data'''
        self.set_file(filename)
        if not data and (self.filename or self.url):
            if self.filename:
                fp = open(self.filename_absolute or self.filename, "rb")
                data = fp.read()
                fp.close()
            else:
                data = get_url(self.url)
        if not data:
            return 0

        count = 0
        for line, hash, type, name in re.findall(self.search_hashes, data, re.MULTILINE):
            name = name.strip()
            if filter_name and filter_name != name:
                continue
            if 'EDONKEY' == type:
                type = 'ED2K'
            if type in ('ED2K', 'AICH', 'BTIH'):
                for _type, length in {'ED2K':32, 'AICH':32, 'BTIH':40}.items():
                    if _type == type:
                        if len(hash) != length:
                            print >> sys.stderr, 'Invalid %s hash: %s' % (type, line.strip())
                        elif not force_type or force_type.upper() == _type:
                            self.hashes[_type.lower()][name] = hash
                            count += 1
                        break
            else:
                for _type, length in {'md5':32, 'sha1':40, 'sha256':64}.items():
                    if len(hash) == length and not force_type or force_type.lower() == _type:
                        self.hashes[_type][name] = hash
                        count += 1
                        break
        return count

    # Find hash files parallel to filename
    def find_files(self, filename=''):
        if not filename:
            filename = self.filename

        name = ''
        if not filename or not os.path.dirname(filename):
            # Search in working directory
            directory = os.getcwd()
            if filename:
                name = filename + '.'
        elif os.path.isdir(filename):
            # Search only for general files in directory
            directory = os.path.realpath(filename)
        else:
            # Search for general and specific files in directory
            directory = os.path.dirname(filename)
            name = os.path.basename(filename) + '.'
        directory += os.sep

        files = []
        # Add general files
        for f in 'MD5SUMS SHA1SUMS SHA256SUMS'.split():
            files.append(directory + f)
        # Add specific files
        if name:
            for f in 'md5 sha1 sha256'.split():
                files.append(directory + name + f)
                files.append(directory + name + f + 'sum')

        found_files = [f for f in files if os.path.isfile(f)]
        self.files.extend(found_files)
        return len(found_files)

    def is_hash_file(self, file):
        _file = os.path.basename(file)
        for hash in 'md5sum sha1sum sha256sum md5 sha1 sha256'.split():
            if _file.lower().endswith('.' + hash):
                self.last_hash_file = _file[: - len(hash) - 1]
                return True
        for hash in 'MD5SUMS SHA1SUMS SHA256SUMS'.split():
            if _file.upper() == hash:
                self.last_hash_file = _file
                return True
        return False

    # Find signature files parallel to filename
    # TODO: Move signatures into Hashes class
    def find_signatures(self, filename=''):
        if not filename:
            filename = self.filename

        name = ''
        if not filename or not os.path.dirname(filename):
            # Search in working directory
            directory = os.getcwd()
            if filename:
                name = filename + '.'
        elif os.path.isdir(filename):
            # Search only for general files in directory
            directory = os.path.realpath(filename)
        else:
            # Search for general and specific files in directory
            directory = os.path.dirname(filename)
            name = os.path.basename(filename) + '.'
        directory += os.sep

        files = []
        # Add specific files
        if name:
            for f in 'asc gpg.sig gpg sig'.split():
                files.append(directory + name + f)

        found_files = [f for f in files if os.path.isfile(f)]
        return found_files

    def is_signature_file(self, file):
        _file = os.path.basename(file)
        for signature in 'asc gpg.sig gpg sig'.split():
            if _file.lower().endswith('.' + signature):
                self.last_hash_file = _file[: - len(signature) - 1]
                return True
        return False

    # TODO: filter_name
    def parse_files(self):
        self.url = ''
        for file in self.files:
            self.parse(file)

    def has(self, hash):
        hash = hash.lower()
        if hash not in self.hashes or not self.hashes[hash]:
            return False
        h = self.hashes[hash]
        if self.filename:
            return self.filename in h and "" != h[self.filename].strip()
        return 1 == len(h) and "" != h.values()[0].strip()

    def has_one(self, hashes):
        for hash in hashes.split():
            if self.has(hash):
                return True

    def get(self, hash):
        hash = hash.lower()
        if not self.has(hash):
            return ""
        if self.filename:
            return self.hashes[hash][self.filename].strip()
        return self.hashes[hash].values()[0].strip()

    def get_all(self):
        return self.get_multiple(" ".join(self.hashes.keys()))

    def get_multiple(self, hashes):
        hashes_found = {}
        for hash in hashes.lower().split():
            if self.has(hash):
                hashes_found[hash] = self.get(hash)
        return hashes_found

    def remove(self, hashes):
        for hash in hashes.lower().split():
            if self.has(hash):
                self.hashes[hash].clear()

    def update(self, hashes):
        for hash, value in hashes.get_multiple(self.verification_hashes).items():
            if hash not in self:
                self[hash] = value

    # Array-access methods
    def __getitem__(self, hash):
        return self.get(hash)

    def __delitem__(self, hash):
        self.remove(hash)

    def __setitem__(self, hash, value):
        self.hashes[hash.lower()][self.filename or len(self.hashes[hash])] = value

    def __contains__(self, hash):
        return self.has(hash)

    def reset(self, filename='', url=''):
        """Reset mutable attributes to allow object reuse"""
        self.filename = ''
        self.filename_absolute = ''
        self.set_file(filename)
        self.url = url
        self.hashes = {}
        self.init()
        self.last_hash_file = ''
        self.pieces = []
        self.piecelength = 0
        self.piecetype = ''
        self.files = []

class OptParser(object):
    def __init__(self, long_options = []):
        self.opts = {}
        self._opts = {}
        self._positions = []
        self.errors = []

        self.init(long_options)

    def addError(self, msg):
        if not msg in self.errors:
            self.errors.append(msg)

    def parseValue(self, val, is_bool=False, inverse=False):
        if not is_bool: return val
        if val is None: return not inverse
        value = val.strip().lower()
        if value in '1 True yes y on enable'.split():
            return not inverse
        if value in '0 False no n off disable'.split():
            return inverse
        return val

    def getOpt(self, opt):
        if not opt in self.opts:
            self.addError("Option '%s' is unknown" % opt)
            return [None, False, 0]
        _opt = self._opts[self.opts[opt]]
        is_bool = 'bool' == _opt['type']
        required = _opt['required']
        return [_opt, is_bool, required]

    def cmp_option_length(self, a, b):
        len_a = len(a)
        len_b = len(b)
        if len_a != len_b:
            return cmp(len_a, len_b)
        return cmp(a, b)

    def getHelp(self):
        help = ''
        _options = []
        _len = 0
        for key in self._positions:
            option = self._opts[key]
            _opt = []
            for opt in sorted(option['options'], self.cmp_option_length):
                _opt.append('%s%s' % (len(opt) > 1 and '--' or '-', opt))
            _opt = ', '.join(_opt)
            if option['explanation'] and option['required']:
                _opt += '%s=%s%s' % (1 != option['required'] and '[' or '', option['explanation'], 1 != option['required'] and ']' or '')
            _options.append((_opt, option['help'] + "\n")) # TODO: os.linesep
            if len(_opt) > _len: _len = len(_opt)
        _len += 2
        for key, option in _options:
            help += ' ' + key.ljust(_len) + option
        return help

    # options string|array String means short options, dict means ZendFramework like long options
    # ['file|f=sFILE'=>'Input file (-: use STDIN)']
    def init(self, options = []):
        if not isinstance(options, list):
            return False
        for i in range(0, len(options), 2):
            _long, help = options[i:i+2]
            # Only associative array keys allowed
            if isinstance(_long, (int, long)) or _long.isdigit(): continue
            _long = _long.strip()
            if '' == _long: continue

            required = 0
            _type = 'bool'
            explanation = ''
            match = re.search('(=|-)([isw])(.+)?', _long)
            if match:
                _long = _long[:match.start()]
                match = match.groups()
                required = '=' == match[0] and 1 or 2
                _type = 'i' == match[1] and 'int' or 'string'
                explanation = match[2] is not None and match[2] or ''
            opts = unique(_long.split('|'))
            self._positions.append(_long)

            for opt in opts:
                # Overwrite existing short options
                if len(opt) == 1 and opt in self._opts:
                    del self._opts[opt]
                self.opts[opt] = _long
            self._opts[_long] = {'type':_type, 'required':required, 'help':help, 'explanation':explanation, 'options':opts}
        return True

    def parse(self, args, convert_hyphen=True):
        stdin = False
        opts     = {}
        non_opts = []
        # Predefine empty values
        for option in self._opts.values():
            for opt in option['options']:
                opts[convert_hyphen and opt.replace('-', '_') or opt] = None

        if not args:
            return [opts, non_opts, stdin, []]

        # args = list(args)

        length = len(args)
        skip = False
        for i, arg in enumerate(args):
            if skip:
                skip = False
                continue

            arg = arg.strip()
            if arg == '': continue
            if arg[0] != '-':
                non_opts.append(arg)
            elif arg == '-':
                stdin = True
            elif arg == '--':
                self.addError("Unknown option '--'")
            elif len(arg) > 1 and arg[1] == '-':
                opt = arg[2:]
                value = None
                has_value = '=' in arg
                if has_value:
                    opt, value = opt.split('=', 1)
                if not has_value and opt in self.opts and self._opts[self.opts[opt]]['required'] and i < length - 1 and (0 == len(args[i+1]) or '-' != args[i+1][0]):
                    has_value = True
                    value = args[i+1]
                    skip = True

                default = True
                if not opt in self.opts and re.match('^(disable|no)-', opt):
                    opt = opt[re.match('^(disable|no)-', opt).end():]
                    default = False
                _opt, is_bool, required = self.getOpt(opt)
                if not _opt: continue
                if is_bool:
                    value = self.parseValue(value, is_bool, not default)
                if not required and has_value and (not is_bool or not isinstance(value, bool)):
                    self.addError("--%s allows no value" % opt)
                elif 1 == required and not has_value:
                    self.addError("--%s requires a value" % opt)
                elif not has_value:
                    value = default
                if value is not None:
                    for option in _opt['options']:
                        opts[convert_hyphen and option.replace('-', '_') or option] = value
            else:
                # Parse short option
                default = True
                if re.match('^-(disable|no)-', arg):
                    arg = arg[re.match('^-(disable|no)-', arg).end() - 1:]
                    default = False
                opt = ''
                _len = len(arg)
                for j in range(1, _len):
                    if arg[j] == '=':
                        if _opt:
                            if required:
                                if _len - 1 == j:
                                    value = ''
                                else:
                                    value = self.parseValue(arg[j+1:], is_bool, not default)
                                for option in _opt['options']:
                                    opts[option] = value
                            else:
                                self.addError("-%s allows no value" % opt)
                        break
                    opt = arg[j]
                    _opt, is_bool, required = self.getOpt(opt)
                    if not _opt: continue
                    value = default
                    if j < _len - 1 and '=' == arg[j+1]:
                        if j == _len - 2:
                            value = ''
                        else:
                            value = self.parseValue(arg[j+2:], is_bool, not default)
                    elif required and j == _len - 1 and i < length - 1 and (0 == len(args[i+1]) or '-' != args[i+1][0]):
                        value = self.parseValue(args[i+1], is_bool, not default)
                        skip = True
                    if 1 == required and isinstance(value, bool) and not is_bool:
                        self.addError("-%s requires a value" % opt)
                    else:
                        for option in _opt['options']:
                            opts[option] = value

        return [opts, non_opts, stdin, self.errors]

def doGetopt(args, long_options=[]):
    optParser = OptParser(long_options)
    return optParser.parse(args)

def _get_opt(opt, key=None):
    if opt not in _opts:
        return None
    if key is not None:
        try:
            return _opts[opt][key]
        except:
            return None
    return _opts[opt]

def _set_opt(opt, value, key=None):
    if key is not None:
        if opt not in _opts:
            _opts[opt] = {}
        _opts[opt][key] = value
    else:
        _opts[opt] = value


if __name__ == '__main__':
    main()
