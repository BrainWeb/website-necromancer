import asyncio
import httpx

async def main():
    url = "http://abcqualitymanagement.com//*"
    request_url = "https://web.archive.org/cdx/search/xd"
    params = [("output", "json"), ("url", url), ("fl", "timestamp,original"), ("collapse", "digest"), ("gzip", "false"), ("page", "0")]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(request_url, params=params, timeout=30.0)
            print(f"Status: {response.status_code}")
            print(f"Content length: {len(response.text)}")
            if response.status_code >= 400:
                print(response.text)
        except Exception as e:
            print(f"Exception: {repr(e)}")

asyncio.run(main())
