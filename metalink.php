<?php
/*
    Copyright (c) 2007 René Leonhardt, Germany.
    Copyright (c) 2007 Hampus Wessman, Sweden.

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if(not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

// TODO: Should be constants
$current_version = "1.1.0";
$preference_ed2k = "95";
$verbose = false;


function usage_and_exit($error_msg=null) {
  $progname = basename(__FILE__);

  $stream = $error_msg ? STDERR : STDOUT;
  if($error_msg)
    fwrite($stream, sprintf("ERROR: %s\n\n", $error_msg));
  fwrite($stream, sprintf("Metalink Generator %s by Hampus Wessman and Rene Leonhardt

Usage: %s [FILE|DIRECTORY]...

Create Metalink download files by parsing download files.
Helper files will be searched and parsed automatically:
.metalink, .torrent, .mirrors, .md5, .sha1, MD5SUMS, SHA1SUMS.
Glob wildcard expressions are allowed for filenames (openproj-0.9.6*).


Examples:

# Parse file1, search helper files file1.* and generate file1.metalink.
%s file1

# Parse directory, search download and helper files *.* and generate
# *.metalink for all non-helper files bigger than 1 MB.
%s directory

# Define URL prefix to save the original .metalink download URL
# http://openoffice.org/url/prefix/file1.metalink.
%s http://openoffice.org/url/prefix/ file1
", $GLOBALS['current_version'], $progname, $progname, $progname, $progname));
  exit($error_msg ? 1 : 0);
}

function get_first($x) {
    if(is_array($x) && array_key_exists(0, $x))
        return $x[0];
    return $x;
}

// http://www.tellinya.com/read/2007/08/28/gzdecode-function-for-php/
if (!function_exists('gzdecode')) {
    function &gzdecode ($data) {
        $headerlen = 10;
        $flags = ord(substr($data, 3, 1));
        if ($flags & 4) {
            $extralen = unpack('v' ,substr($data, 10, 2));
            $headerlen += 2 + $extralen[1];
        }
        if ($flags & 8) // Filename
            $headerlen = strpos($data, chr(0), $headerlen) + 1;
        if ($flags & 16) // Comment
            $headerlen = strpos($data, chr(0), $headerlen) + 1;
        if ($flags & 2) // CRC at end of file
            $headerlen += 2;
        if (false === $unpacked = gzinflate(substr($data, $headerlen)))
            return $data;
        return $unpacked;
    }
}

// Uses compression if available
function &get_url($url) {
  $context = stream_context_create(array('http'=>array('header'=>"Accept-encoding: gzip;q=1.0, deflate;q=0.9, identity;q=0.5\r\nUser-agent: Mozilla/5.0 (X11; U; Linux i686; de; rv:1.8.1.7) Gecko/20070914 Firefox/2.0.0.7")));
  $data = file_get_contents($url, FALSE, $context);
  foreach($http_response_header as $header)
    if(! strncasecmp('Content-Encoding:', $header, 17)) {
      if('deflate' == strtolower(trim(substr($header, 17))))
        $data = gzinflate($data);
      else
        $data = gzdecode($data);
      break;
    }
    return $data;
}

function generate_verification_and_resources($self, $add_p2p=true, $protocols=array(), $is_child=true) {
    $text = '';
    $indentation = $is_child ? '    ' : '  ';

    // Verification
    if($self->hashes->pieces or $self->signature or $self->hashes->has_one('ed2k md5 sha1 sha256')) {
        $text .= $indentation . '  <verification>' . "\n";
        foreach($self->hashes->get_multiple('ed2k md5 sha1 sha256') as $hash => $value)
            $text .= sprintf('%s    <hash type="%s">%s</hash>' . "\n", $indentation, $hash, strtolower($value));
        if(sizeof($self->hashes->pieces)) {
            $text .= $indentation . '    <pieces type="' . $self->hashes->piecetype . '" length="' . $self->hashes->piecelength . '">' . "\n";
            foreach($self->hashes->pieces as $id => $piece)
                $text .= $indentation . '      <hash piece="' . $id . '">' . $piece . '</hash>' . "\n";
            $text .= $indentation . '    </pieces>' . "\n";
        }
        if(trim($self->signature) != "")
            $text .= sprintf('%s    <signature type="%s">%s</signature>' . "\n", $indentation, $self->signature_type, $self->signature);
        $text .= $indentation . '  </verification>' . "\n";
    }

    // Add missing P2P resources implicitly if hashes are available
    if($add_p2p and isset($self->hashes['ed2k']) and $self->size and (property_exists($self, 'filename') and $self->filename) and ! array_key_exists('ed2k', $protocols)) {
        $aich = isset($self->hashes['aich']) ? 'h=' . strtoupper($self->hashes['aich']) . '|' : '';
        $url = sprintf("ed2k://|file|%s|%s|%s|%s/", rawurlencode(basename($self->filename)), $self->size, strtoupper($self->hashes['ed2k']), $aich);
        $self->add_url($url, "ed2k", "", $GLOBALS['preference_ed2k'], "", $is_child);
    }
    if($add_p2p and (($self->size and (property_exists($self, 'filename') and $self->filename)) or $self->hashes->has_one('btih ed2k sha1')) and ! array_key_exists('magnet', $protocols)) {
        $magnet = array();
        $hashes = array();
        if(property_exists($self, 'filename') and $self->filename) $magnet['dn'] = basename($self->filename);
        if($self->size) $magnet['xl'] = $self->size;
        if(isset($self->hashes['sha1'])) $hashes[] = sprintf("urn:sha1:%s", strtoupper($self->hashes['sha1']));
        if(isset($self->hashes['ed2k'])) {
            $hashes[] = sprintf("urn:ed2k:%s", strtolower($self->hashes['ed2k']));
            // Another way of including the ED2K hash: $hashes[] = sprintf("urn:ed2khash:%s", strtolower($self->hashes['ed2k']));
        }
        // TODO: tiger-tree root hash: http://wiki.shareaza.com/static/MagnetsMakeAndUse
        // TODO: kzhash
        if($magnet or $hashes) {
            $params = http_build_query($magnet);
            if($hashes)
                $params .= ($params ? '&' : '' ) . 'xt=' . implode('&xt=', $hashes);
            $url = sprintf("magnet:?%s", $params);
            $self->add_url($url, "magnet", "", "90", "", $is_child);
        }
        if(isset($self->hashes['btih'])) {
          $url = sprintf("magnet:?xt=urn:btih:%s", strtoupper($self->hashes['btih']));
          $self->add_url($url, "magnet", "", "99", "", $is_child);
        }
    }

    if($self->resources) {
      if(property_exists($self, 'maxconn_total') and "" != trim($self->maxconn_total) and "-" != trim($self->maxconn_total))
          $text .= $indentation . '  <resources maxconnections="' . $self->maxconn_total . '">' . "\n";
      else
          $text .= $indentation . "  <resources>\n";
      foreach($self->resources as $res) {
          $details = '';
          if(trim($res->location) != "")
              $details .= ' location="' . strtolower($res->location) . '"';
          if(trim($res->preference) != "") $details .= ' preference="' . $res->preference . '"';
          if(trim($res->conns) != "" and trim($res->conns) != "-") $details .= ' maxconnections="' . $res->conns . '"';
          $text .= sprintf('%s    <url type="%s"%s>%s</url>' . "\n", $indentation, $res->type, $details, htmlspecialchars($res->url));
      }
      $text .= $indentation . '  </resources>' . "\n";
    }

    return $text;
}

// return 0=no valid URL, 1=URL prefix, 2=normal URL
function is_url($url) {
    $u = @parse_url($url);
    if(! $u or ! (isset($u['scheme']) and isset($u['host']) and isset($u['path'])))
        return 0;
    $_is_url = in_array($u['scheme'], explode(' ', 'http https ftp ftps')) and ($u['host'] and $u['path']) and (! isset($u['query']) or ! $u['query']) and (! isset($u['fragment']) or ! $u['fragment']);
    if(! $_is_url)
        return 0;
    return $url[strlen($url)-1] == '/' ? 1 : 2;
}

function main($args=array()) {
    $renames = array();
    $url_prefix = '';
    $files = array();
    $files_skipped = array();
    $m = new Metalink();

    $_files = array();
    $_hashes = array();
    $_hashes_general = new Hashes();
    $_metalinks = array();
    $_metalink_general = '';
    $_mirrors = array();
    $_mirrors_general = new Mirrors();
    $_signatures = array();
    $_torrents = array();

    // Read arguments
    $args = array_merge(array_slice($_SERVER['argv'], 1), $args);

    // Search files and url_prefix
    foreach($args as $arg) {
        if(isdir($arg)) {
            foreach(glob(sprintf('%s%s*', realpath($arg), DIRECTORY_SEPARATOR)) as $file)
                if(isfile($file)) {
                    $_files[] = $file;
                    // Search parallel helper files
                    array_merge($_files, $m->find_helper_files($file));
                }
        } elseif(isfile($arg)) {
            $file = realpath($arg);
            $_files[] = $file;
            // Search parallel helper files
            $_files = array_merge($_files, $m->find_helper_files($file));
        } elseif(is_url($arg)) {
            if(1 == is_url($arg))
                $url_prefix = $arg;
            else
                // Add mirror
                $_mirrors_general->parse('', $arg);
        } else
            // Try glob expression (wildcards)
            foreach(glob($arg) as $file)
                if(isfile($file)) {
                    $_files[] = $file;
                    // Search parallel helper $files
                    $_files = array_merge($_files, $m->find_helper_files($file));
                }
    }
    $_files = array_unique($_files);

    // Categorize and filter files (hashes, mirrors, torrents, signatures)
    foreach($_files as $file) {
        $_file = basename($file);
        if(substr($_file, -9) == '.metalink')
            $_metalinks[substr($_file, 0, -9)] = $file;
        elseif(substr($_file, -8) == '.torrent')
            $_torrents[substr($_file, 0, -8)] = $file;
        elseif(substr($_file, -8) == '.mirrors' or strtolower($_file) == 'mirrors') {
            $key = strtolower($_file) == 'mirrors' ? $_file : substr($_file, 0, -8);
            $_mirrors[$key] = $file;
        } elseif($m->hashes->is_hash_file($_file)) {
            $hash_file = $m->hashes->last_hash_file;
            if(! in_array($hash_file, $_hashes))
                $_hashes[$hash_file] = array();
            if($hash_file == $_file)
                $key = dirname($file);
            else
                $key = substr($_file, strlen($hash_file)+1);
            $_hashes[$hash_file][$key] = $file;
        } elseif($m->hashes->is_signature_file($_file)) {
            $hash_file = $m->hashes->last_hash_file;
            if(! in_array($hash_file, $_signatures))
                $_signatures[$hash_file] = array();
            $_signatures[$hash_file][substr($_file, strlen($hash_file)+1)] = $file;
            $_signatures[$m->hashes->last_hash_file] = $file;
        } elseif(filesize($file) > 1000000)
            $files[$_file] = $file;
        else
            $files_skipped[] = $file;
    }

    if($files_skipped) {
        sort($files_skipped);
        fwrite(STDERR, sprintf("Skipped the following $files:\n%s", implode("\n", $files_skipped)));
    }

    // Mirror update mode
    if(! $files and sizeof($_metalinks) == 1 and sizeof($_mirrors) == 1)
        $files[key($_metalinks)] = key($_metalinks);

    // Filter general help files
    foreach(array_diff(array_keys($_metalinks), array_keys($files)) as $filename) {
        // TODO: Parse general metalink only once
        $_metalink_general = $_metalinks[$filename];
        unset($_metalinks[$filename]);
        break;
    }
    foreach(array_diff(array_keys($_mirrors), array_keys($files)) as $filename) {
        $_mirrors_general->parse($_mirrors[$filename]);
        unset($_mirrors[$filename]);
    }
    foreach(array_diff(array_keys($_hashes), array_keys($files)) as $filename)
        foreach($_hashes[$filename] as $file)
            $_hashes_general->parse($file);

    if(! $files)
        usage_and_exit(); // 'No $files to process'

    foreach($files as $filename => $file) {
        print sprintf('Processing %s', $file);
        $m = new Metalink();

        $_filename = $renames ? str_replace($filename($renames[0][0], $renames[0][1])) : $filename;

        // Parse metalink template
        if(isset($_metalinks[$_filename]))
            $m->load_file($_metalinks[$_filename]);
        elseif($_metalink_general)
            $m->load_file($_metalink_general);

        //if($m->file->filename and not $m->filename_absolute:
        //    $m->filename_absolute = $file[:-8]

        // Overwrite old mirror filenames from template
        // $filename = $filename.replace('-rc-', '-')
        $m->change_filename($filename);

        if(isset($_mirrors[$_filename])) {
            $m->clear_res('http ftp https ftps');
            $m->parse_mirrors($_mirrors[$filename], '', '', true, true);
            // $m->file->mirrors->change_filename($filename);
        } elseif($_mirrors_general->mirrors) {
            $_mirrors_general->change_filename($filename);
            $m->file->mirrors->add($_mirrors_general, true);
        }

        // Parse torrent files
        if(isset($_torrents[$_filename]))
            $m->parse_torrent($_torrents[$filename]);
        elseif(sizeof($_torrents) == sizeof($files) and sizeof($_torrents) == 1)
            $m->parse_torrent(current($_torrents));

        // Parse hash files
        $_hashes_general->set_file($file);
        $m->file->hashes->update($_hashes_general);
        if(isset($_hashes[$_filename])) {
            $m->file->hashes->files = array_values($_hashes[$filename]);
            $m->file->hashes->parse_files();
        }
        $m->file->hashes->set_file($file);

        if(isfile($file))
            // Scan file for remaining hashes
            $m->scan_file($file);

        $m->url_prefix = $url_prefix;
        $m->generate(true);
    }
}


class Resource {
    function __construct($url, $type="default", $location="", $preference="", $conns="") {
        $this->errors = array();
        $this->url = $url;
        $this->location = $location;
        if($type == "default" or trim($type) == "") {
            if(substr($url, -8) == ".torrent")
                $this->type = "bittorrent";
            else {
                $chars = strpos($url, ":");
                $this->type = substr($url, 0, $chars);
            }
        } else
            $this->type = $type;
        $this->preference = (string) $preference;
        if(trim($conns) == "-" or trim($conns) == "")
            $this->conns = "-";
        else
            $this->conns = $conns;
    }

    function validate() {
        if($this->url.strip() == "")
            $this->errors[] = "Empty URLs are not allowed!";
        $allowed_types = array("ftp", "ftps", "http", "https", "rsync", "bittorrent", "magnet", "ed2k");
        if(! in_array($this->type, $allowed_types))
            $this->errors[] = "Invalid URL: " . $this->url . '.';
        elseif(in_array($this->type, array('http', 'https', 'ftp', 'ftps', 'bittorrent')))
            if(! preg_match('°\w+://.+\..+/.*°', $this->url))
                $this->errors[] = "Invalid URL: " . $this->url . '.';
        if(trim($this->location) != "") {
            $iso_locations = array("AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "KH", "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MK", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "AN", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "SH", "KN", "LC", "PM", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SK", "SI", "SB", "SO", "ZA", "GS", "ES", "LK", "SD", "SR", "SJ", "SZ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW", "UK");
            if(! in_array(strtoupper($this->location), $iso_locations))
                $this->errors[] = $this->location . " is not a $valid country code.";
        }
        if($this->preference != "") {
            if(is_numeric($this->preference)) {
                $pref = intval($this->preference);
                if($pref < 0 or $pref > 100)
                    $this->errors[] = "Preference must be between 0 and 100, not " . $this->preference . '.';
            } else
                $this->errors[] = "Preference must be a number, between 0 and 100.";
        }
        if(trim($this->conns) != "" and trim($this->conns) != "-") {
            if(is_numeric($this->conns)) {
                $conns = intval($this->conns);
                if($conns < 1)
                    $this->errors[] = "Max connections must be at least 1, not " . $this->conns . '.';
                elseif($conns > 20)
                    $this->errors[] = "You probably don't want max connections to be as high as " . $this->conns . '!';
            } else
                $this->errors[] = "Max connections must be a positive integer, not " . $this->conns . ".";
        }
        return sizeof($this->errors) == 0;
    }
}

class Metafile {
    function __construct() {
        $this->changelog = "";
        $this->description = "";
        $this->filename = "";
        $this->identity = "";
        $this->language = "";
        $this->logo = "";
        $this->maxconn_total = "";
        $this->mimetype = "";
        $this->os = "";
        // TODO: $this->relations = ""; ?
        $this->releasedate = "";
        $this->screenshot = "";
        $this->signature = "";
        $this->signature_type = "";
        $this->size = "";
        $this->tags = array();
        $this->upgrade = "";
        $this->version = "";

        $this->hashes = new Hashes();
        $this->mirrors = new Mirrors();
        $this->resources = array();
        $this->urls = array();

        $this->errors = array();
    }

    function clear_res($types='') {
        if(! trim($types)) {
            $this->resources = array();
            $this->urls = array();
        } else {
            $_types = explode(' ', trim($types));
            $new_resources = array();
            $this->urls = array();
            foreach($this->resources as $res)
                if(! in_array($res->type,  $_types)) {
                    $new_resources[] = $res;
                    $this->urls[] = $res->url;
                }
            $this->resources = $new_resources;
        }
    }

    function add_url($url, $type="default", $location="", $preference="", $conns="", $add_to_child=true) {
        if(! in_array($url, $this->urls) and $this->mirrors->parse_link($url, $location)) {
            $this->resources[] = new Resource($url, $type, $location, $preference, $conns);
            $this->urls[] = $url;
            return true;
        }
        return false;
    }

    function add_res($res) {
        if(! in_array($url, $this->urls)) {
            $this->resources[] = $res;
            $this->urls[] = $res->url;
            return true;
        }
        return false;
    }

    function scan_file($filename, $use_chunks=true, $max_chunks=255, $chunk_size=256, $progresslistener=null) {
        GLOBAL $verbose;
        if($verbose) print "Scanning file...\n";
        // Filename and size
        $this->filename = basename($filename);
        if(! $this->hashes->filename)
            $this->hashes->filename = $this->filename;
        $size = filesize($filename);
        $this->size = (string) $size;
        $piecelength_ed2k = 9728000;

        $known_hashes = $this->hashes->get_multiple('ed2k md5 sha1 sha256');
        // If all hashes and pieces are already known, do nothing
        if(4 == sizeof(known_hashes) and $this->hashes->pieces)
            return true;

        // Calculate piece $length
        if($use_chunks) {
            $minlength = $chunk_size*1024;
            $this->hashes->piecelength = 1024;
            while($size / $this->hashes->piecelength > $max_chunks or $this->hashes->piecelength < $minlength)
                $this->hashes->piecelength *= 2;
            if($verbose) print "Using piecelength " . $this->hashes->piecelength . " (" . ($this->hashes->piecelength / 1024) . " KiB)\n";
            $numpieces = $size / $this->hashes->piecelength;
            if($numpieces < 2) $use_chunks = false;
        }
        $hashes = array();
        // Try to use hash extension
        if(extension_loaded('hash')) {
            $hashes['md4'] = hash_init('md4');
            $hashes['md5'] = hash_init('md5');
            $hashes['sha1'] = hash_init('sha1');
            $hashes['sha256'] = hash_init('sha256');
            $piecehash = hash_init('sha1');
            $md4piecehash = null;
            if($size > $piecelength_ed2k) {
                $md4piecehash = hash_init('md4');
                $length_ed2k = 0;
            }
        } else {
            print "Hash extension not available. No support for SHA-256 and ED2K.\n";
            $hashes['md4'] = null;
            $hashes['md5'] = null;
            $hashes['sha1'] = null;
            $hashes['sha256'] = null;
            $piecehash = '';
        }
        $piecenum = 0;
        $length = 0;

        // If some hashes are already available, do not calculate them
        if(isset($known_hashes['ed2k'])) {
            $known_hashes['md4'] = $known_hashes['ed2k'];
            unset($known_hashes['ed2k']);
        }
        foreach(array_keys($known_hashes) as $hash)
            $hashes[$hash] = null;

        // TODO: Don't calculate pieces if already known
        $this->hashes->pieces = array();
        if(! $this->hashes->piecetype)
            $this->hashes->piecetype = "sha1";

        $num_reads = ceil($size / 4096.0);
        $reads_per_progress = (int) ceil($num_reads / 100.0);
        $reads_left = $reads_per_progress;
        $progress = 0;
        $fp = fopen($filename, "rb");
        while(true) {
            $data = fread($fp, 4096);
            if($data == "") break;
            // Progress updating
            if($progresslistener) {
                $reads_left -= 1;
                if($reads_left <= 0) {
                    $reads_left = $reads_per_progress;
                    $progress += 1;
                    $result = $progresslistener->Update($progress);
                    if(get_first($result) == false) {
                        if($verbose) print "Cancelling scan!\n";
                        return false;
                    }
                }
            }
            // Process the $data
            if($hashes['md5']) hash_update($hashes['md5'], $data);
            if($hashes['sha1']) hash_update($hashes['sha1'], $data);
            if($hashes['sha256']) hash_update($hashes['sha256'], $data);
            $left = strlen($data);
            if($hashes['md4']) {
                if($md4piecehash) {
                    $l = $left;
                    $numbytes_ed2k = 0;
                    while($l > 0) {
                        if($length_ed2k + $l <= $piecelength_ed2k) {
                            if($numbytes_ed2k)
                                hash_update($md4piecehash, substr($data, $numbytes_ed2k));
                            else
                                hash_update($md4piecehash, $data);
                            $length_ed2k += $l;
                            $l = 0;
                        } else {
                            $numbytes_ed2k = $piecelength_ed2k - $length_ed2k;
                            hash_update($md4piecehash, substr($data, 0, $numbytes_ed2k));
                            $length_ed2k = $piecelength_ed2k;
                            $l -= $numbytes_ed2k;
                        }
                        if($length_ed2k == $piecelength_ed2k) {
                            hash_update($hashes['md4'], hash_final($md4piecehash, true));
                            $md4piecehash = hash_init('md4');
                            $length_ed2k = 0;
                        }
                    }
                } else
                    hash_update($hashes['md4'], $data);
            }
            if($use_chunks) {
                while($left > 0) {
                    if($length + $left <= $this->hashes->piecelength) {
                        if(is_string($piecehash))
                            $piecehash .= $data;
                        else
                            hash_update($piecehash, $data);
                        $length += $left;
                        $left = 0;
                    } else {
                        $numbytes = $this->hashes->piecelength - $length;
                        if(is_string($piecehash))
                            $piecehash .= substr($data, 0, $numbytes);
                        else
                            hash_update($piecehash, substr($data, 0, $numbytes));
                        $length = $this->hashes->piecelength;
                        $data = substr($data, $numbytes);
                        $left -= $numbytes;
                    }
                    if($length == $this->hashes->piecelength) {
                        if($verbose) print "Done with piece hash" . sizeof($this->hashes->pieces) . "\n";
                        $this->hashes->pieces[] = is_string($piecehash) ? sha1($piecehash) : hash_final($piecehash);
                        $piecehash = is_string($piecehash) ? '' : hash_init('sha1');
                        $length = 0;
                    }
                }
            }
        }
        if($use_chunks) {
            if($length > 0) {
                if($verbose) print "Done with piece hash" . sizeof($this->hashes->pieces) . "\n";
                $this->hashes->pieces[] = is_string($piecehash) ? sha1($piecehash) : hash_final($piecehash);
            }
            if($verbose) print "Total number of pieces:" . sizeof($this->hashes->pieces) . "\n";
        }
        fclose($fp);
        if($hashes['md4']) {
            if($md4piecehash and $length_ed2k)
                hash_update($hashes['md4'], hash_final($md4piecehash, true));
            $this->hashes['ed2k'] = hash_final($hashes['md4']);
        }
        foreach(explode(' ', 'md5 sha1 sha256') as $hash)
            if($hashes[$hash])
                $this->hashes[$hash] = hash_final($hashes[$hash]);
            elseif(function_exists($function = $hash . '_file'))
              $this->hashes[$hash] = call_user_func($function, $filename);
        if(sizeof($this->hashes->pieces) < 2) $this->hashes->pieces = array();
        // Convert to string
        $this->hashes->piecelength = (string) $this->hashes->piecelength;
        if($verbose) print "done\n";
        if($progresslistener) $progresslistener->Update(100);
        return true;
    }

    function validate() {
        foreach(explode(' ', 'screenshot logo') as $url)
            if(trim($this->$url) != "")
                if(! $this->_validate_url($this->$url))
                    $this->errors[] = "Invalid URL: " . $this->$url . ".\n";
        if(! $this->resources and ! $this->mirrors)
            $this->errors[] = "You need to add at least one URL!";
        foreach(array('md5'=>32, 'sha1'=>40, 'sha256'=>64) as $hash => $length)
            if(isset($this->hashes[$hash]))
                if(! preg_match(sprintf('°^[0-9a-fA-F]{%d}$°', $length), $this->hashes[$hash]))
                    $this->errors[] = sprintf("Invalid %s hash.", $hash);
        if(trim($this->size) != "") {
            if(is_numeric($this->size)) {
                $size = (int) $this->size;
                if($size < 0)
                    $this->errors[] = "File size must be at least 0, not " . $this->size . '.';
            } else
                $this->errors[] = "File size must be an integer, not " . $this->size . ".";
        }
        if(trim($this->maxconn_total) != "" and trim($this->maxconn_total) != "-") {
            if(is_numeric($this->maxconn_total)) {
                $conns = (int) $this->maxconn_total;
                if($conns < 1)
                    $this->errors[] = "Max connections must be at least 1, not " . $this->maxconn_total . '.';
                elseif($conns > 20)
                    $this->errors[] = "You probably don't want max connections to be as high as " . $this->maxconn_total . '!';
            } else
                $this->errors[] = "Max connections must be a positive integer, not " . $this->maxconn_total . ".";
        }
        if(trim($this->upgrade) != "")
            if(! in_array($this->upgrade, array("install", "uninstall, reboot, install", "uninstall, install")))
                $this->errors[] = 'Upgrade must be "install", "uninstall, reboot, install", or "uninstall, install".';
        return sizeof($this->errors) == 0;
    }

    function generate_file($add_p2p=true) {
        if(trim($this->filename) != "")
            $text = '    <file name="' . $this->filename . '">' . "\n";
        else
            $text = '    <file>' . "\n";
        // File info
        // TODO: relations
        foreach(explode(' ', 'identity size version language os changelog description logo mimetype releasedate screenshot upgrade') as $attr)
            if("" != trim($this->$attr))
                $text .= sprintf("      <%s>%s</%s>\n", $attr, htmlspecialchars($this->$attr), $attr);
        if($this->tags)
            $text .= '      <tags>' . implode(',', array_unique($this->tags)) . "</tags>\n";

        // Add mirrors
        foreach($this->mirrors->mirrors as $mirror) {
            list($url, $type, $location, $preference) = $mirror;
            // Add filename for relative urls
            if('/' == $url[strlen($url) - 1])
                $url .= basename($this->filename);
            $this->add_url($url, $type, $location, $preference);
        }

        $text .= generate_verification_and_resources($this, $add_p2p, $this->get_protocols());

        $text .= '    </file>' . "\n";
        return $text;
    }

    // Return list of found resource types
    function get_protocols() {
        $found = array();
        foreach($this->resources as $res)
            if(! array_key_exists($res->type, $found))
                $found[$res->type] = $res->url;
        return $found;
    }

    // Call with filename or url
    function parse_torrent($filename='', $url='') {
        $torrent = new Torrent($filename, $url);
        $torrent->parse();
        if(! $this->description)
            $this->description = $torrent->comment;
        $this->filename = $torrent->files[0][0];
        $this->size = $torrent->files[0][1];
        $this->hashes['btih'] = $torrent->infohash;
        $this->hashes->pieces = $torrent->pieces;
        $this->hashes->piecelength = $torrent->piecelength;
        $this->hashes->piecetype = 'sha1';
        if($url and ! $filename)
            $this->add_url($url, "bittorrent", "", "100");
        return $torrent->files;
    }

    // Call with filename, url or text
    function parse_mirrors($filename='', $url='', $data='', $plain=true, $remove_others=false) {
        $mirrors = new Mirrors($filename, $url);
        $mirrors->parse($filename, $data, $plain);
        $this->mirrors->add($mirrors, $remove_others);
    }

    // Call with filename, url or text
    function parse_hashes($filename='', $url='', $data='', $force_type='', $filter_name='') {
        $hashes = new Hashes($filename, $url);
        if($this->filename)
            $hashes->filename = $this->filename;
        $hashes->parse('', $data, $force_type, $filter_name);
        // TODO: Better setting of dict key
        $this->hashes->filename = $hashes->filename;
        $this->hashes->update($hashes);
    }

    function change_filename($new, $old='') {
        if(! $old)
            $old = $this->filename;
        if(! $old or ! $new)
            return false;

        $this->mirrors->change_filename($new, $old);


        $this->clear_res('ed2k magnet');

        $old = rawurlencode($old);
        $new = rawurlencode($new);

        foreach($this->resources as $res)
            $res->url = str_replace($old, $new, $res->url);

        return true;
    }

    function remove_other_mirrors($mirrors) {
        $_types = explode(" ", "bittorrent ed2k magnet");
        $new_resources = array();
        $this->urls = array();
        foreach($this->resources as $res)
            if(in_array($res->type,  $_types) or in_array($res->url, $mirrors->urls)) {
                $new_resources[] = $res;
                $this->urls[] = $res->url;
            }
        $this->resources = $new_resources;
        $this->mirrors->remove_other_mirrors($mirrors);
    }

    function replace_hashes($hashes) {
        $old = $hashes->filename;
        $hashes->filename = $this->filename;
        foreach($hashes->get_multiple('ed2k md5 sha1 sha256') as $hash => $value)
            $this->hashes[$hash] = $value;
        $hashes->filename = $old;
    }

    function get_urls() {
        $urls = array();
        foreach($this->resources as $res)
            $urls[] = $res->url;
        return $urls;
    }

}

class Metalink implements ArrayAccess, Iterator {
    private $_valid = false;

    function __construct() {
        $this->changelog = "";
        $this->copyright = "";
        $this->description = "";
        $this->filename_absolute = "";
        $this->identity = "";
        $this->license_name = "";
        $this->license_url = "";
        $this->logo = "";
        $this->origin = "";
        $this->pubdate = "";
        $this->publisher_name = "";
        $this->publisher_url = "";
        $this->refreshdate = "";
        $this->releasedate = "";
        $this->screenshot = "";
        $this->tags = array();
        $this->type = "";
        $this->upgrade = "";
        $this->version = "";

        // For multi-file torrent data
        $this->hashes = new Hashes();
        $this->resources = array();
        $this->signature = "";
        $this->signature_type = "";
        $this->size = "";
        $this->urls = array();

        $this->errors = array();
        $this->file = new Metafile();
        $this->files = array($this->file);
        $this->url_prefix = '';
        $this->_valid = true;
    }

    function clear_res($types='') {
        $this->file->clear_res($types);
    }

    function add_url($url, $type="default", $location="", $preference="", $conns="", $add_to_child=true) {
        if($add_to_child)
            return $this->file->add_url($url, $type, $location, $preference, $conns);
        elseif(! in_array($url, $this->urls) and $this->file->mirrors->parse_link($url, $location)) {
            $this->resources[] = new Resource($url, $type, $location, $preference, $conns);
            $this->urls[] = $url;
            return true;
        }
        return false;
    }

    function add_res($res) {
        return $this->file->add_res($res);
    }

    function scan_file($filename, $use_chunks=true, $max_chunks=255, $chunk_size=256, $progresslistener=null) {
        $this->filename_absolute = $filename;
        return $this->file->scan_file($filename, $use_chunks, $max_chunks, $chunk_size, $progresslistener);
    }

    function validate() {
        foreach(explode(' ', 'publisher_url license_url origin screenshot logo') as $url)
            if(trim($this->$url) != "")
                if(! $this->_validate_url($this->$url))
                    $this->errors[] = "Invalid URL: " . $this->$url . ".\n";
        foreach(array($this->pubdate, $this->refreshdate) as $d)
            if(trim($d) != "") {
                $_d = preg_replace('° (GMT|\+0000)$°', '', $d);
                // Unfortunately strptime() does not exist on Windows. date(DATE_RFC822), strftime()
                $check_date = function_exists('strptime') ? strptime('%a, %d %b %y %H:%M:%S %Z', $_d) : strtotime($_d);
                if(false === $check_date)
                    $this->errors[] = sprintf("Date must be of format RFC 822: %s", $d);
            }
        if(trim($this->type) != "")
            if(! in_array($this->type, array("dynamic", "static")))
                $this->errors[] = "Type must be either dynamic or static.";
        if(trim($this->upgrade) != "")
            if(! in_array($this->upgrade, array("install", "uninstall, reboot, install", "uninstall, install")))
                $this->errors[] = 'Upgrade must be "install", "uninstall, reboot, install", or "uninstall, install".';

        $valid_files = true;
        foreach($this->files as $f)
            $valid_files = $f->validate() and $valid_files;

        return $valid_files and sizeof($this->errors) == 0;
    }

    function get_errors() {
        $errors = $this->errors;
        foreach($this->files as $file)
            $errors = array_merge($errors, $file->errors);
        return $errors;
    }

    function validate_url($url) {
        if(substr($url, -8) == ".torrent")
            $type = "bittorrent";
        else {
            $chars = strpos($url, ":");
            $type = substr($url, 0, $chars);
        }
        $allowed_types = array("ftp", "ftps", "http", "https", "rsync", "bittorrent", "magnet", "ed2k");
        if(! in_array($type, $allowed_types))
            return false;
        elseif(in_array($type, array('http', 'https', 'ftp', 'ftps', 'bittorrent')))
            if(! preg_match('°\w+://.+\..+/.*°', $url))
                return false;
        return true;
    }

    function generate($filename='', $add_p2p=true) {
        $text = '<?xml version="1.0" encoding="utf-8"?>' . "\n";
        $origin = "";
        if($this->url_prefix) {
            $text .= sprintf('<?xml-stylesheet type="text/xsl" href="%smetalink.xsl"?>' . "\n", $this->url_prefix);
            if($this->origin) {
                if($filename and $filename !== true)
                    $metalink = basename($filename);
                else
                    $metalink = basename($this->filename_absolute);
                if(! substr($metalink, -9) == '.metalink')
                    $metalink .= '.metalink';
                $this->origin = $this->url_prefix . metalink;
            }
        }

        if(trim($this->origin) != "")
            $origin = 'origin="' . $this->origin . '" ';
        $pubdate = $this->pubdate ? $this->pubdate : gmdate('r');
        if('dynamic' == $this->type and $this->refreshdate)
            $refreshdate = '" refreshdate="' . $this->refreshdate;
        else
            $refreshdate = '';
        $type = "";
        if(trim($this->type) != "")
            $type = 'type="' . $this->type . '" ';
        $text .= '<metalink version="3.0" ' . $origin . $type . 'pubdate="' . $pubdate . $refreshdate . '" generator="Metalink Editor version ' . $GLOBALS['current_version'] . '" xmlns="http://www.metalinker.org/">' . "\n";
        $text .= $this->generate_info();
        $text .= "  <files>\n";
        // Add multi-file torrent information
        $text .= generate_verification_and_resources($this, $add_p2p, array(), false);
        $text_start = $text;
        $text_end = "  </files>\n";
        $text_end .= '</metalink>';

        $text_files = '';
        foreach($this->files as $f) {
            $text = $f->generate_file($add_p2p);
            $text_files .= $text;
            # TODO: Save separate .metalink for multi-file metalinks
        }
        $text = $text_start . $text_files . $text_end;

        $data = utf8_encode($text);
        if($filename) {
            if($filename === true)
                $filename = ($this->filename_absolute ? $this->filename_absolute : $this->file->filename) . '.metalink';
            // Create backup
            if(isfile($filename)) {
                $filename .= '.new';
                // @unlink($filename . '.bak');
                // rename($filename, $filename . '.bak');
            }
            file_put_contents($filename, $data);
            return true;
        }
        return $data;
        // TODO: return recode_string('latin1..utf8');
    }

    function generate_info() {
        $text = "";
        // Publisher info
        if(trim($this->publisher_name) != "" or trim($this->publisher_url) != "") {
            $text .= '  <publisher>' . "\n";
            if(trim($this->publisher_name) != "")
                $text .= '    <name>' . $this->publisher_name . '</name>' . "\n";
            if(trim($this->publisher_url) != "")
                $text .= '    <url>' . $this->publisher_url . '</url>' . "\n";
            $text .= '  </publisher>' . "\n";
        }
        // License info
        if(trim($this->license_name) != "" or trim($this->license_url) != "") {
            $text .= '  <license>' . "\n";
            if(trim($this->license_name) != "")
                $text .= '    <name>' . $this->license_name . '</name>' . "\n";
            if(trim($this->license_url) != "")
                $text .= '    <url>' . $this->license_url . '</url>' . "\n";
            $text .= '  </license>' . "\n";
        }
        // Release info
        foreach(explode(' ', 'identity version copyright description logo releasedate screenshot upgrade changelog') as $attr)
            if("" != trim($this->$attr))
                $text .= sprintf("  <%s>%s</%s>\n", $attr, htmlspecialchars($this->$attr), $attr);
        if($this->tags)
            $text .= '  <tags>' . implode(',', array_unique($this->tags)) . "</tags>\n";
        return $text;
    }

    function load_file($filename) {
        if(false === $doc = simplexml_load_file($filename))
            throw new Exception("Failed to parse metalink file! Please select a valid metalink.");
        foreach(explode(' ', 'origin pubdate refreshdate type') as $attr)
            $this->$attr = $this->get_attribute($doc, $attr);
        $publisher = $this->get_tag($doc, "publisher");
        if($publisher != null) {
            $this->publisher_name = $this->get_tagvalue($publisher, "name");
            $this->publisher_url = $this->get_tagvalue($publisher, "url");
        }
        $license = $this->get_tag($doc, "license");
        if($license != null) {
            $this->license_name = $this->get_tagvalue($license, "name");
            $this->license_url = $this->get_tagvalue($license, "url");
        }
        foreach(explode(' ', 'identity version copyright description logo releasedate screenshot upgrade changelog') as $attr)
            $this->$attr = $this->get_tagvalue($doc, $attr);
        $tags = explode(',', $this->get_tagvalue($doc, "tags"));
        foreach($tags as $tag)
            if($tag = trim($tag) and ! in_array($tag, $this->tags))
                $this->tags[] = $tag;
        $files = $this->get_tag($doc, "files");
        if($files == null)
            throw new Exception("Failed to parse metalink. Found no <files></files> tag.");
        $metafiles = $this->get_tag($files, "file");
        if($metafiles == null)
            throw new Exception("Failed to parse metalink. It must contain exactly one file description.");
        // TODO: File PHP SimpleXML bug
        // if(array_key_exists("name", $file)) $this->filename = (string) $file["name"];
        foreach($metafiles as $index => $file) {
            if(isset($file["name"])) $this->file->filename = (string) $file["name"];
            foreach(explode(' ', 'identity size version language os changelog description logo mimetype releasedate screenshot upgrade') as $attr)
                $this->file->$attr = $this->get_tagvalue($file, $attr);
            // TODO: $this->file->relations = $this->get_tagvalue($file, "relations");
            if($this->version == "")
                $this->version = $this->file->version;
            $tags = explode(',', $this->get_tagvalue($file, "tags"));
            foreach($tags as $tag)
                if($tag = trim($tag) and ! in_array($tag, $this->file->tags))
                    $this->file->tags[] = $tag;
            $this->file->hashes->filename = basename($this->file->filename);
            $verification = $this->get_tag($file, "verification");
            if($verification != null) {
                $signature = $this->get_tag($verification, "signature");
                if($signature) {
                    $this->file->signature = $this->get_text($signature, false);
                    $this->file->signature_type = $this->get_attribute($signature, "type");
                }
                // TODO: Is ed2k hash really allowed? Used by Metalink Gen - http://metalink.packages.ro
                foreach($verification->hash as $hash)
                    if(isset($hash["type"]))
                        if(in_array($type = strtolower((string) $hash["type"]), explode(" ", "ed2k md5 sha1 sha256")))
                            $this->file->hashes[$type] = strtolower($this->get_text($hash));
                $pieces = $this->get_tag($verification, "pieces");
                if($pieces != null) {
                    if(isset($pieces["type"]) and isset($pieces["length"])) {
                        $this->file->hashes->piecetype = (string) $pieces["type"];
                        $this->file->hashes->piecelength = (string) $pieces["length"];
                        $this->file->hashes->pieces = array();
                        foreach($pieces->hash as $hash)
                            $this->file->hashes->pieces[] = strtolower($this->get_text($hash));
                    } else
                        print "Load error: missing attributes in <pieces>\n";
                }
            }
            $resources = $this->get_tag($file, "resources");
            $num_urls = 0;
            if($resources != null) {
                $this->file->maxconn_total = $this->get_attribute($resources, "maxconnections");
                if(trim($this->file->maxconn_total) == "") $this->file->maxconn_total = "-";
                foreach($resources->url as $resource) {
                    $type = $this->get_attribute($resource, "type");
                    $location = $this->get_attribute($resource, "location");
                    $preference = $this->get_attribute($resource, "preference");
                    $conns = $this->get_attribute($resource, "maxconnections");
                    $url = trim($this->get_text($resource));
                    $this->add_url($url, $type, $location, $preference, $conns);
                    $num_urls += 1;
                }
            }
            if($num_urls == 0)
                throw new Exception("Failed to parse metalink. Found no URLs!");
            if($index < sizeof($metafiles) - 1)
                $this->add_file();
        }
        $this->rewind();
    }

    function get_attribute($element, $attribute) {
        // TODO: SimpleXML array_key_exists bug
        if(isset($element[$attribute]))
            return (string) $element[$attribute];
        return "";
    }

    function get_tagvalue($node, $tag) {
        if(property_exists($node, $tag))
            return $this->get_text($node->$tag);
        return "";
    }

    // HINT: only_first not needed for SimpleXML
    function get_tag($node, $tag) {
        if(property_exists($node, $tag))
            return $node->$tag;
        return null;
    }

    function get_text($node, $strip=true) {
        return $strip ? trim((string) $node) : (string) $node;
    }

    function __toString() {
        return $this->generate();
    }

    // Call with filename or url
    function parse_torrent($filename='', $url='') {
        $files = $this->file->parse_torrent($filename, $url);
        if(! $this->description)
            // Set torrent comment as description
            $this->description = $this->file->description;
        if(sizeof($files) > 1) {
            $this->hashes['btih'] = $this->file->hashes['btih'];
            $this->hashes->pieces = $this->file->hashes->pieces;
            $this->hashes->piecelength = $this->file->hashes->piecelength;
            $this->hashes->piecetype = $this->file->hashes->piecetype;
            $this->file->description = '';
            $this->file->hashes['btih'] = '';
            $this->file->hashes->pieces = array();
            if($url and ! $filename)
                $this->resources[] = array_pop($this->file->resources);
            $current_key = $this->key();
        } else
            // Remove single file description
            $this->file->description = '';
        foreach(array_slice($files, 1) as $file) {
            list($name, $size) = $file;
            $this->add_file();
            $this->file->filename = $name;
            $this->file->size = $size;
        }
        if(sizeof($files) > 1)
            $this->seek($current_key);
    }

    // Call with filename, url or text
    function parse_mirrors($filename='', $url='', $data='', $plain=true, $remove_others=false) {
        return $this->file->parse_mirrors($filename, $url, $data, $plain, $remove_others);
    }

    // Call with filename, url or text
    function parse_hashes($filename='', $url='', $data='', $force_type='', $filter_name='') {
        return $this->file->parse_hashes($filename, $url, $data, $force_type, $filter_name);
    }

    /** Set multiple attribute values. */
    function setattrs($attrs) {
        foreach($attrs as $attr => $value)
            if(property_exists($this, $attr))
                $this->$attr = $value;
            else
                $this->file->$attr = $value;
    }

    function change_filename($new, $old='') {
        $_old = $old ? $old : ($this->filename_absolute ? basename($this->filename_absolute) : $this->file->filename);
        if($_old)
            $this->origin = str_replace($_old, $new, $this->origin);
        return $this->file->change_filename($new, $old);
    }

    function remove_other_mirrors($mirrors) {
        $this->file->remove_other_mirrors($mirrors);
    }

    function replace_hashes($hashes) {
        $this->file->replace_hashes($hashes);
    }

    function is_helper_file($file) {
        $p = pathinfo($file);
        $filename = isset($p['filename']) ? $p['filename'] : '';
        $extension = isset($p['extension']) ? $p['extension'] : '';
        // Skip filenames without extension
        if($filename and ! $extension and in_array(strtoupper($filename), explode(' ', 'MD5SUMS SHA1SUMS SHA256SUMS')))
            return true;
        if(! ($filename and strlen($extension)))
            return false;

        return in_array(strtolower($extension), explode(' ', 'metalink torrent mirrors md5 sha1 sha256 md5sum sha1sum sha256sum asc gpg sig'));
    }

    function find_helper_files($file) {
        $files = array();
        // Skip helper files
        if($this->is_helper_file($file))
            return $files;

        foreach(explode(' ', 'metalink torrent mirrors') as $helper)
            if(isfile($file . '.' . $helper))
                $files[] = $file . '.' . $helper;
        $hashes = new Hashes();
        $hashes->find_files($file);
        $files = array_merge($files, $hashes->files);
        $files = array_merge($files, $hashes->find_signatures($file));
        return $files;
    }

    function add_file() {
        $this->files[] = new Metafile();
        $this->file = end($this->files);
        $this->_valid = true;
    }

    function rewind() {
        $this->_valid = false !== reset($this->files);
        if($this->_valid)
            $this->file = current($this->files);
    }

    function prev() {
        if($result = prev($this->files))
            $this->file = $result;
        $this->_valid = true;
        return $result;
    }

    function current() {
        return current($this->files);
    }

    function key() {
        return key($this->files);
    }

    function next() {
        if($result = next($this->files))
            $this->file = $result;
        else
            $this->_valid = false;
        return $result;
    }

    function end() {
        $this->_valid = true;
        return end($this->files);
    }

    function seek($key) {
        $current_key = $this->key();
        if($current_key == $key) return true;
        $this->rewind();
        if($key == 0) return true;
        while($result = $this->next())
            if($key == $this->key()) {
                $this->file = $result;
                return true;
            }
        reset($this->files);
        $this->seek($current_key);
        return false;
    }

    function valid() {
        return $this->_valid;
    }

    /**
    * Access metafile directly by index (TODO: or filename).
    * @param integer key
    * @return mixed value
    */
    function offsetGet($key) {
       if($this->seek($key))
           return $this->current();
    }

    /**
    * Setting metafiles is not supported!
    * @param mixed key (string or integer)
    * @param mixed value
    * @return void
    */
    function offsetSet($key, $value) {
        throw new Exception("Setting metafiles is not supported.");
    }

    /**
    * Remove metafile directly by index (TODO: or filename)
    * @param integer key
    * @return void
    */
    function offsetUnset($key) {
        if (! $this->offsetExists($key))
          return null;
        $current_key = $this->key();
        array_splice($this->files, $key, 1);
        if(! $this->files)
            $this->files = array(new Metafile());
        $this->file = $this->current();
    }

    /**
    * Does metafile with index (TODO: or filename) exist?
    * @param integer key
    * @return boolean
    */
    function offsetExists($key) {
       return array_key_exists($key, $this->files);
    }
}

class Torrent {
    function __construct($filename='', $url='') {
        $this->filename = $filename;
        $this->url = $url;
        $this->comment = '';
        $this->files = array();
        $this->infohash = '';
        $this->piecelength = 0;
        $this->pieces = array();
    }

    /** Main function to decode bencoded data and extract important information */
    function &parse(&$data='') {
        // Main function to decode bencoded data
        if(! $data and ($this->filename or $this->url)) {
            if($this->filename)
                $data = file_get_contents($this->filename);
            else
                $data =& get_url($this->url);
        }
        if(! $data)
            return array();
        $this->data = $data;
        $this->pos = 0;
        $root = $this->bdecode();
        unset($this->data);
        unset($this->pos);

        if(isset($root['comment']))
            $this->comment = $root['comment'];

        if(isset($root['info']) and 3 == sizeof(array_intersect(array('pieces', 'piece length', 'name'), array_keys($root['info'])))) {
            $info = $root['info'];
            $name = trim($info['name']);
            if(isset($info['length']))
                $this->files[] = array($name, $info['length']);

            if(isset($info['files'])) {
                // Multi-file torrent: info['name'] is directory name and prefix for all file names
                $name = array($name);
                foreach($info['files'] as $f)
                    if(isset($f['length']) and isset($f['path']))
                        $this->files[] = array(implode('/', array_merge($name, $f['path'])), $f['length']);
            }

            $this->piecelength = $info['piece length'];
            $pieces = $info['pieces'];
            if(strlen($pieces) and strlen($pieces) % 20 == 0)
                foreach(str_split($pieces, 20) as $piece)
                  $this->pieces[] = bin2hex($piece);
        }

        return $root;
    }

    function bdecode() {
        $c = $this->data[$this->pos];
        switch($c) {
            case 'd':
                $d = array();
                $this->pos++;
                while (!$this->_is_end()) {
                    $start = $this->pos + 6;
                    $key = $this->_process_string();
                    $d[$key] = $this->bdecode();
                    if(! $this->infohash and 'info' == $key and extension_loaded('hash'))
                        $this->infohash = strtoupper(hash('sha1', substr($this->data, $start, $this->pos - $start)));
                }
                $this->pos++;
                return $d;
            case 'l':
                $l = array();
                $this->pos++;
                while (!$this->_is_end())
                    $l[] = $this->bdecode();
                $this->pos++;
                return $l;
            case 'i':
                $this->pos++;
                $pos = strpos($this->data, 'e', $this->pos);
                $i = abs(intval(substr($this->data, $this->pos, $pos - $this->pos)));
                $this->pos = $pos + 1;
                return $i;
        }
        if (is_numeric($c))
            return $this->_process_string();
        throw new Exception('Invalid bencoded string');
    }

    function _process_string() {
        $pos = strpos($this->data, ':', $this->pos);
        $length = intval(substr($this->data, $this->pos, $pos - $this->pos));
        $this->pos = $pos + 1;
        $text = substr($this->data, $this->pos, $length);
        $this->pos += $length;
        return $text;
    }

    function _is_end() {
        return $this->data[$this->pos] == 'e';
    }
}

class Mirrors {
    function __construct($filename='', $url='') {
        $this->filename = $filename;
        $this->url = $url;
        $this->locations = explode(" ", "af ax al dz as ad ao ai aq ag ar am aw au at az bs bh bd bb by be bz bj bm bt bo ba bw bv br io bn bg bf bi kh cm ca cv ky cf td cl cn cx cc co km cg cd ck cr ci hr cu cy cz dk dj dm do ec eg sv gq er ee et fk fo fj fi fr gf pf tf ga gm ge de gh gi gr gl gd gu gt gg gn gw gy ht hm va hn hk hu is in id ir iq ie im il it jm jp je jo kz ke ki kp kr kw kg la lv lb ls lr ly li lt lu mo mk mg mw my mv ml mt mh mq mr mu yt mx fm md mc mn me ms ma mz mm na nr np nl an nc nz ni ne ng nu nf mp no om pk pw ps pa pg py pe ph pn pl pt pr qa re ro ru rw sh kn lc pm vc ws sm st sa sn rs sc sl sg sk si sb so za gs es lk sd sr sj sz se ch sy tw tj tz th tl tg tk to tt tn tr tm tc tv ug ua ae gb us um uy uz vu ve vn vg vi wf eh ye zm zw");
        $this->search_link = '°((?:(ftps?|https?|rsync|ed2k)://|(magnet):\?)[^" <>\r\n]+)°';
        $this->search_links = '°((?:(?:ftps?|https?|rsync|ed2k)://|magnet:\?)[^" <>\r\n]+)°';
        $this->search_location = '°(?:ftps?|https?|rsync)://([^/]*?([^./]+\.([^./]+)))/°';
        $this->search_btih = '°xt=urn:btih:[a-zA-Z0-9]{32}°';
        $this->domains = array('ovh.net'=>'fr', 'clarkson.edu'=>'us', 'yousendit.com'=>'us', 'lunarpages.com'=>'us', 'kgt.org'=>'de', 'vt.edu'=>'us', 'lupaworld.com'=>'cn', 'pdx.edu'=>'us', 'mainseek.com'=>'pl', 'vmmatrix.net'=>'cn', 'mirrormax.net'=>'us', 'cn99.com'=>'cn', 'anl.gov'=>'us', 'mirrorservice.org'=>'gb', 'oleane.net'=>'fr', 'proxad.net'=>'fr', 'osuosl.org'=>'us', 'telia.net'=>'dk', 'mtu.edu'=>'us', 'utah.edu'=>'us', 'oakland.edu'=>'us', 'calpoly.edu'=>'us', 'supp.name'=>'cz', 'wayne.edu'=>'us', 'tummy.com'=>'us', 'dotsrc.org'=>'dk', 'ubuntu.com'=>'sp', 'wmich.edu'=>'us', 'smenet.org'=>'us', 'bay13.net'=>'de', 'saix.net'=>'za', 'vlsm.org'=>'id', 'ac.uk'=>'gb', 'optus.net'=>'au', 'esat.net'=>'ie', 'unrealradio.org'=>'us', 'dudcore.net'=>'us', 'filearena.net'=>'au', 'ale.org'=>'us', 'linux.org'=>'se', 'ipacct.com'=>'bg', 'planetmirror.com'=>'au', 'tds.net'=>'us', 'ac.yu'=>'sp', 'stealer.net'=>'de', 'co.uk'=>'gb', 'iu.edu'=>'us', 'jtlnet.com'=>'us', 'umn.edu'=>'us', 'rfc822.org'=>'de', 'opensourcemirrors.org'=>'us', 'xmission.com'=>'us', 'xtec.net'=>'es', 'nullnet.org'=>'us', 'ubuntu-es.org'=>'es', 'roedu.net'=>'ro', 'mithril-linux.org'=>'jp', 'gatech.edu'=>'us', 'ibiblio.org'=>'us', 'kangaroot.net'=>'be', 'comactivity.net'=>'se', 'prolet.org'=>'bg', 'actuatechina.com'=>'cn', 'areum.biz'=>'kr', 'daum.net'=>'kr', 'daum.net'=>'kr', 'calvin.edu'=>'us', 'columbia.edu'=>'us', 'crazeekennee.com'=>'us', 'buffalo.edu'=>'us', 'uta.edu'=>'us', 'software-mirror.com'=>'us', 'optusnet.dl.sourceforge.net'=>'au', 'belnet.dl.sourceforge.net'=>'be', 'ufpr.dl.sourceforge.net'=>'br', 'puzzle.dl.sourceforge.net'=>'ch', 'switch.dl.sourceforge.net'=>'ch', 'dfn.dl.sourceforge.net'=>'de', 'mesh.dl.sourceforge.net'=>'de', 'ovh.dl.sourceforge.net'=>'fr', 'heanet.dl.sourceforge.net'=>'ie', 'garr.dl.sourceforge.net'=>'it', 'jaist.dl.sourceforge.net'=>'jp', 'surfnet.dl.sourceforge.net'=>'nl', 'nchc.dl.sourceforge.net'=>'tw', 'kent.dl.sourceforge.net'=>'uk', 'easynews.dl.sourceforge.net'=>'us', 'internap.dl.sourceforge.net'=>'us', 'superb-east.dl.sourceforge.net'=>'us', 'superb-west.dl.sourceforge.net'=>'us', 'umn.dl.sourceforge.net'=>'us');
        $this->mirrors = array();
        $this->urls = array();
    }

    /** Main function to parse mirror data */
    function parse($filename='', $data='', $plain=true) {
        if(! $data and ($filename or $this->filename or $this->url))
            if($filename or $this->filename)
                $data = file_get_contents($filename ? $filename : $this->filename);
            else
                $data =& get_url($this->url);
        if(! $data)
            return false;

        $links = array();
        if($plain) {
            foreach(preg_split("°[\r\n]+°", $data) as $link)
                if($link = trim($link))
                    $links[$link] = 1;
            if($links)
                $links = array_keys($links);
        } else {
            if(preg_match_all($this->search_links, $data, $matches))
                $links = array_unique($matches[1]);
        }
        foreach($links as $i => &$link) {
            $link = $this->parse_link($link);
            if(! $link)
                unset($links[$i]);
        }
        $this->mirrors = array_merge($this->mirrors, $links);
        return true;
    }

    // Return list (link, type, location, preference, language)
    function parse_link($link, $location='', $check_duplicate=true) {
        if(preg_match($this->search_link, $link, $m)) {
            $group = array_slice($m, 1);
            $type = substr($group[0], -8) == '.torrent' ? 'bittorrent' : ( $group[1] ? $group[1] : $group[2] );
            $_location = $this->parse_location($group[0], $location);
            if(in_array($group[0], $this->urls)) {
                if($check_duplicate) {
                    print 'Duplicate mirror found: ' . $group[0] . "\n";
                    return null;
                }
            } else
                $this->urls[] = $group[0];
            $preference = $this->parse_preference($group[0], $type);
            return array($group[0], $type, $_location, $preference);
        }
        print 'Invalid mirror link: ' . $link . "\n";
        return null;
    }

    // Return location if a valid 2-letter country code can be found
    function parse_location($link, $location='') {
        if(preg_match($this->search_location, $link, $m)) {
            $group = array_slice($m, 1);
            if(in_array($group[2], $this->locations))
                return $group[2];
            if(isset($this->domains[$group[1]]))
                return $this->domains[$group[1]];
            if(isset($this->domains[$group[0]]))
                return $this->domains[$group[0]];
            if($location) {
                $this->domains[$group[1]] = $location;
                return $location;
            }
            print 'Country unknown for: ' . $group[0] . "\n";
        }
        return '';
    }

    function parse_preference($link, $type) {
        if('bittorrent' == $type)
            return 100;
        if('ed2k' == $type)
            return $GLOBALS['preference_ed2k'];
        if('magnet' == $type) {
            if(preg_match($this->search_btih, $link))
                return 99;
            return 90;
        }
        return 10;
    }

    function change_filename($new, $old='') {
        if(! $new)
            return false;

        if(! $old)
            foreach($this->mirrors as $mirror) {
                list($url, $type) = $mirror;
                if(! in_array($type, explode(" ", "bittorrent ed2k magnet"))) {
                    $old = basename($url);
                    break;
                }
            }

        if($old) $old = rawurlencode($old);
        $new = rawurlencode($new);

        $this->urls = array();
        foreach($this->mirrors as &$mirror) {
            // Rename file
            if($old) $mirror[0] = str_replace($old, $new, $mirror[0]);
            // Or append new name
            elseif($mirror[0][strlen($mirror[0])-1] == '/') $mirror[0] .= $new;
            $this->urls[] = $mirror[0];
        }

        return true;
    }

    function add($mirrors, $remove_others=false) {
        if($remove_others)
            $this->remove_other_mirrors($mirrors);
        foreach($this->mirrors as $mirror)
            if(! in_array($mirror[0], $this->urls)) {
                $this->mirrors[] = $mirror;
                $this->urls[] = $mirror[0];
            }
    }

    function remove_other_mirrors($mirrors) {
        $types = explode(" ", "bittorrent ed2k magnet");
        $new_mirrors = array();
        $this->urls = array();
        foreach($this->mirrors as $mirror)
            if(in_array($mirror[1], $types) or in_array($mirror[0], $mirrors->urls)) {
                $new_mirrors[] = $mirror;
                $this->urls[] = $mirror[0];
            }
        $this->mirrors = $new_mirrors;
    }
}

class Hashes implements ArrayAccess {
    function __construct($filename='', $url='') {
        $this->filename = '';
        $this->filename_absolute = '';
        $this->set_file($filename);
        $this->url = $url;
        $this->search_hashes = "°^([a-z0-9]{32,64})\s+(?:\?(AICH|BTIH|EDONKEY|SHA1|SHA256))?\*?([^\r\n]+)°m";
        // aich=ED2K AICH hash, btih=BitTorrent infohash (= magnet:?xt=urn:btih link)
        $this->verification_hashes = 'md4 md5 sha1 sha256 sha384 sha512 rmd160 tiger crc32 btih ed2k aich';
        $this->hashes = array();
        $this->init();
        $this->last_hash_file = '';
        $this->pieces = array();
        $this->piecelength = 0;
        $this->piecetype = '';
        $this->files = array();
    }

    function init() {
        $this->hashes = array();
        foreach(explode(' ', $this->verification_hashes) as $hash)
            $this->hashes[$hash] = array();
    }

    function set_file($filename) {
        if(! trim($filename))
            return false;
        $this->filename_absolute = $filename;
        $this->filename = basename($filename);
        foreach(explode(' ', 'md5sum sha1sum sha256sum md5 sha1 sha256') as $extension)
            if(strtolower(substr($this->filename, - strlen($extension) +1)) == '.' . $extension) {
                $this->filename = substr($this->filename, 0, - strlen($extension) -1);
                break;
            }
        return true;
    }

    /** Main function to parse hash data */
    function parse($filename='', $data='', $force_type='', $filter_name='') {
        $this->set_file($filename);
        if(! $data and ($this->filename or $this->url))
            if($this->filename)
                $data = file_get_contents($this->filename_absolute ? $this->filename_absolute : $this->filename);
            else
                $data =& get_url($this->url);
        if(! $data)
            return 0;

        preg_match_all($this->search_hashes, $data, $matches, PREG_SET_ORDER);

        $count = 0;
        foreach($matches as $match) {
            list($line, $hash, $type, $name) = $match;
            $name = trim($name);
            if($filter_name and $filter_name != $name)
                continue;
            if('EDONKEY' == $type)
                $type = 'ED2K';
            if(in_array($type, array('ED2K', 'AICH', 'BTIH'))) {
                foreach(array('ED2K'=>32, 'AICH'=>32, 'BTIH'=>40) as $_type => $length)
                    if($_type == $type) {
                        if(strlen($hash) != $length)
                            print sprintf('Invalid %s hash: %s', $type, $line);
                        elseif(!$force_type or strtoupper($force_type) == $_type) {
                            $this->hashes[strtolower($_type)][$name] = $hash;
                            $count += 1;
                        }
                        break;
                    }
            } else
                foreach(array('md5'=>32, 'sha1'=>40, 'sha256'=>64) as $_type => $length)
                    if(strlen($hash) == $length and (! $force_type or strtolower($force_type) == $_type)) {
                        $this->hashes[$_type][$name] = $hash;
                        $count += 1;
                        break;
                    }
        }

        return $count;
    }

    // Find hash files parallel to filename
    function find_files($filename='') {
        if(! $filename)
            $filename = $this->filename;

        $name = '';
        if(! $filename or '.' == dirname($filename)) {
            // Search in working directory
            $directory = getcwd();
            if($filename)
                $name = $filename . '.';
        } elseif(is_dir($filename))
            // Search only for general files in directory
            $directory = realpath($filename);
        else {
            // Search for general and specific files in directory
            $directory = dirname($filename);
            $name = basename($filename) . '.';
        }
        $directory .= DIRECTORY_SEPARATOR;

        $files = array();
        // Add general $files
        foreach(explode(' ', 'MD5SUMS SHA1SUMS SHA256SUMS') as $f)
            $files[] = $directory . $f;
        // Add specific $files
        if($name)
            foreach(explode(' ', 'md5 sha1 sha256') as $f) {
                $files[] = $directory . $name . $f;
                $files[] = $directory . $name . $f . 'sum';
            }

        $found_files = array();
        foreach($files as $f)
            if(is_file($f))
                $found_files[] = $f;
        $this->files += $found_files;
        return sizeof($found_files);
    }

    function is_hash_file($file) {
        $_file = basename($file);
        foreach(explode(' ', 'md5sum sha1sum sha256sum md5 sha1 sha256') as $hash)
            if(strtolower(substr($_file, - strlen($hash) - 1)) == '.' . $hash) {
                $this->last_hash_file = substr($_file, 0, - strlen($hash) - 1);
                return true;
            }
        foreach(explode(' ', 'MD5SUMS SHA1SUMS SHA256SUMS') as $hash)
            if(strtoupper($_file) == $hash) {
                $this->last_hash_file = $_file;
                return true;
            }
        return false;
    }

    function is_signature_file($file) {
        $_file = basename($file);
        foreach(explode(' ', 'asc gpg.sig gpg sig') as $signature)
            if(strtolower(substr($_file, - strlen($signature) - 1)) == '.' . $signature) {
                $this->last_hash_file = substr($_file, 0, - strlen($signature) - 1);
                return true;
            }
        return false;
    }

    // TODO: filter_name
    function parse_files() {
        $this->url = '';
        foreach($this->files as $file)
            $this->parse($file);
    }

    function has($hash) {
        $hash = strtolower($hash);
        if(! isset($this->hashes[$hash]) or ! $this->hashes[$hash])
            return false;
        $h = $this->hashes[$hash];
        if($this->filename)
            return isset($h[$this->filename]) and "" != trim($h[$this->filename]);
        return 1 == sizeof($h) and "" != trim(current($h));
    }

    function has_one($hashes) {
        foreach(explode(' ', $hashes) as $hash)
            if($this->has($hash))
                return true;
    }

    function get($hash) {
        $hash = strtolower($hash);
        if(! $this->has($hash))
            return "";
        if($this->filename)
            return trim($this->hashes[$hash][$this->filename]);
        return trim(current($this->hashes[$hash]));
    }

    function get_all() {
        return $this->get_multiple(implode(" ", array_keys($this->hashes)));
    }

    function get_multiple($hashes) {
        $hashes_found = array();
        foreach(explode(' ', strtolower($hashes)) as $hash)
            if($this->has($hash))
                $hashes_found[$hash] = $this->get($hash);
        return $hashes_found;
    }

    function remove($hashes) {
        foreach(explode(' ', strtolower($hashes)) as $hash)
          if($this->has($hash))
              $this->hashes[$hash] = array();
    }

    function update($hashes) {
        foreach($hashes->get_multiple($this->verification_hashes) as $hash => $value)
            if(! isset($this[$hash]))
                $this[$hash] = $value;
    }

    // Array-access methods
    function offsetGet($hash) {
        return $this->get($hash);
    }

    function offsetSet($hash, $value) {
        $this->hashes[strtolower($hash)][$this->filename ? $this->filename : sizeof($this->hashes[$hash])] = $value;
    }

    function offsetUnset($hash) {
        $this->remove($hash);
    }

    function offsetExists($hash) {
        return $this->has($hash);
    }
}


if(__FILE__ == realpath($_SERVER['SCRIPT_NAME'])) {
    main();
}
