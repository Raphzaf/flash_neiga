import DOMPurify from 'dompurify';

/**
 * Sanitizes HTML content to prevent XSS attacks
 * @param {string} html - The HTML string to sanitize
 * @returns {string} - Sanitized HTML string
 */
export function sanitizeHtml(html) {
    if (!html) return '';
    
    // Configure DOMPurify to allow common safe HTML elements
    const config = {
        ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a', 'img', 'div', 'span', 'blockquote', 'code', 'pre'],
        ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id', 'target', 'rel'],
        ALLOW_DATA_ATTR: false,
    };
    
    return DOMPurify.sanitize(html, config);
}

/**
 * Validates and sanitizes video URLs to only allow trusted domains
 * @param {string} url - The video URL to validate
 * @returns {string|null} - Sanitized URL or null if invalid
 */
export function sanitizeVideoUrl(url) {
    if (!url) return null;
    
    try {
        const urlObj = new URL(url);
        const allowedDomains = [
            'youtube.com',
            'www.youtube.com',
            'youtu.be',
            'vimeo.com',
            'player.vimeo.com',
            'dailymotion.com',
            'www.dailymotion.com'
        ];
        
        if (allowedDomains.some(domain => urlObj.hostname === domain || urlObj.hostname.endsWith('.' + domain))) {
            return url;
        }
        
        return null;
    } catch (e) {
        return null;
    }
}
