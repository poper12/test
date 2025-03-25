import os
import asyncio
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, AsyncIterable
import cloudscraper
from pathlib import Path

from models import LastChapter
from tools import LanguageSingleton


@dataclass
class MangaCard:
    client: "MangaClient"
    name: str
    url: str
    picture_url: str

    def get_url(self):
        return self.url

    def unique(self):
        return str(hash(self.url))


@dataclass
class MangaChapter:
    client: "MangaClient"
    name: str
    url: str
    manga: MangaCard
    pictures: List[str]
    novel: str
    
    def get_url(self):
        return self.url

    def unique(self):
        return str(hash(self.url))


def clean(name, length=-1):
    while '  ' in name:
        name = name.replace('  ', ' ')
    name = name.replace(':', '')
    if length != -1:
        name = name[:length]
    return name


class MangaClient(metaclass=LanguageSingleton):
    scraper = cloudscraper.create_scraper()

    async def get_url(self, url, *args, file_name=None, cache=False, req_content=True, method='get', data=None, **kwargs):
        if cache:
            path = Path(f'cache/{self.name}/{file_name}')
            os.makedirs(path.parent, exist_ok=True)
            try:
                with open(path, 'rb') as f:
                    content = f.read()
            except FileNotFoundError:
                if method == 'get':
                    response = await asyncio.to_thread(self.scraper.get, url, *args, **kwargs)
                elif method == 'post':
                    response = await asyncio.to_thread(self.scraper.post, url, data=data or {}, **kwargs)
                else:
                    raise ValueError
                if str(response.status_code).startswith('2'):
                    content = response.content
                    with open(path, 'wb') as f:
                        f.write(content)
        else:
            if method == 'get':
                response = await asyncio.to_thread(self.scraper.get, url, *args, **kwargs)
            elif method == 'post':
                response = await asyncio.to_thread(self.scraper.post, url, data=data or {}, **kwargs)
            else:
                raise ValueError
            content = response.content
        if req_content:
            return content
        else:
            return response

    async def set_pictures(self, manga_chapter: MangaChapter):
        requests_url = manga_chapter.url
        if requests_url.startswith("https://weebcentral.com/"):
            requests_url = requests_url.replace("%C2%", "&")
        
        try:
            headers = {**self.headers}
            if manga_chapter.manga:
                headers['referer'] = manga_chapter.manga.url
            
            response = await asyncio.to_thread(self.scraper.get, requests_url, headers=headers)
        
        except:
            response = await asyncio.to_thread(self.scraper.get, requests_url)
        
        content = response.content

        manga_chapter.pictures = await self.pictures_from_chapters(content, response)

        return manga_chapter

    async def download_pictures(self, manga_chapter: MangaChapter):
        if not manga_chapter.pictures:
            await self.set_pictures(manga_chapter)

        folder_name = f'{clean(manga_chapter.manga.name)}/{clean(manga_chapter.name)}'
        i = 0
        for picture in manga_chapter.pictures:
            ext = picture.split('.')[-1].split('?')[0].lower()
            file_name = f'{folder_name}/{format(i, "05d")}.{ext}'
            for _ in range(3):
                req = await self.get_picture(manga_chapter, picture, file_name=file_name, cache=True, req_content=False)
                if str(req.status_code).startswith('2'):
                    break
            else:
                raise ValueError
            i += 1

        return Path(f'cache/{manga_chapter.client.name}') / folder_name

    async def get_picture(self, manga_chapter: MangaChapter, url, *args, **kwargs):
        return await self.get_url(url, *args, **kwargs)

    async def get_cover(self, manga_card: MangaCard, *args, **kwargs):
        return await self.get_url(manga_card.picture_url, *args, **kwargs)

    async def check_updated_urls(self, last_chapters: List[LastChapter]):
        return [lc.url for lc in last_chapters], []

    @abstractmethod
    async def search(self, query: str = "", page: int = 1) -> List[MangaCard]:
        raise NotImplementedError

    @abstractmethod
    async def get_chapters(self, manga_card: MangaCard, page: int = 1) -> List[MangaChapter]:
        raise NotImplementedError

    @abstractmethod
    async def contains_url(self, url: str):
        raise NotImplementedError

    @abstractmethod
    async def iter_chapters(self, manga_url: str, manga_name: str) -> AsyncIterable[MangaChapter]:
        raise NotImplementedError

    @abstractmethod
    async def pictures_from_chapters(self, content: bytes, response=None):
        raise NotImplementedError
