const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_HOSTS = new Set(['youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtube-nocookie.com']);

export function extractYouTubeVideoId(input: string): string | null {
  const raw = input.trim();
  if (!raw) return null;

  let parsed: URL;
  try {
    parsed = new URL(raw.includes('://') ? raw : `https://${raw}`);
  } catch {
    return null;
  }

  let host = parsed.hostname.toLowerCase();
  if (host.startsWith('www.')) host = host.slice(4);

  let videoId: string | null = null;
  if (host === 'youtu.be') {
    videoId = parsed.pathname.split('/').filter(Boolean)[0] ?? null;
  } else if (YOUTUBE_HOSTS.has(host)) {
    if (parsed.pathname === '/watch') {
      videoId = parsed.searchParams.get('v');
    } else {
      const [kind, id] = parsed.pathname.split('/').filter(Boolean);
      if (['shorts', 'embed', 'live'].includes(kind)) videoId = id ?? null;
    }
  }

  return videoId && VIDEO_ID_RE.test(videoId) ? videoId : null;
}

export function isValidYouTubeVideoUrl(input: string): boolean {
  return extractYouTubeVideoId(input) !== null;
}
