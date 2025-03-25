from typing import List, AsyncIterable
from urllib.parse import urlparse, urljoin, quote, quote_plus

from bs4 import BeautifulSoup

from plugins.client import MangaClient, MangaCard, MangaChapter, LastChapter


class WuxiaWorldClient(MangaClient):
    name = "Novel-WuxiaWorld"
    
    base_url = urlparse("https://wuxiaworld.site")
    updates_url = urljoin(base_url.geturl(), "/latest")

    pre_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
    }
    
    headers = pre_headers

    def mangas_from_page(self, page: bytes):
      bs = BeautifulSoup(page, "html.parser")
      
      con = bs.find(class_="tab-content-wrap")
      cards = con.find_all(class_="post-title")
      
      names = [card.findNext('a').string.strip() for card in cards]
      urls = [card.findNext('a')['href'] for card in cards]
      images = ["https://graph.org/file/aa477c9c5ba182829628b.jpg" for card in cards]
      
      mangas = [MangaCard(self, *tup) for tup in zip(names, urls, images)]
      
      return mangas

    def chapters_from_page(self, page: bytes, manga: MangaCard = None):
      bs = BeautifulSoup(page, "html.parser")
      cards = bs.findAll("li")
      
      texts = [card.findNext("a").string.strip() for card in cards]
      links = [card.findNext("a")['href'] for card in cards]
      
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
      """ This Function Return Text List """
      bs = BeautifulSoup(content, "html.parser")
      
      con = bs.find(class_="text-left")
      
      cards = con.findAll("p")
      
      texts = [card.text for card in cards]
      
      return texts

    async def search(self, query: str = "", page: int = 1) -> List[MangaCard]:
        query = quote_plus(query)

        request_url = f"https://wuxiaworld.site/?s={query}&post_type=wp-manga"
        
        content = await self.get_url(request_url)

        return self.mangas_from_page(content)

    async def get_chapters(self, manga_card: MangaCard, page: int = 1) -> List[MangaChapter]:
      request_url = f'{manga_card.url}'
      
      slugs = request_url.split("/")[4]
      
      url = f"https://wuxiaworld.site/novel/{slugs}/ajax/chapters/"
      
      content = await self.get_url(url, method='post')
      
      return self.chapters_from_page(content, manga_card)[(page - 1) * 20:page * 20]

    async def iter_chapters(self, manga_url: str, manga_name) -> AsyncIterable[MangaChapter]:
      manga_card = MangaCard(self, manga_name, manga_url, '')
      
      request_url = f'{manga_card.url}'
      
      slugs = request_url.split("/")[4]
      
      url = f"https://wuxiaworld.site/novel/{slugs}/ajax/chapters/"
      
      content = await self.get_url(url, method='post')
      
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
