from typing import List, AsyncIterable
from urllib.parse import urlparse, urljoin, quote, quote_plus

from bs4 import BeautifulSoup

from plugins.client import MangaClient, MangaCard, MangaChapter, LastChapter
import json

class ReadNovelClient(MangaClient):
    name = "NovelRead"
    
    base_url = urlparse("https://readnovel.eu/")
    updates_url = base_url.geturl()

    pre_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
    }
    
    headers = pre_headers

    def mangas_from_page(self, page: bytes):
        try:
            datas = json.loads(page)
            
            mangas = []
            for data in datas["results"]:
                url = f"https://readnovel.eu/novel/{data['slug']}"
                mangas.append(MangaCard(self, data["name"], url, data['image']))
        except:
            mangas = []
        
        return mangas

    def chapters_from_page(self, page: bytes, manga: MangaCard = None):
      datas = json.loads(page)
      
      chapters = []
      for data in datas:
        url = f"https://readnovel.eu/chapter/{data['novSlugChapSlug']}"
        
        chapters.append(MangaChapter(self, data['title'], url, manga, [], "True"))
      
      return chapters

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
      """ This Function Return Text List """
      bs = BeautifulSoup(content, "html.parser")
      
      con = bs.find_all(class_="mantine-Text-root mantine-1ekvxsp")
      
      texts = [i.text for i in con]
      
      return texts

    async def search(self, query: str = "", page: int = 1) -> List[MangaCard]:
        url = f"https://wuxiaworld.eu/api/search/?search={quote_plus(query)}&offset=0&limit=12&order="
        
        content = await self.get_url(url)
        
        if not content: return MangaCard(self, [], [], [])
        
        return self.mangas_from_page(content)

    async def get_chapters(self, manga_card: MangaCard, page: int = 1) -> List[MangaChapter]:
      request_url = f'{manga_card.url}'
      
      slugs = request_url.split("/")[4]
      
      url = f"https://wuxiaworld.eu/api/chapters/{slugs}/"
      
      content = await self.get_url(url)
      
      return self.chapters_from_page(content, manga_card)[(page - 1) * 20:page * 20]

    async def iter_chapters(self, manga_url: str, manga_name) -> AsyncIterable[MangaChapter]:
      manga_card = MangaCard(self, manga_name, manga_url, '')
      
      request_url = f'{manga_card.url}'
      
      slugs = request_url.split("/")[4]
      
      url = f"https://wuxiaworld.eu/api/chapters/{slugs}/"
      
      content = await self.get_url(url)
      
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
