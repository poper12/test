from typing import List, AsyncIterable 

from urllib.parse import urlparse, urljoin, quote, quote_plus, urlencode
from bs4 import BeautifulSoup 

from plugins.client import MangaClient, MangaCard, MangaChapter, LastChapter

import cloudscraper
import asyncio 

class WeebCentralClient(MangaClient):
    name="WeebCentral"
    
    base_url = urlparse("https://weebcentral.com/")
    search_url = base_url.geturl()
    updates_url = "https://weebcentral.com/hot-updates"

    pre_headers = {
      "Accept": "*/*",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      #Content-Length: 9
      "Content-Type": "application/x-www-form-urlencoded",
      "Host": "weebcentral.com",
      "HX-Request": "true",
      "Origin": "https://weebcentral.com",
      "Referer": "https://weebcentral.com/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    }

    async def cpost(self, url, params):
      scraper = cloudscraper.create_scraper()
      
      page = await asyncio.to_thread(scraper.post, url, params, headers=self.pre_headers)
      
      if page.status_code == 200:
        return page.text
      else:
        return None
    
    async def cget(self, url):
        scraper = cloudscraper.create_scraper()
        
        page = await asyncio.to_thread(scraper.get, url, headers=self.pre_headers)
        
        if page.status_code == 200:
            return page.text
        else:
            return None
    
    def mangas_from_page(self, page: bytes):
      bs = BeautifulSoup(page, "html.parser")
      
      con = bs.find_all("a")
      
      url = [c['href'] for c in con]
      images = [c.findNext("img")['src']for c in con]
      names = [
        c.findNext("div").findNext("div").string.strip()
        for c in con
      ]
      
      mangas = [MangaCard(self, *tup) for tup in zip(names, url, images)]
      
      return mangas

    def chapters_from_page(self, page: bytes, manga: MangaCard = None):
        params = {
            'is_prev': 'False',
            'current_page': '1',  # Ensure this is correctly named
            'reading_style': 'long_strip'
        }
        
        bs = BeautifulSoup(page, "html.parser")
        
        rdata = bs.find_all("a", class_="hover:bg-base-300 flex-1 flex items-center p-2")
        
        chapters_name = [i.findNext("span", class_="").text for i in rdata]
        chapters_link = [f"{i['href']}/images?{urlencode(params)}" for i in rdata]
        
        return list(map(lambda x: MangaChapter(self, x[0], x[1], manga, [], "None"), zip(chapters_name, chapters_link)))


    async def updates_from_page(self, page):
        bs = BeautifulSoup(page, "html.parser")
        
        urls = dict()
        for i in bs.find_all("abbr"):
            chapters_url = i.findNext("a")['href']
            
            manga_url = i.findNext("a").findNext("a")['href']
            
            urls[manga_url] = chapters_url
        
        return urls

    async def pictures_from_chapters(self, data: bytes, response=None):
        bs = BeautifulSoup(data, 'html.parser')
        
        images_url = [i['src'] for i in bs.find_all("img")]
        
        return images_url
        

    async def search(self, query: str = "", page: int = 1) -> List[MangaCard]:
        request_url = "https://weebcentral.com/search/simple?location=main"
        
        self.pre_headers['Content-Length'] = str(len(query))
        self.pre_headers["HX-Current-URL"] = "https://weebcentral.com/"
        self.pre_headers["HX-Target"] = "quick-search-result"
        self.pre_headers["HX-Trigger"] = "quick-search-input"
        self.pre_headers["HX-Trigger-Name"] = "text"
        
        params = {"text": query}
        content = await self.cpost(request_url, params)
        
        del self.pre_headers['Content-Length']
        del self.pre_headers["HX-Target"]
        del self.pre_headers["HX-Trigger"]
        del self.pre_headers["HX-Trigger-Name"]
        
        if not content:
            return [MangaCard(self, *tup) for tup in zip([], [], [])]
        
        return self.mangas_from_page(content)

    async def get_chapters(self, manga_card: MangaCard, page: int = 1) -> List[MangaChapter]:
        request_url = f'{manga_card.url}'
        
        link = request_url.split("/")
        new_link = "/".join(link[:-1]) + "/full-chapter-list"
        self.pre_headers['hx-current-url'] = request_url
        self.pre_headers['hx-target'] = "chapter-list"
        self.pre_headers['referer'] = request_url
        
        content = await self.cget(new_link)
        
        del self.pre_headers['hx-current-url']
        del self.pre_headers['hx-target']
        del self.pre_headers['referer']
        
        if not content:
            return list(map(lambda x: MangaChapter(self, x[0], x[1], manga, []), zip([], [])))
        
        return self.chapters_from_page(content, manga_card)[(page - 1) * 20:page * 20]

    async def iter_chapters(self, manga_url: str, manga_name) -> AsyncIterable[MangaChapter]:
        manga_card = MangaCard(self, manga_name, manga_url, '')

        request_url = f'{manga_card.url}'
        
        link = request_url.split("/")
        new_link = "/".join(link[:-1]) + "/full-chapter-list"
        self.pre_headers['hx-current-url'] = request_url
        self.pre_headers['hx-target'] = "chapter-list"
        self.pre_headers['referer'] = request_url

        content = await self.cget(request_url)
        
        del self.pre_headers['hx-current-url']
        del self.pre_headers['hx-target']
        del self.pre_headers['referer']
        
        for chapter in self.chapters_from_page(content, manga_card):
            yield chapter

    async def contains_url(self, url: str):
        return url.startswith(self.base_url.geturl())

    async def check_updated_urls(self, last_chapters: List[LastChapter]):
        content = await self.cget(self.updates_url)
        
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

  
