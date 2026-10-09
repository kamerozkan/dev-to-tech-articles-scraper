import asyncio
import datetime
import logging
import httpx
from apify import Actor


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        max_items = actor_input.get("maxItems", 30)
        tag = (actor_input.get("tag") or "").strip().lower()
        top_days = actor_input.get("topDays", 0)
        state = (actor_input.get("state") or "rising").strip().lower()

        Actor.log.info(f"Starting Dev.to scraper (maxItems={max_items}, tag='{tag}', topDays={top_days}, state='{state}')...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        articles = []
        page = 1
        per_page = 30

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            while len(articles) < max_items:
                params = {
                    "page": page,
                    "per_page": min(per_page, max_items - len(articles))
                }
                if tag:
                    params["tag"] = tag
                if top_days and top_days > 0:
                    params["top"] = top_days
                elif state in ("rising", "fresh"):
                    params["state"] = state

                url = "https://dev.to/api/articles"
                Actor.log.info(f"Fetching page {page} with params {params}...")

                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        Actor.log.warning(f"HTTP error {resp.status_code}: {resp.text[:150]}")
                        break

                    data = resp.json()
                    if not data or not isinstance(data, list):
                        Actor.log.info("No more articles found in feed.")
                        break

                    for it in data:
                        user = it.get("user") or {}
                        article_item = {
                            "id": it.get("id"),
                            "title": it.get("title", ""),
                            "description": it.get("description", ""),
                            "url": it.get("url", ""),
                            "canonicalUrl": it.get("canonical_url", ""),
                            "authorName": user.get("name", ""),
                            "authorUsername": user.get("username", ""),
                            "authorGithub": user.get("github_username") or "",
                            "authorTwitter": user.get("twitter_username") or "",
                            "authorWebsite": user.get("website_url") or "",
                            "authorProfileImage": user.get("profile_image") or "",
                            "tags": it.get("tag_list", []),
                            "reactionsCount": it.get("public_reactions_count", 0),
                            "positiveReactionsCount": it.get("positive_reactions_count", 0),
                            "commentsCount": it.get("comments_count", 0),
                            "readingTimeMinutes": it.get("reading_time_minutes", 0),
                            "publishedAt": it.get("published_at", ""),
                            "coverImage": it.get("cover_image") or "",
                            "extractedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
                        }
                        articles.append(article_item)
                        if len(articles) >= max_items:
                            break

                    page += 1
                    await asyncio.sleep(0.5)

                except Exception as e:
                    Actor.log.error(f"Error fetching page {page}: {e}")
                    break

        await Actor.push_data(articles)
        try:
            await Actor.charge("job-extracted", count=len(articles))
        except Exception as ce:
            Actor.log.warning(f"Charge notice: {ce}")
        await Actor.set_value("OUTPUT", {
            "articlesExtracted": len(articles),
            "sampleArticle": f"{articles[0]['title']} by {articles[0]['authorName']}" if articles else None
        })
        Actor.log.info(f"Successfully scraped and pushed {len(articles)} articles.")


if __name__ == "__main__":
    asyncio.run(main())
