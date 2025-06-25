from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
import requests

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/113.0.0.0 Safari/537.36"
}

def fetch_page_content(url: str) -> str | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_music_detail_page(html_content: str) -> dict | None:
    soup = BeautifulSoup(html_content, 'html.parser')
    post_container = soup.find("div", class_="post anm")
    if not post_container:
        return None

    content_div = post_container.find("div", class_="pcontent")
    if not content_div or not content_div.div:
        return None

    title = content_div.div.h1.text if content_div.div.h1 else "No Title"
    image_url = content_div.div.img.get("data-src") if content_div.div.img else None

    content_div.decompose()
    heading_h2 = post_container.find("h2")
    if heading_h2:
        heading_h2.decompose()

    download_links = []
    for anchor_tag in post_container.find_all("a"):
        if anchor_tag.get("rel"):
            continue
        href = anchor_tag.get("href")
        quality = ""
        if anchor_tag.div:
            divs = anchor_tag.div.find_all("div")
            if len(divs) > 1 and divs[1].span:
                quality = divs[1].span.text
        download_links.append({"url": href, "quality": quality})

    return {"title": title, "image": image_url, "links": download_links}

def parse_detail_pages(detail_urls: list[str], total_pages:int =1) -> list[dict]:
    results = []
    for url in detail_urls:
        content = fetch_page_content(url)
        if content:
            detail_data = parse_music_detail_page(content)
            if detail_data:
                results.append(detail_data)
    data = {
        "channel": "@tss_apis",
        "programer": "tss",
        "id_rubika": "@tss_dev",
        "total pages": total_pages,
        "results": results
    }
    return [data]

@app.get("/search")
def search_music(q: str = Query(..., min_length=1), page: int = Query(2, ge=1, le=5)):
    formatted_query = q.replace(" ", "+")
    base_search_url = f"https://nex1music.com/?s={formatted_query}"

    first_page_html = fetch_page_content(base_search_url)
    if not first_page_html:
        raise HTTPException(status_code=500, detail="Failed to fetch search results.")

    soup = BeautifulSoup(first_page_html, 'html.parser')
    pagination_links = soup.find_all("a", class_="page-numbers")

    if soup.find("div", class_="pn") and len(pagination_links) >= 2:
        try:
            total_pages = int(pagination_links[-2].text)
        except ValueError:
            total_pages = 1
    else:
        total_pages = 1

    page_target = min(total_pages, page)
    search_result_pages = [f"https://nex1music.com/page/{page_target}/?s={formatted_query}"]

    music_results = []
    for page_url in search_result_pages:
        page_html = fetch_page_content(page_url)
        if not page_html:
            continue

        soup = BeautifulSoup(page_html, 'html.parser')
        music_posts = soup.find_all("div", class_="post anm")
        if not music_posts:
            continue

        detail_urls = []
        for post in music_posts:
            detail_url = post.h2.a.get("href")
            if detail_url:
                detail_urls.append(detail_url)

        details = parse_detail_pages(detail_urls, total_pages)
        music_results.extend(details)

    if not music_results:
        return JSONResponse(status_code=404, content={"message": "No results found"})

    return music_results
