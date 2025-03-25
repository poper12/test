from typing import List, AsyncIterable
from urllib.parse import urlparse, urljoin, quote, quote_plus

from bs4 import BeautifulSoup

from plugins.client import MangaClient, MangaCard, MangaChapter, LastChapter


class NovelHallClient(MangaClient):
    name = "NovelHall"
    
    base_url = urlparse("https://www.novelhall.com")
    updates_url = urljoin(base_url.geturl(), "/latest")

    pre_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
    }
    
    headers = pre_headers

    def mangas_from_page(self, page: bytes):
        try:
            bs = BeautifulSoup(page, "html.parser")
            
            con = bs.find(class_="section3 inner mt30")
            cards = con.find_all("td")
            
            mangas = []
            for card in cards:
                ex_url = card.find_next("a")["href"]
                ex_name = card.find_all(string=True)
                if not ex_url.startswith("/search"):
                    if not ex_url.endswith(".html"):
                        if not ex_url.startswith("javascript"):
                            if not ex_url.endswith(".xml"):
                                url = self.base_url.geturl() + ex_url
                                name = " ".join(part.strip() for part in ex_name if part.strip())
                                image = "https://graph.org/file/aa477c9c5ba182829628b.jpg"
                                mangas.append(MangaCard(self, name, url, image))
            
            return mangas
        except:
            return []

    def chapters_from_page(self, page: bytes, manga: MangaCard = None):
        bs = BeautifulSoup(page, "html.parser")
        
        con = bs.find('div', id='morelist')
        cards = con.find_all("li")
        
        links = [
            self.base_url.geturl() + card.find_next("a")["href"]
            for card in cards
            if not "：" in card.find_next("a")["href"]
        ]
        
        texts = [
            card.find_next("a").string.strip()
            for card in cards
            if not "：" in card.find_next("a")["href"]
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
        """
        This Function Return Text List
        """
        bs = BeautifulSoup(content, "html.parser")
        
        con = bs.find('div', id='htmlContent')
        
        cards = con.find_all(string=True, recursive=True)
        
        texts = [card.strip() for card in cards]
        
        return texts

    async def search(self, query: str = "", page: int = 1) -> List[MangaCard]:
        query = quote_plus(query)

        request_url = f"https://www.novelhall.com/index.php?s=so&module=book&keyword={query}"
        
        content = await self.get_url(request_url)
        
        if not content: return MangaCard(self, [], [], [])

        return self.mangas_from_page(content)

    async def get_chapters(self, manga_card: MangaCard, page: int = 1) -> List[MangaChapter]:

        request_url = f'{manga_card.url}'

        content = await self.get_url(request_url)

        return self.chapters_from_page(content, manga_card)[(page - 1) * 20:page * 20]

    async def iter_chapters(self, manga_url: str, manga_name) -> AsyncIterable[MangaChapter]:
        manga_card = MangaCard(self, manga_name, manga_url, '')

        request_url = f'{manga_card.url}'

        content = await self.get_url(request_url)

        for chapter in self.chapters_from_page(content, manga_card):
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
