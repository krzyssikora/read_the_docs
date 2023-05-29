# coding=utf=8
from bs4 import BeautifulSoup
import urllib.request
import urllib.parse
# import requests
# url = ''
# r = requests.get(url)
# r.text
from w3lib.url import safe_url_string
import logging
import os
import json
from pathlib import Path

DOCS_MAIN_PAGE \
    = 'https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-nutmeg.master'
DOCS_TOC_PAGE = DOCS_MAIN_PAGE + '/index.html'

# _logger = logging.getLogger(f'{__name__}: ')
# _logger.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s : '
                           '%(asctime)s : '
                           '%(filename)s : '
                           '%(funcName)s(): '
                           '%(lineno)d:\t'
                           '%(message)s', level=logging.INFO)
_logger = logging.getLogger(f'{__name__}: ')


def _iri_to_uri(iri):
    return safe_url_string(iri, encoding="UTF-8")


def _json_dumps_tuple_keys(mapping: dict) -> str:
    string_keys = {json.dumps(k): v for k, v in mapping.items()}
    return json.dumps(string_keys)


def _json_loads_tuple_keys(string: str) -> dict:
    mapping = json.loads(string)
    return {tuple(json.loads(k)): v for k, v in mapping.items()}


def parse_href(href: str) -> (str, str, str):
    """
    parse_href('aaa/bbb.html#cc-ddd')
    Out: ('aaa/bbb.html', '#cc-ddd', '#aaa-bbb-cc-ddd')
    parse_href('aaa/bbb.html')
    Out: ('aaa/bbb.html', None, '#aaa-bbb')
    """
    ll = [x for x in href.split('#') if x]
    filename = ll[0]
    if len(ll) > 2:
        print('*' * 30)
        print(ll)
        print('*' * 30)
    old_id = ll[1] if len(ll) == 2 else None
    new_id = f'{filename.split(".")[0].replace("/", "-")}{f"-{old_id}" if old_id else ""}'
    return filename, old_id, new_id


def make_hrefs_absolute(toc_dict: dict) -> dict:
    for k, v in toc_dict.items():
        if not v['href'].startswith('https'):
            v['href'] = f"{DOCS_MAIN_PAGE}/{v['href']}"
    return toc_dict


class Parser:
    def __init__(self, from_json=True):
        self.from_json = from_json
        self.main_page_url = \
            'https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-nutmeg.master'
        self.toc_url = self.main_page_url + '/index.html'
        self.urls_json = Path(__file__).parent / 'data' / 'urls.json'
        self.ids_json = Path(__file__).parent / 'data' / 'ids.json'
        self.toc_json = Path(__file__).parent / 'data' / 'toc.json'

        self.urls = dict()
        self.ids = dict()
        self.toc = dict()
        self.html = ''

        if from_json:
            self.get_urls_from_json()
            self.get_ids_from_json()
            self.get_toc_from_json()
        else:
            self.get_urls()
            self.get_ids(self.urls)
            self.get_toc()
            self.save_as_json('urls')
            self.save_as_json('ids')
            self.save_as_json('toc')

        self.json_objects_dict = {
            'urls': (self.urls, self.urls_json),
            'ids': (self.ids, self.ids_json),
            'toc': (_json_dumps_tuple_keys(self.toc), self.toc_json)
        }

    def save_as_json(self, object_name: str) -> None:
        object_to_save, json_path = {
            'urls': (self.urls, self.urls_json),
            'ids': (self.ids, self.ids_json),
            'toc': (_json_dumps_tuple_keys(self.toc), self.toc_json)
        }.get(object_name)

        with open(json_path, "w") as outfile:
            json.dump(object_to_save, outfile)

    def get_toc_from_json(self):
        with open(self.toc_json) as infile:
            string = json.load(infile)
        self.toc = _json_loads_tuple_keys(string)

    def get_ids_from_json(self):
        with open(self.ids_json) as infile:
            self.ids = json.load(infile)

    def get_urls_from_json(self):
        with open(self.urls_json) as infile:
            self.urls = json.load(infile)

    def get_urls(self) -> None:
        _logger.info('collecting urls')
        url = _iri_to_uri(self.toc_url)
        # get urls from main page TOC
        with urllib.request.urlopen(url) as response:
            output = response.read().decode()
            soup = BeautifulSoup(output, 'html.parser')
        content = soup.find_all('div', {"class": 'wy-menu wy-menu-vertical'})[0]
        toc = content.find('ul')
        lis = toc.find_all('li')
        for li in lis:
            a_tag = li.find_all('a')
            for i in a_tag:
                contents = [x for x in i.contents if not x.name][0]
                idxs, title = contents.split('. ')
                key_idx = (tuple(map(int, idxs.split('.'))))
                chapter = key_idx[0]
                href = i.get('href').split('#')[0]
                href = f"{DOCS_MAIN_PAGE}/{href}"
                self.urls[chapter] = self.urls.get(chapter) or list()
                if href not in self.urls[chapter]:
                    self.urls[chapter].append(href)
        _logger.info('url collected')

    def get_ids(self, urls_dict: dict) -> None:
        _logger.info('collecting ids...')
        # {chapter_number: {url: {old_id: new_id}}}
        for chapter, urls in urls_dict.items():
            _logger.info('... from chapter %s', chapter)
            self.ids[chapter] = dict()
            for url in urls:
                filename = url[len(DOCS_MAIN_PAGE) + 1:].split(".")[0].replace("/", "-")
                self.ids[chapter][url] = dict()
                self.ids[chapter][url][''] = filename
                with urllib.request.urlopen(url) as response:
                    output = response.read().decode()
                    soup = BeautifulSoup(output, 'html.parser')
                    tags_with_id = soup.find_all(lambda t: t.has_attr('id'))
                    for tag in tags_with_id:
                        old_id = tag.attrs.get('id')
                        new_id = f'{filename}{f"-{old_id}" if old_id else ""}'
                        self.ids[chapter][url][old_id] = new_id
        _logger.info('ids collected')

    def _update_ids(self, key_idx: tuple, url: str, old_id: str, new_id: str) -> None:
        saved_new_id = self.ids[key_idx[0]][url.split('#')[0]].get(old_id)
        if saved_new_id is None:
            self.ids[key_idx[0]][url.split('#')[0]][old_id] = new_id
        elif new_id != saved_new_id:
            _logger.error(f"key_idx: {key_idx}")
            _logger.error(f"url: {url}")
            _logger.error(f"new_id: {new_id}")
            _logger.error(f"saved_new_id: {saved_new_id}")

    def update_toc_dict(self, url: str) -> None:
        def get_id_and_title_from_ascendant_section(t: BeautifulSoup) -> (int or None, str):
            p = t.parent
            while True:
                if p.name == 'section' and p.attrs.get('id'):
                    tid = p.attrs.get('id')
                    break
                p = p.parent
            p = t.parent
            title_l = [x.strip(' \n') for x in p.contents if not x.name]
            title_l = [x for x in title_l if x]
            if title_l:
                ttl = title_l[0]
            else:
                try:
                    ttl = p.find('code').find('span').string
                except Exception as exc:
                    print('key_idx: ', key_idx)
                    print('tag: ', t)
                    print('parent: ', p.name)
                    print('filename: ', filename)
                    print('old_id: ', old_id)
                    print('new_id: ', new_id)
                    print('title: ', title)
                    print('.' * 30)
                    print(p.parent)
                    raise exc
            return tid, ttl

        with urllib.request.urlopen(url) as response:
            output = response.read().decode()
            soup = BeautifulSoup(output, 'html.parser')
            sections = soup.find_all('section')
            section = [s for s in sections if s.attrs.get('id')][0]
            # get ids from class='session-number'
            section_numbers_tags = section.find_all(class_='section-number')
            filename = url[len(DOCS_MAIN_PAGE) + 1:]
            for tag in section_numbers_tags:
                key_idx = tuple(map(int, tag.string.strip('. ').split('.')))
                if key_idx in self.toc:
                    continue

                old_id, title = get_id_and_title_from_ascendant_section(tag)
                new_id = f'{filename.split(".")[0].replace("/", "-")}{"-" + old_id if old_id else ""}'
                self._update_ids(key_idx, url, old_id, new_id)

                self.toc[key_idx] = {
                    'title': title,
                    'filename': filename,
                    'old_id': old_id,
                    'new_id': new_id,
                    'href': f"{url}#{old_id}"
                }

    def get_toc(self) -> None:
        _logger.info('collecting toc from main page')
        url = _iri_to_uri(self.toc_url)
        # get content from main page TOC
        with urllib.request.urlopen(url) as response:
            output = response.read().decode()
            soup = BeautifulSoup(output, 'html.parser')
        content = soup.find_all('div', {"class": 'wy-menu wy-menu-vertical'})[0]
        toc = content.find('ul')
        lis = toc.find_all('li')
        for li in lis:
            a_tag = li.find_all('a')
            for i in a_tag:
                idxs, title = i.contents[0].split('. ')
                key_idx = (tuple(map(int, idxs.split('.'))))
                href = i.get('href')
                filename, old_id, new_id = parse_href(href)
                url = f"{DOCS_MAIN_PAGE}/{href}"

                self._update_ids(key_idx, url, old_id, new_id)

                self.toc[key_idx] = {
                    'title': title,
                    'filename': filename,
                    'old_id': old_id,
                    'new_id': new_id,
                    'url': url
                }
        _logger.info('toc from main page collected')
        _logger.info('collecting toc from other urls')
        # get additional content from all urls
        try:
            for chapter, urls in self.urls.items():
                _logger.info('chapter %s', chapter)
                for url in urls:
                    _logger.info('url: %s', url)
                    self.update_toc_dict(url)
        except TypeError:
            print(self.urls)
            raise

    def _get_section_indexes_from_toc(self, chapter: int) -> list:
        indexes = sorted(list(self.toc.keys()))
        if chapter:
            indexes = [idx for idx in indexes if idx[0] == chapter]
        else:
            indexes = [idx for idx in indexes if len(idx) < 3]
        return indexes

    def get_toc_html_from_dict(self, chapter: int) -> BeautifulSoup:
        indexes = self._get_section_indexes_from_toc(chapter)
        soup = BeautifulSoup()
        div = soup.new_tag("div")
        div.attrs['class'] = 'break-before'
        div.attrs['id'] = f'toc-{chapter}'
        div.attrs['class'] = 'toc'
        soup.append(div)

        prev_idx_len = 0
        ul_dict = dict()
        for idx in indexes:
            idx_len = len(idx)
            if idx_len > prev_idx_len:
                ul_dict[idx_len] = soup.new_tag('ul')
                if idx_len - 1 in ul_dict:
                    ul_dict[idx_len - 1].append(ul_dict[idx_len])
            li = soup.new_tag('li')
            ul_dict[idx_len].append(li)
            a = soup.new_tag('a', href='#' + self.toc[idx]['new_id'])
            a.string = f'{".".join(map(str, idx))} {self.toc[idx]["title"]}'
            li.append(a)
            prev_idx_len = idx_len
        div.append(ul_dict[min(ul_dict.keys())])

        return soup

    def get_chapter_dirs_and_id_replacement_pairs(self, chapter: int) -> dict:
        chapter_ids = sorted([k for k in self.toc.keys() if k[0] == chapter])
        chapter_dirs = dict()
        for idx in chapter_ids:
            chapter_filename = self.toc[idx]['filename']
            chapter_dir = f'{DOCS_MAIN_PAGE}/{chapter_filename}'
            if chapter_dir not in chapter_dirs:
                chapter_dirs[chapter_dir] = list()
            chapter_dirs[chapter_dir].append((self.toc[idx]['old_id'], self.toc[idx]['new_id']))

        return chapter_dirs

    @staticmethod
    def lower_headings(soup: BeautifulSoup) -> BeautifulSoup:
        for h_id in range(5, 0, -1):
            headings = soup.find_all(f'h{h_id}')
            for h in headings:
                h.name = f'h{h_id + 1}'
        return soup

    @staticmethod
    def replace_id(soup: BeautifulSoup, old_id: str, new_id: str) -> BeautifulSoup:
        # replace ids
        tag = soup.find(id=old_id)
        if tag:
            tag.attrs['id'] = new_id
        # replace hrefs
        tags = soup.find_all(href=f'#{old_id}')
        for tag in tags:
            tag.attrs['href'] = f'#{new_id}'
        return soup

    @staticmethod
    def clean_hrefs(soup: BeautifulSoup, url: str) -> BeautifulSoup:
        def href_with_id(t: BeautifulSoup) -> bool:
            return t.has_attr('href') and t.get('href').startswith('#id')

        def href_relative(t: BeautifulSoup) -> bool:
            return t.has_attr('href') and '.html' in t.get('href') and not t.get('href').startswith('http')

        def strip_href_from_folder_up(h: str) -> (str, int):
            f_up = 0
            while True:
                if h.startswith('../'):
                    h = h[3:]
                    f_up += 1
                else:
                    break
            return h, f_up

        # remove_redundant_hrefs
        tags = soup.find_all(href_with_id)
        for tag in tags:
            tag.unwrap()

        # change relative hrefs into absolute
        tags = soup.find_all(href_relative)
        base_path = url[len(DOCS_MAIN_PAGE) + 1:].split('/')
        for tag in tags:
            href = tag.get('href')
            href, folders_up = strip_href_from_folder_up(href)
            href = '/'.join(base_path[:-(folders_up + 1)]) + '/' + href
            filename, old_id, new_id = parse_href(href)
            tag.attrs['href'] = f'#{new_id}'

        return soup

    @staticmethod
    def replace_img_sources(soup: BeautifulSoup) -> BeautifulSoup:
        def href_for_image(t: BeautifulSoup) -> bool:
            return t.has_attr('href') and '_image' in t.get('href')

        def src_for_image(t: BeautifulSoup) -> bool:
            return t.has_attr('src') and '_image' in t.get('src')

        tags = soup.find_all(href_for_image)
        for tag in tags:
            th = tag["href"]
            tag['href'] = f'{DOCS_MAIN_PAGE}/{th[th.find("_image"):]}'
        tags = soup.find_all(src_for_image)
        for tag in tags:
            ts = tag["src"]
            tag['src'] = f'{DOCS_MAIN_PAGE}/{ts[ts.find("_image"):]}'

        return soup

    def get_chapter_html(self, chapter: int) -> BeautifulSoup:
        print(chapter)
        try:
            chapter_dirs_with_ids_dict = self.ids[chapter]
        except KeyError:
            print(self.ids.keys())
            raise
            # todo: keys are strings, should be integers
        chapter_soup = BeautifulSoup()
        if not chapter_dirs_with_ids_dict:
            return chapter_soup
        for url in chapter_dirs_with_ids_dict:
            print(url)
            with urllib.request.urlopen(url) as response:
                output = response.read().decode()
                soup = BeautifulSoup(output, 'html.parser')
                sections = soup.find_all('section')
                section = [s for s in sections if s.attrs.get('id')][0]
                section = self.lower_headings(section)
                for old_id, new_id in chapter_dirs_with_ids_dict[url].items():
                    section = self.replace_id(section, old_id, new_id)
                section = self.replace_img_sources(section)
                section = self.clean_hrefs(section, url)
            chapter_soup.append(section)
        # todo: clean (?)
        # todo: add links from sections to tocs
        # todo: clean tags like:
        #  <a class="reference internal" href="planning_course_information/index.html">
        #        6.1. Planning Course Information
        #  </a>
        return chapter_soup

    def get_full_html(self) -> None:
        soup = BeautifulSoup()
        html = soup.new_tag('html')
        soup.append(html)
        head = soup.new_tag('head')
        html.append(head)
        link = soup.new_tag('link')
        link['rel'] = 'stylesheet'
        link['href'] = 'style.css'
        head.append(link)
        # < link rel = "stylesheet" href = "mystyle.css" >
        body = soup.new_tag('body')
        html.append(body)
        h1 = soup.new_tag('h1')
        body.append(h1)
        h1.string = 'Building and Running an Open edX Course: Nutmeg Release'
        chapters_number = max(self.toc.keys(), key=lambda x: x[0])[0]
        # for chapter in range(chapters_number + 1):
        for chapter in [6]:
            print(chapter)
            chapter_toc = self.get_toc_html_from_dict(chapter)
            body.append(chapter_toc)
            chapter_content = self.get_chapter_html(chapter)
            body.append(chapter_content)

        self.html = soup.prettify()


# def get_urls_from_main_page() -> dict:
#     url = _iri_to_uri(DOCS_TOC_PAGE)
#     # get urls from main page TOC
#     with urllib.request.urlopen(url) as response:
#         output = response.read().decode()
#         soup = BeautifulSoup(output, 'html.parser')
#     content = soup.find_all('div', {"class": 'wy-menu wy-menu-vertical'})[0]
#     toc = content.find('ul')
#     lis = toc.find_all('li')
#     urls_dict = dict()
#     for li in lis:
#         a_tag = li.find_all('a')
#         for i in a_tag:
#             contents = [x for x in i.contents if not x.name][0]
#             idxs, title = contents.split('. ')
#             key_idx = (tuple(map(int, idxs.split('.'))))
#             chapter = key_idx[0]
#             href = i.get('href').split('#')[0]
#             href = f"{DOCS_MAIN_PAGE}/{href}"
#             urls_dict[chapter] = urls_dict.get(chapter) or set()
#             urls_dict[chapter].add(href)
#     return urls_dict


# def get_ids(urls_dict: dict) -> dict:
#     # {chapter_number: {url: {old_id: new_id}}}
#     ids_dict = dict()
#     for chapter, urls in urls_dict.items():
#         ids_dict[chapter] = dict()
#         for url in urls:
#             filename = url[len(DOCS_MAIN_PAGE) + 1:].split(".")[0].replace("/", "-")
#             ids_dict[chapter][url] = dict()
#             ids_dict[chapter][url][''] = filename
#             with urllib.request.urlopen(url) as response:
#                 output = response.read().decode()
#                 soup = BeautifulSoup(output, 'html.parser')
#                 tags_with_id = soup.find_all(lambda t: t.has_attr('id'))
#                 for tag in tags_with_id:
#                     old_id = tag.attrs.get('id')
#                     new_id = f'{filename}{f"-{old_id}" if old_id else ""}'
#                     ids_dict[chapter][url][old_id] = new_id
#     return ids_dict


# def get_toc_dict_from_page(url=DOCS_TOC_PAGE) -> dict:
#     url = _iri_to_uri(url)
#     # get content from main page TOC
#     with urllib.request.urlopen(url) as response:
#         output = response.read().decode()
#         soup = BeautifulSoup(output, 'html.parser')
#     content = soup.find_all('div', {"class": 'wy-menu wy-menu-vertical'})[0]
#     toc = content.find('ul')
#     lis = toc.find_all('li')
#     toc_dict = dict()
#     for li in lis:
#         a_tag = li.find_all('a')
#         for i in a_tag:
#             idxs, title = i.contents[0].split('. ')
#             key_idx = (tuple(map(int, idxs.split('.'))))
#             href = i.get('href')
#             filename, old_id, new_id = parse_href(href)
#             toc_dict[key_idx] = {
#                 'title': title,
#                 'filename': filename,
#                 'old_id': old_id,
#                 'new_id': new_id,
#                 'href': href
#             }
#     toc_dict = make_hrefs_absolute(toc_dict)
#     return toc_dict


# def get_urls_list_from_toc_dict(toc_dict: dict) -> list:
#     urls = list()
#     ch_urls = list()
#     keys = sorted(toc_dict.keys())
#     for k in keys:
#         url = toc_dict[k]['href']
#         if url not in urls:
#             urls.append(url)
#             ch_urls.append((k[0], url))
#     return ch_urls


# def update_toc_dict(toc_dict: dict, url: str) -> dict:
#     def get_id_and_title_from_ascendant_section(t: BeautifulSoup) -> (int or None, str):
#         p = t.parent
#         while True:
#             if p.name == 'section' and p.attrs.get('id'):
#                 tid = p.attrs.get('id')
#                 break
#             p = p.parent
#         p = t.parent
#         title_l = [x.strip(' \n') for x in p.contents if not x.name]
#         title_l = [x for x in title_l if x]
#         if title_l:
#             ttl = title_l[0]
#         else:
#             try:
#                 ttl = p.find('code').find('span').string
#             except Exception as exc:
#                 print('key_idx: ', key_idx)
#                 print('tag: ', t)
#                 print('parent: ', p.name)
#                 print('filename: ', filename)
#                 print('old_id: ', old_id)
#                 print('new_id: ', new_id)
#                 print('title: ', title)
#                 print('.' * 30)
#                 print(p.parent)
#                 raise exc
#         return tid, ttl
#
#     with urllib.request.urlopen(url) as response:
#         output = response.read().decode()
#         soup = BeautifulSoup(output, 'html.parser')
#         sections = soup.find_all('section')
#         section = [s for s in sections if s.attrs.get('id')][0]
#         # get ids from class='session-number'
#         section_numbers_tags = section.find_all(class_='section-number')
#         filename = url[len(DOCS_MAIN_PAGE) + 1:]
#         for tag in section_numbers_tags:
#             key_idx = tuple(map(int, tag.string.strip('. ').split('.')))
#             if key_idx in toc_dict:
#                 continue
#
#             old_id, title = get_id_and_title_from_ascendant_section(tag)
#             new_id = f'{filename.split(".")[0].replace("/", "-")}{"-" + old_id if old_id else ""}'
#
#             toc_dict[key_idx] = {
#                 'title': title,
#                 'filename': filename,
#                 'old_id': old_id,
#                 'new_id': new_id,
#                 'href': f"{url}#{old_id}"
#             }
#     return toc_dict
#
#
# def get_toc_dict() -> dict:
#     toc_dict = get_toc_dict_from_page()
#     # c = 0
#     # for k, v in toc_dict.items():
#     #     print(k)
#     #     print(v)
#     #     c += 1
#     #     if c == 10:
#     #         quit()
#     urls = get_urls_list_from_toc_dict(toc_dict)
#     old_chapter = 0
#     for chapter, url in urls:
#         if chapter > old_chapter:
#             print(f'chapter {chapter}')
#             old_chapter = chapter
#         toc_dict = update_toc_dict(toc_dict, url)
#
#     return toc_dict


# def get_section_indexes_from_toc(toc_dict: dict, chapter: int) -> list:
#     indexes = sorted(list(toc_dict.keys()))
#     if chapter:
#         indexes = [idx for idx in indexes if idx[0] == chapter]
#     else:
#         indexes = [idx for idx in indexes if len(idx) < 3]
#     return indexes
#
#
# def get_toc_html_from_dict(toc_dict: dict, chapter: int) -> BeautifulSoup:
#     indexes = get_section_indexes_from_toc(toc_dict, chapter)
#     soup = BeautifulSoup()
#     div = soup.new_tag("div")
#     div.attrs['class'] = 'break-before'
#     div.attrs['id'] = f'toc-{chapter}'
#     div.attrs['class'] = 'toc'
#     soup.append(div)
#
#     prev_idx_len = 0
#     ul_dict = dict()
#     for idx in indexes:
#         idx_len = len(idx)
#         if idx_len > prev_idx_len:
#             ul_dict[idx_len] = soup.new_tag('ul')
#             if idx_len - 1 in ul_dict:
#                 ul_dict[idx_len - 1].append(ul_dict[idx_len])
#         li = soup.new_tag('li')
#         ul_dict[idx_len].append(li)
#         a = soup.new_tag('a', href='#' + toc_dict[idx]['new_id'])
#         a.string = f'{".".join(map(str, idx))} {toc_dict[idx]["title"]}'
#         li.append(a)
#         prev_idx_len = idx_len
#     div.append(ul_dict[min(ul_dict.keys())])
#
#     return soup
#
#
# def lower_headings(soup: BeautifulSoup) -> BeautifulSoup:
#     for h_id in range(5, 0, -1):
#         headings = soup.find_all(f'h{h_id}')
#         for h in headings:
#             h.name = f'h{h_id + 1}'
#     return soup


# def get_chapter_dirs_and_id_replacement_pairs(toc_dict: dict, chapter: int) -> dict:
#     chapter_ids = sorted([k for k in toc_dict.keys() if k[0] == chapter])
#     chapter_dirs = dict()
#     for idx in chapter_ids:
#         chapter_filename = toc_dict[idx]['filename']
#         chapter_dir = f'{DOCS_MAIN_PAGE}/{chapter_filename}'
#         if chapter_dir not in chapter_dirs:
#             chapter_dirs[chapter_dir] = list()
#         chapter_dirs[chapter_dir].append((toc_dict[idx]['old_id'], toc_dict[idx]['new_id']))
#
#     return chapter_dirs
#
#
# def replace_id(soup: BeautifulSoup, old_id: str, new_id: str) -> BeautifulSoup:
#     # replace ids
#     tag = soup.find(id=old_id)
#     if tag:
#         tag.attrs['id'] = new_id
#     # replace hrefs
#     tags = soup.find_all(href=f'#{old_id}')
#     for tag in tags:
#         tag.attrs['href'] = f'#{new_id}'
#     return soup


# def strip_href_from_folder_up(href: str) -> (str, int):
#     folders_up = 0
#     while True:
#         if href.startswith('../'):
#             href = href[3:]
#             folders_up += 1
#         else:
#             break
#     return href, folders_up
#

# def clean_hrefs(soup: BeautifulSoup, url: str) -> BeautifulSoup:
#     def href_with_id(t: BeautifulSoup) -> bool:
#         return t.has_attr('href') and t.get('href').startswith('#id')
#
#     def href_relative(t: BeautifulSoup) -> bool:
#         return t.has_attr('href') and '.html' in t.get('href') and not t.get('href').startswith('http')
#
#     # remove_redundant_hrefs
#     tags = soup.find_all(href_with_id)
#     for tag in tags:
#         tag.unwrap()
#
#     # change relative hrefs into absolute
#     tags = soup.find_all(href_relative)
#     base_path = url[len(DOCS_MAIN_PAGE) + 1:].split('/')
#     for tag in tags:
#         href = tag.get('href')
#         href, folders_up = strip_href_from_folder_up(href)
#         href = '/'.join(base_path[:-(folders_up + 1)]) + '/' + href
#         filename, old_id, new_id = parse_href(href)
#         tag.attrs['href'] = f'#{new_id}'
#
#     return soup
#

# def replace_img_sources(soup: BeautifulSoup) -> BeautifulSoup:
#     def href_for_image(t: BeautifulSoup) -> bool:
#         return t.has_attr('href') and '_image' in t.get('href')
#
#     def src_for_image(t: BeautifulSoup) -> bool:
#         return t.has_attr('src') and '_image' in t.get('src')
#
#     tags = soup.find_all(href_for_image)
#     for tag in tags:
#         th = tag["href"]
#         tag['href'] = f'{DOCS_MAIN_PAGE}/{th[th.find("_image"):]}'
#     tags = soup.find_all(src_for_image)
#     for tag in tags:
#         ts = tag["src"]
#         tag['src'] = f'{DOCS_MAIN_PAGE}/{ts[ts.find("_image"):]}'
#
#     return soup
#

# def get_chapter_html(toc_dict: dict, chapter: int) -> BeautifulSoup:
#     print(chapter)
#     chapter_dirs_with_ids_dict = get_chapter_dirs_and_id_replacement_pairs(toc_dict, chapter)
#     chapter_soup = BeautifulSoup()
#     if not chapter_dirs_with_ids_dict:
#         return chapter_soup
#     for url in chapter_dirs_with_ids_dict:
#         print(url)
#         with urllib.request.urlopen(url) as response:
#             output = response.read().decode()
#             soup = BeautifulSoup(output, 'html.parser')
#             sections = soup.find_all('section')
#             section = [s for s in sections if s.attrs.get('id')][0]
#             section = lower_headings(section)
#             for old_id, new_id in chapter_dirs_with_ids_dict[url]:
#                 section = replace_id(section, old_id, new_id)
#                 if old_id == 'what-you-will-learn-guidelines':
#                     print('*' * 30)
#                     print(new_id)
#                     print(section)
#                     print('*' * 30)
#             section = replace_img_sources(section)
#             section = clean_hrefs(section, url)
#         chapter_soup.append(section)
#     # todo: clean (?)
#     # todo: add links from sections to tocs
#     # todo: clean tags like:
#     #  <a class="reference internal" href="planning_course_information/index.html">
#     #        6.1. Planning Course Information
#     #  </a>
#     return chapter_soup


# def get_full_html(toc_dict: dict) -> str:
#     soup = BeautifulSoup()
#     html = soup.new_tag('html')
#     soup.append(html)
#     head = soup.new_tag('head')
#     html.append(head)
#     link = soup.new_tag('link')
#     link['rel'] = 'stylesheet'
#     link['href'] = 'style.css'
#     head.append(link)
#     # < link rel = "stylesheet" href = "mystyle.css" >
#     body = soup.new_tag('body')
#     html.append(body)
#     h1 = soup.new_tag('h1')
#     body.append(h1)
#     h1.string = 'Building and Running an Open edX Course: Nutmeg Release'
#     chapters_number = max(toc_dict.keys(), key=lambda x: x[0])[0]
#     # for chapter in range(chapters_number + 1):
#     for chapter in [6]:
#         print(chapter)
#         chapter_toc = get_toc_html_from_dict(toc_dict, chapter)
#         body.append(chapter_toc)
#         chapter_content = get_chapter_html(toc_dict, chapter)
#         body.append(chapter_content)
#
#     return soup.prettify()
#
#
def save_html(html: str, filename='content.html') -> None:
    dir_path = Path(__file__).parent
    html_filepath = dir_path / filename
    with open(html_filepath, 'w', encoding="utf-8") as f:
        f.write(html)


# def save_toc_dict_as_json():
#     toc_dict = get_toc_dict()
#     with open("toc_data.json", "w") as outfile:
#         json.dump(_json_dumps_tuple_keys(toc_dict), outfile)
#
#
# def get_toc_dict_from_json():
#     with open("toc_data.json") as infile:
#         string = json.load(infile)
#         toc_dict = _json_loads_tuple_keys(string)
#     return toc_dict


def main():
    p = Parser(from_json=True)
    p.get_full_html()

    # save_toc_dict_as_json()
    # toc_dict = get_toc_dict_from_json()
    # html = get_full_html(toc_dict)
    # save_html(html)


if __name__ == '__main__':
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')
    try:
        main()
    except TimeoutError as e:
        _logger.error(e)
