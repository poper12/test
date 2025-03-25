from typing import List, AsyncIterable
from urllib.parse import urlparse, urljoin, quote, quote_plus

from bs4 import BeautifulSoup

from plugins.client import MangaClient, MangaCard, MangaChapter, LastChapter
import re

class NovelBuddyClient(MangaClient):
    name = "NovelBuddy"
    
    base_url = urlparse("https://novelbuddy.com/")
    novel_link = urljoin(base_url.geturl(), "novel")
    updates_url = urljoin(base_url.geturl(), "latest")
    novel = "https://novelbuddy.com/novel"

    pre_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
    }
    
    headers = pre_headers

    def mangas_from_page(self, page: bytes):
        bs = BeautifulSoup(page, "html.parser")
        
        cards = bs.find_all("div", {"class": "novel__item"})
        
        mangas = [card.a for card in cards if card.a is not None]
        names = [manga.get("title").strip() for manga in mangas]
        urls = [self.novel + manga.get('href').strip() for manga in mangas]
        images = [urljoin("https:", manga.findNext("img").get("src")) for manga in mangas]

        mangas = [MangaCard(self, *tup) for tup in zip(names, urls, images)]

        return mangas

    def chapters_from_page(self, page: bytes, manga: MangaCard = None, slugs: str = None):
        bs = BeautifulSoup(page, "html.parser")
        
        di = bs.find("div", {"id": "chapter-list-inner"})
        li = di.find_all("li")
        ul = [l.findNext("a") for l in li]
        
        links = [urljoin(self.novel_link, u["href"]) for u in ul if slugs in u["href"]]
        
        names = [u["title"] for u in ul if slugs in u["href"]]
        pattern = r'(\d+\.\d+|\d+)(.*)'
        texts = [
            f"{match[0]} {match[1].strip()}"  # Format as "number text" if match is found
            if (match := re.search(pattern, text))  # If a match is found
            else text  # Otherwise, keep the original text
            for text in names
        ]

        return list(map(lambda x: MangaChapter(self, x[0], x[1], manga, [], "True"), zip(texts, links)))


    async def updates_from_page(self, content):
        bs = BeautifulSoup(content, "html.parser")

        manga_items = bs.find_all("div", {"class": "bs"})

        urls = dict()

        for manga_item in manga_items:
            manga_url = manga_item.findNext("a").get("href")
            
            if manga_url in urls:
                continue
            
            data = await self.get_url(manga_url)
            bs = BeautifulSoup(data, "html.parser")
            cards = bs.find("div", {"class": "eplister"})
            for card in cards: chapter_url = card.find("li").findNext("a").get("href")
            
            urls[manga_url] = chapter_url

        return urls

    async def pictures_from_chapters(self, content: bytes, response=None):
        bs = BeautifulSoup(content, "html.parser")
        
        content = bs.find(class_="content-inner")
        
        d = bs.findAll(["p", "em"])
        
        texts = [i.text for i in d]
        
        return texts

    async def search(self, query: str = "", page: int = 1) -> List[MangaCard]:
        query = quote_plus(query)

        request_url = f"https://novelbuddy.com/api/manga/search?q={query}&sort=views&status=all"
        
        content = await self.get_url(request_url)

        return self.mangas_from_page(content)

    async def get_chapters(self, manga_card: MangaCard, page: int = 1) -> List[MangaChapter]:

        request_url = f'{manga_card.url}'
        
        slugs = request_url.split("/")[4]
        
        content = await self.get_url(request_url)

        return self.chapters_from_page(content, manga_card, slugs)[(page - 1) * 20:page * 20]

    async def iter_chapters(self, manga_url: str, manga_name) -> AsyncIterable[MangaChapter]:
        manga_card = MangaCard(self, manga_name, manga_url, '')

        request_url = f'{manga_card.url}'
        
        slugs = request_url.split("/")[4]
        
        content = await self.get_url(request_url)

        for chapter in self.chapters_from_page(content, manga_card, slugs):
            yield chapter

    async def contains_url(self, url: str):
        return url.startswith(self.base_url.geturl())

    async def check_updated_urls(self, last_chapters: List[LastChapter]):
        content = await self.get_url(self.updates_url)

        updates = await self.updates_from_page(content)

        updated = []
        not_updated = []
        for lc in last_chapters:
            if lc.url in updates.keys():
                if updates.get(lc.url) != lc.chapter_url:
                    updated.append(lc.url)
            elif updates.get(lc.url) == lc.chapter_url:
                not_updated.append(lc.url)
                
        return updated, not_updated
