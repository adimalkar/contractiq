# Google Search Console & Search Engine Indexing Guide for Termnova

This document details the search engine optimization (SEO) architecture implemented for **Termnova** (`https://termnova.onrender.com/`) and instructions for verifying and accelerating indexation on Google, Bing, and major search engines.

---

## 1. Implemented SEO Infrastructure

| Component | URL / Implementation | Description |
| :--- | :--- | :--- |
| **Robots Directives** | [`https://termnova.onrender.com/robots.txt`](https://termnova.onrender.com/robots.txt) | Grants crawler access to `/` and `/static/`, disallows backend `/api/`, links to sitemap. |
| **XML Sitemap** | [`https://termnova.onrender.com/sitemap.xml`](https://termnova.onrender.com/sitemap.xml) | Canonical URLs with `<lastmod>`, `<changefreq>`, and `<priority>`. |
| **PWA Web Manifest** | [`https://termnova.onrender.com/site.webmanifest`](https://termnova.onrender.com/site.webmanifest) | Mobile search rich previews and PWA configuration. |
| **Schema.org Structured Data** | `application/ld+json` in `index.html` | `WebApplication`, `Organization`, and `FAQPage` rich snippets. |
| **OpenGraph & Twitter Cards** | Meta tags in `index.html` | Social sharing previews for LinkedIn, Twitter, Discord, and Slack. |
| **Semantic Crawl Content** | Accessible semantic HTML in `index.html` | `<h1>`, `<h2>`, `<h3>` hierarchy with feature descriptions for non-JS crawlers. |

---

## 2. Immediate Steps to Index `termnova.onrender.com` on Google

### Step 1: Add Property in Google Search Console (GSC)
1. Go to [Google Search Console](https://search.google.com/search-console).
2. Click **Add Property** and select **URL Prefix**: `https://termnova.onrender.com/`.
3. Choose **HTML tag** verification method. If an ownership tag is needed, add `<meta name="google-site-verification" content="YOUR_KEY">` to `<head>`.

### Step 2: Submit Sitemap
1. In Google Search Console, navigate to **Indexing** $\rightarrow$ **Sitemaps**.
2. Enter `sitemap.xml` and click **Submit**.
3. Googlebot will schedule automatic crawling of all canonical pages.

### Step 3: Request Immediate URL Indexing (URL Inspection)
1. In the top search bar of Google Search Console, paste `https://termnova.onrender.com/`.
2. Click **Test Live URL**.
3. Once the live test passes, click **Request Indexing**.

---

## 3. Bing Webmaster Tools & Yahoo Indexing

1. Visit [Bing Webmaster Tools](https://www.bing.com/webmasters).
2. Import your property directly from Google Search Console or add `https://termnova.onrender.com/`.
3. Submit `https://termnova.onrender.com/sitemap.xml` under **Sitemaps**.
