"""yt-dlp extractor for AniKuro (anikuro.to / anikuro.ru / anikuro.site).

AniKuro has no yt-dlp support upstream, but it exposes a small JSON API:

    GET /api/v1/anime/{animeId}/episodes            -> episode list
    GET /api/v1/anime/{animeId}/full                -> title / artwork
    GET /api/v1/animepower/video/{animeId}/{epNum}   -> HLS sources + subtitles

The HLS manifests on the CDN refuse to load without a matching Referer, so every
format carries `http_headers`.
"""

from datetime import datetime
import json
import time
import urllib.parse
import urllib.request

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    determine_ext,
    join_nonempty,
    traverse_obj,
    url_or_none,
)

DOMAINS = ('anikuro.to', 'anikuro.ru', 'anikuro.site')

LANG_MAP = {
    'english': 'en',
    'japanese': 'ja',
    'spanish': 'es',
    'portuguese': 'pt',
    'french': 'fr',
    'german': 'de',
    'italian': 'it',
    'arabic': 'ar',
    'hindi': 'hi',
    'indonesian': 'id',
    'turkish': 'tr',
    'russian': 'ru',
}


def _short_lang(value):
    if not value:
        return None
    value = str(value).lower()
    return LANG_MAP.get(value, value.split('-')[0][:2] or 'und')


def _timestamp(value):
    try:
        return int(datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp())
    except Exception:
        return None


_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
       'Chrome/126.0 Safari/537.36')
_META_TTL = 1800     # series title/artwork is cached for 30 minutes
_META_TIMEOUT = 4    # the site occasionally stalls for 20s+, so cap the wait
_META_CACHE = {}

_IMAGE_MAGIC = (b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'RIFF', b'BM', b'II*\x00', b'MM\x00*')
_SEG_PROBE_CACHE = {}


def _fetch(url, headers, timeout, limit=None):
    req = urllib.request.Request(url, headers={'User-Agent': _UA, **headers})
    if limit:
        req.add_header('Range', f'bytes=0-{limit}')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _first_segment(playlist_url, headers, timeout, skip=0):
    """URLs of the first media segments of a (possibly master) HLS playlist."""
    text = _fetch(playlist_url, headers, timeout).decode('utf-8', 'replace')
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if any(ln.startswith('#EXT-X-STREAM-INF') for ln in lines):
        variant = next((ln for ln in lines if not ln.startswith('#')), None)
        if not variant:
            return []
        playlist_url = urllib.parse.urljoin(playlist_url, variant)
        text = _fetch(playlist_url, headers, timeout).decode('utf-8', 'replace')
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    media = [ln for ln in lines if not ln.startswith('#')]
    return [urllib.parse.urljoin(playlist_url, seg) for seg in media[skip:skip + 2]]


def _is_image_slideshow(source_url, headers):
    """True when an HLS source is a placeholder image sequence, not real video.

    AniKuro sometimes points an episode at an "HLS" stream whose segments are
    PNG/JPEG stills (one per few seconds). Downloading it wastes hundreds of
    megabytes and then breaks the MP3 conversion, so it is rejected up front.
    Two segments have to look like images, so a stream that merely starts with
    a poster frame is still treated as real video.
    """
    if source_url in _SEG_PROBE_CACHE:
        return _SEG_PROBE_CACHE[source_url]
    verdict = False
    try:
        segments = _first_segment(source_url, headers, 8)
        if segments:
            heads = [_fetch(seg, headers, 8, limit=8) for seg in segments]
            verdict = all(any(h.startswith(magic) for magic in _IMAGE_MAGIC) for h in heads)
    except Exception:
        verdict = False   # never reject a good source just because the probe failed
    _SEG_PROBE_CACHE[source_url] = verdict
    return verdict


def _meta_fast(base, anime_id):
    """Series title + artwork with a hard deadline and a cache.

    The app only needs a label for the queue row, so waiting on this request
    (which the site sometimes holds open for 20 seconds) is never worth it.
    """
    key = f'{base}/{anime_id}'
    hit = _META_CACHE.get(key)
    if hit and time.time() - hit[0] < _META_TTL:
        return hit[1]
    try:
        req = urllib.request.Request(
            f'{base}/api/v1/anime/{anime_id}/full',
            headers={'User-Agent': _UA, 'Accept': 'application/json',
                     'Referer': f'{base}/', 'Origin': base})
        with urllib.request.urlopen(req, timeout=_META_TIMEOUT) as r:
            data = json.loads(r.read().decode('utf-8', 'replace')).get('data') or {}
        titles = data.get('title') or {}
        title = (titles.get('userPreferred') or titles.get('english')
                 or titles.get('romaji') or titles.get('native'))
        if title:
            cover = url_or_none(traverse_obj(data, ('images', 'cover', {url_or_none}))
                                or traverse_obj(data, ('coverImage', 'extraLarge', {url_or_none}))
                                or traverse_obj(data, ('coverImage', 'large', {url_or_none})))
            value = (title, cover)
            _META_CACHE[key] = (time.time(), value)
            return value
    except Exception:
        pass
    return hit[1] if hit else (None, None)


class AniKuroIE(InfoExtractor):
    IE_NAME = 'anikuro'
    IE_DESC = 'AniKuro (anikuro.to, anikuro.ru, anikuro.site)'
    _ENABLED = True

    _VALID_URL = r'https?://(?:[^/?#]+\.)?(?P<domain>%s)/watch/(?P<id>[\w-]+)(?::(?P<ep>[\d.]+))?' % '|'.join(
        d.replace('.', r'\.') for d in DOMAINS)

    def _base(self, domain):
        return f'https://{domain}'

    def _api(self, base, path, referer=None, fatal=True, note=None, retries=3, delay=1.2):
        payload = {}
        for attempt in range(retries):
            payload = self._download_json(
                f'{base}/api/v1{path}',
                None,
                note=note or 'Requesting AniKuro API',
                errnote='Unable to reach the AniKuro API',
                fatal=fatal,
                headers={'Referer': referer or f'{base}/', 'Origin': base}) or {}
            if payload.get('data'):
                return payload
            if attempt < retries - 1:
                time.sleep(delay)
        return payload

    def _anime_title(self, data):
        title = traverse_obj(data, ('data', 'title', {dict})) or {}
        return (title.get('userPreferred') or title.get('english')
                or title.get('romaji') or title.get('native') or 'AniKuro')

    def _episodes(self, base, anime_id):
        data = self._api(base, f'/anime/{anime_id}/episodes', fatal=False)
        episodes = traverse_obj(data, ('data', 'episodes', ...)) or []
        if not episodes:
            raise ExtractorError('No episodes found for this page', expected=True)
        return episodes

    @staticmethod
    def _ep_number(episode):
        return str(episode.get('displayNumber')
                   or episode.get('number')
                   or traverse_obj(episode, ('id', {str}, {str.rpartition(':')}))[2]
                   or '1')

    def _entry(self, base, anime_id, ep_num, anime_title, episode=None, variant=None,
               metadata_only=False):
        watch_url = f'{base}/watch/{anime_id}:{ep_num}'
        # this endpoint regularly answers with an empty list, so keep trying
        normalized = []
        for attempt in range(2 if metadata_only else 5):
            if attempt:
                time.sleep(1.5)
            data = self._api(base, f'/animepower/video/{anime_id}/{ep_num}',
                             referer=watch_url, note='Looking up episode sources',
                             retries=1 if metadata_only else 3)
            normalized = traverse_obj(data, ('data', 'normalized', ...)) or []
            if normalized:
                break
        if not normalized:
            raise ExtractorError('No streams returned for this episode', expected=True)

        if variant:
            wanted = variant.lower()
            normalized = [v for v in normalized if (v.get('variant') or '').lower() == wanted] or normalized
        elif metadata_only:
            # analysing only needs to know whether the stream that would actually
            # be picked is usable, so look at the one variant that will be used
            # and its first source - that keeps adding a link to the queue fast
            normalized = [next((v for v in normalized
                                if (v.get('variant') or 'sub').lower() == 'sub'),
                               normalized[0])]

        formats, subtitles, chosen, junk = [], {}, None, 0
        for entry in normalized:
            name = (entry.get('variant') or 'sub').capitalize()
            headers = {'Referer': watch_url, 'Origin': base, **(entry.get('headers') or {})}
            found = []

            for sub in traverse_obj(entry, ('subtitles', ...)) or []:
                sub_url, lang = url_or_none(sub.get('url')), _short_lang(sub.get('lang') or sub.get('label'))
                if sub_url and lang:
                    sub_ext = determine_ext(sub_url, 'vtt')
                    if sub_ext in ('tx', 'ttml', 'xml', 'dfxp'):
                        sub_ext = 'ttml'
                    subtitles.setdefault(lang, []).append({'url': sub_url, 'ext': sub_ext})

            for src in traverse_obj(entry, ('sources', ...)) or []:
                src_url = url_or_none(src.get('url'))
                if not src_url:
                    continue
                quality = src.get('quality') or 'default'
                is_hls = bool(src.get('isM3U8')) or '.m3u8' in src_url
                if is_hls and (not metadata_only or not formats) \
                        and _is_image_slideshow(src_url, headers):
                    # a still-image "stream" - unusable, and there is no point
                    # spending a few hundred MB to find that out during download
                    junk += 1
                    continue
                if metadata_only:
                    # the caller only wants the title, so skip the manifest round
                    # trip - the real formats get extracted when it downloads
                    found = [{
                        'url': src_url,
                        'format_id': f'{name}-{quality}',
                        'ext': 'mp4',
                        'protocol': 'm3u8',
                    }]
                elif is_hls:
                    found = self._extract_m3u8_formats(
                        src_url, anime_id, ext='mp4', headers=headers,
                        m3u8_id=name, fatal=False, note='Downloading HLS manifest')
                else:
                    found = [{
                        'url': src_url,
                        'format_id': f'{name}-{quality}',
                        'ext': determine_ext(src_url) or 'mp4',
                    }]
                for fmt in found:
                    fmt['format_note'] = join_nonempty(name, quality, delim=' ')
                    formats.append(fmt)

            if found and (chosen is None or name.lower() == 'sub'):
                chosen = name

        if not formats and junk:
            raise ExtractorError(
                'AniKuro lists this episode but has published no real video for it - '
                'the only stream it offers is a placeholder image sequence with no audio',
                expected=True)
        if not formats and not metadata_only:
            raise ExtractorError('No usable stream formats for this episode', expected=True)

        if not variant and any(f['format_id'].startswith('Sub') for f in formats):
            # default to the subtitled stream so the audio matches the "[Sub]"
            # in the filename - ?variant=dub picks the other one
            formats = [f for f in formats if f['format_id'].startswith('Sub')]

        info = {
            'id': f'{anime_id}:{ep_num}',
            'title': join_nonempty(anime_title, f'Episode {ep_num}',
                                   f'[{chosen}]' if chosen else None, delim=' '),
            'formats': formats,
            'http_headers': {'Referer': watch_url, 'Origin': base},
        }
        if subtitles:
            info['subtitles'] = subtitles
        thumb = url_or_none((episode or {}).get('thumbnail') or (episode or {}).get('image'))
        if thumb:
            info['thumbnail'] = thumb
        description = (episode or {}).get('description') or (episode or {}).get('overview')
        if description:
            info['description'] = description
        if (episode or {}).get('airedAt'):
            info['release_timestamp'] = _timestamp(episode['airedAt'])
        return info

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        base = self._base(mobj.group('domain'))
        anime_id = mobj.group('id')
        ep_num = mobj.group('ep')
        variant = self._search_regex(r'[?&]variant=([^&#]+)', url, 'variant', default=None) \
            or next(iter(self._configuration_arg('variant', default=[])), None)
        # set by the app when it only needs the title for the queue row
        metadata_only = bool(self._configuration_arg('metadata_only', default=[]))

        anime_title, cover = _meta_fast(base, anime_id)
        if not anime_title:
            # fast path timed out - fall back to yt-dlp's requester (bounded by
            # the app's socket_timeout) so odd networks still work
            meta = self._api(base, f'/anime/{anime_id}/full', fatal=False, retries=1)
            anime_title = self._anime_title(meta)
            cover = url_or_none(traverse_obj(meta, ('data', 'images', 'cover', {url_or_none}))
                                or traverse_obj(meta, ('data', 'coverImage', 'extraLarge', {url_or_none}))
                                or traverse_obj(meta, ('data', 'coverImage', 'large', {url_or_none})))

        if ep_num:
            # the episode list is only used for descriptions/artwork, which the
            # queue doesn't display, so skip it when analysing
            episode = None
            if not metadata_only:
                episode = next((e for e in self._episodes(base, anime_id)
                                if self._ep_number(e) == ep_num), None)
            return self._entry(base, anime_id, ep_num, anime_title, episode, variant,
                               metadata_only=metadata_only)

        entries = []
        for episode in self._episodes(base, anime_id):
            num = self._ep_number(episode)
            entries.append(self.url_result(
                f'{base}/watch/{anime_id}:{num}', AniKuroIE.ie_key(), f'{anime_id}:{num}',
                join_nonempty(anime_title, f'Episode {num}', delim=' '),
                extractor_args={'variant': [variant]} if variant else None))

        result = self.playlist_result(entries, anime_id, f'{anime_title} (AniKuro)')
        if cover:
            result['thumbnails'] = [{'url': cover}]
        return result
