import { NextRequest } from 'next/server';
import * as cheerio from 'cheerio';

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get('url');
  const maxLinks = parseInt(req.nextUrl.searchParams.get('max') || '50', 10);

  if (!url) {
    return new Response('Missing URL', { status: 400 });
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const sendEvent = (data: any) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      try {
        const baseUrl = new URL(url);
        sendEvent({ type: 'info', message: `Fetching ${url}...` });

        const response = await fetch(url, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (compatible; LinkCrawlerBot/1.0)',
          }
        });

        if (!response.ok) {
          sendEvent({ type: 'error', message: `Failed to fetch starting URL: ${response.status} ${response.statusText}` });
          controller.close();
          return;
        }

        const html = await response.text();
        const $ = cheerio.load(html);
        const links = new Set<string>();

        $('a[href]').each((_, el) => {
          const href = $(el).attr('href');
          if (href) {
            try {
              // Ignore mailto, tel, javascript, etc.
              if (href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) {
                return;
              }
              
              // Resolve relative URLs
              const resolvedUrl = new URL(href, url).href;
              
              // Only add http/https links
              if (resolvedUrl.startsWith('http')) {
                // Remove hash fragments to avoid duplicate checking of the same page
                const urlWithoutHash = new URL(resolvedUrl);
                urlWithoutHash.hash = '';
                links.add(urlWithoutHash.href);
              }
            } catch (e) {
              // Ignore invalid URLs
            }
          }
        });

        const linkArray = Array.from(links);
        sendEvent({ type: 'info', message: `Found ${linkArray.length} unique links.` });
        sendEvent({ type: 'start', total: Math.min(linkArray.length, maxLinks) });

        const linksToCheck = linkArray.slice(0, maxLinks);

        // Check links in parallel batches to speed up
        const BATCH_SIZE = 5;
        for (let i = 0; i < linksToCheck.length; i += BATCH_SIZE) {
          const batch = linksToCheck.slice(i, i + BATCH_SIZE);
          
          await Promise.all(batch.map(async (link) => {
            let isInternal = false;
            try {
              isInternal = new URL(link).hostname === baseUrl.hostname;
            } catch (e) {}

            try {
              const headResponse = await fetch(link, { 
                method: 'HEAD', 
                redirect: 'follow',
                headers: { 'User-Agent': 'Mozilla/5.0 (compatible; LinkCrawlerBot/1.0)' }
              });
              
              let status = headResponse.status;
              let ok = headResponse.ok;

              if (status === 405 || status === 403 || status === 401) {
                 const getResponse = await fetch(link, { 
                   method: 'GET', 
                   redirect: 'follow',
                   headers: { 'User-Agent': 'Mozilla/5.0 (compatible; LinkCrawlerBot/1.0)' }
                 });
                 status = getResponse.status;
                 ok = getResponse.ok;
              }

              sendEvent({
                type: 'result',
                data: {
                  url: link,
                  status,
                  ok,
                  isInternal
                }
              });
            } catch (error) {
              sendEvent({
                type: 'result',
                data: {
                  url: link,
                  status: 0,
                  ok: false,
                  isInternal,
                  error: error instanceof Error ? error.message : 'Unknown error'
                }
              });
            }
          }));
        }

        sendEvent({ type: 'done', message: 'Crawling complete.' });
      } catch (error) {
        sendEvent({ type: 'error', message: error instanceof Error ? error.message : 'Unknown error' });
      } finally {
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
