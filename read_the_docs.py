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


def iri_to_uri(iri):
    return safe_url_string(iri, encoding="UTF-8")


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
    new_id = f'{filename.split(".")[0].replace("/", "-")}{"-" + old_id if old_id else ""}'
    return filename, old_id, new_id


def get_toc_dict(url=DOCS_TOC_PAGE) -> dict:
    url = iri_to_uri(url)
    with urllib.request.urlopen(url) as response:
        output = response.read().decode()
        soup = BeautifulSoup(output, 'html.parser')
    content = soup.find_all('div', {"class": 'wy-menu wy-menu-vertical'})[0]
    toc = content.find('ul')
    lis = toc.find_all('li')
    toc_dict = dict()
    for li in lis:
        a_tag = li.find_all('a')
        for i in a_tag:
            idxs, title = i.contents[0].split('. ')
            key_idx = (tuple(map(int, idxs.split('.'))))
            href = i.get('href')
            filename, old_id, new_id = parse_href(href)
            toc_dict[key_idx] = {
                'title': title,
                'filename': filename,
                'old_id': old_id,
                'new_id': new_id,
                'href': href
            }

            if len(key_idx) == 1:
                with urllib.request.urlopen(f'{DOCS_MAIN_PAGE}/{href}') as r:
                    page_output = r.read().decode()
                    page_soup = BeautifulSoup(page_output, 'html.parser')


    #todo levels 4+ missing!
    return toc_dict


def get_section_indexes_from_toc(toc_dict: dict, chapter: int) -> list:
    indexes = sorted(list(toc_dict.keys()))
    if chapter:
        indexes = [idx for idx in indexes if idx[0] == chapter]
    else:
        indexes = [idx for idx in indexes if len(idx) < 3]
    return indexes


def get_toc_html_from_dict(toc_dict: dict, chapter: int) -> BeautifulSoup:
    indexes = get_section_indexes_from_toc(toc_dict, chapter)
    soup = BeautifulSoup()
    div = soup.new_tag("div")
    div.attrs['class'] = 'break-before'
    div.attrs['id'] = f'toc-{chapter}'
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
        a = soup.new_tag('a', href='#' + toc_dict[idx]['new_id'])
        a.string = f'{".".join(map(str, idx))} {toc_dict[idx]["title"]}'
        li.append(a)
        prev_idx_len = idx_len
    div.append(ul_dict[min(ul_dict.keys())])

    return soup


def lower_headings(soup: BeautifulSoup) -> BeautifulSoup:
    for h_id in range(5, 0, -1):
        headings = soup.find_all(f'h{h_id}')
        for h in headings:
            h.name = f'h{h_id + 1}'
    return soup


def get_chapter_dirs_and_id_replacement_pairs(toc_dict: dict, chapter: int) -> dict:
    chapter_ids = sorted([k for k in toc_dict.keys() if k[0] == chapter])
    chapter_dirs = dict()
    for idx in chapter_ids:
        chapter_filename = toc_dict[idx]['filename']
        chapter_dir = f'{DOCS_MAIN_PAGE}/{chapter_filename}'
        if chapter_dir not in chapter_dirs:
            chapter_dirs[chapter_dir] = list()
        chapter_dirs[chapter_dir].append((toc_dict[idx]['old_id'], toc_dict[idx]['new_id']))

    return chapter_dirs


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


def replace_img_sources(soup: BeautifulSoup) -> BeautifulSoup:
    def href_for_image(t: BeautifulSoup):
        return t.has_attr('href') and '_image' in t.get('href')

    def src_for_image(t: BeautifulSoup):
        return t.has_attr('src') and '_image' in t.get('src')

    tags = soup.find_all(href_for_image)
    for tag in tags:
        th = tag["href"]
        tag['href'] = f'{DOCS_MAIN_PAGE}/{th[th.find("_image"):]}'
    tags = soup.find_all(src_for_image)
    for tag in tags:
        ts = tag["src"]
        print(".", ts)
        tag['src'] = f'{DOCS_MAIN_PAGE}/{ts[ts.find("_image"):]}'
        print(">", tag['src'])

    return soup


def get_chapter_html(toc_dict: dict, chapter: int) -> BeautifulSoup:
    print(chapter)
    chapter_dirs_with_ids_dict = get_chapter_dirs_and_id_replacement_pairs(toc_dict, chapter)
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
            section = lower_headings(section)
            for old_id, new_id in chapter_dirs_with_ids_dict[url]:
                section = replace_id(section, old_id, new_id)
            section = replace_img_sources(section)
        chapter_soup.append(section)
    # todo: clean (?)
    #  id="id4", href="#id4" <- add filename
    # todo: add links from sections to tocs
    return chapter_soup


def get_full_html() -> str:
    soup = BeautifulSoup()
    toc_dict = get_toc_dict()
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
    chapters_number = max(toc_dict.keys(), key=lambda x: x[0])[0]
    for chapter in range(chapters_number + 1):
    # for chapter in [6]:
        chapter_toc = get_toc_html_from_dict(toc_dict, chapter)
        body.append(chapter_toc)
        chapter_content = get_chapter_html(toc_dict, chapter)
        body.append(chapter_content)

    return soup.prettify()


def save_html(html: str, filename='content.html') -> None:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    html_filepath = os.path.join(dir_path, filename)
    with open(html_filepath, 'w', encoding="utf-8") as f:
        f.write(html)


def temp(toc_dict: dict):
    # toc_dict = {k: v for k, v in toc_dict.items() if len(k) == 1 and k[0] == chapter}
    chapter_dict = toc_dict[(6,1,1)]
    with urllib.request.urlopen(f'{DOCS_MAIN_PAGE}/{chapter_dict["href"]}') as r:
        page_output = r.read().decode()
        soup = BeautifulSoup(page_output, 'html.parser')
        sections = soup.find_all('section')
        section = [s for s in sections if s.get('id')][0]
        tags = section.find_all(lambda t: t.has_attr('href'))
        print('HREFS:')
        for tag in tags:
            print(f"   {tag.name}, {tag['href']}")
        tags = section.find_all(lambda t: t.has_attr('id'))
        print()
        print('IDS:')
        for tag in tags:
            print(f"   {tag.name}, {tag['id']}")


def main():
    toc_dict = get_toc_dict()
    # for k, v in toc_dict.items():
    #     if len(k) == 1:
    #         print(k, v)
    temp(toc_dict)

    # print(get_toc_html_from_dict(toc_dict, 3))
    # print("chapters' dirs'")
    # for ch in range(22):
    #     a = get_chapter_dirs(toc_dict, ch)
    #     print(ch, a)

    # html = get_full_html()
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
