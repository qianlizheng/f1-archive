#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11 支车队的新闻/新闻稿源配置

探测结论（2026-11-02 实测）：
- 大多数车队站点是 JS 渲染，HTML 里没有文章链接 → 走 sitemap.xml（都带 lastmod）
- McLaren 有静态列表页，走 HTML
- Ferrari 是纯客户端渲染，既无 sitemap 也无静态链接 → 暂缺
- Alpine / Audi 是品牌站，混着民用车新闻 → 用关键词过滤出 F1 相关

每个源：
  sitemap     sitemap 地址（可以是 index，会自动展开）
  include     只保留匹配的文章 URL（正则）
  exclude     排除掉匹配的 URL（正则）
  max_age     只要 lastmod 在最近 N 天内的（可选）
"""

TEAM_SOURCES = [
    {
        # 它的 sitemap 把 1397 个页面全标成当天，lastmod 不可用，改抓列表页
        "name": "team-mercedes",
        "label": "Mercedes",
        "type": "html",
        "limit": 8,
        "title_from_slug": True,
        "url": "https://www.mercedesamgf1.com/news",
        "base": "https://www.mercedesamgf1.com",
        "link_re": r'href="(/news/[^"?]+)"[^>]*>([^<]*)',
    },
    {
        "name": "team-astonmartin",
        "label": "Aston Martin",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.astonmartinf1.com/sitemap.xml",
        "include": r"/en-GB/news/[^/]+/[^/]+/?$",
    },
    {
        "name": "team-williams",
        "label": "Williams",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.williamsf1.com/sitemap.xml",
        "include": r"/articles/[0-9a-f-]{20,}/[^/]+/?$",
    },
    {
        "name": "team-haas",
        "label": "Haas",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.haasf1team.com/sitemap.xml",
        "include": r"/news/[^/]+/?$",
    },
    {
        "name": "team-cadillac",
        "label": "Cadillac",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.cadillacf1team.com/sitemap.xml",
        "include": r"/news/[^/]+/?$",
    },
    {
        # Red Bull 的文章是 /int-en/<slug>，栏目页是 /int-en/<section>/<slug>
        "name": "team-redbull",
        "label": "Red Bull",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.redbullracing.com/sitemap.xml",
        "include": r"/int-en/[^/]+/?$",
        "min_slug": 12,
        "exclude": r"/(videos|races|galleries|team|newsletter|f1-academy|careers|esports|shop|tickets|partners|heritage|drivers|podcast-episodes)/",
    },
    {
        "name": "team-racingbulls",
        "label": "Racing Bulls",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.visacashapprb.com/sitemap.xml",
        "include": r"/int-en/[^/]+/?$",
        "min_slug": 12,
        "exclude": r"/(videos|races|galleries|team|newsletter|f1-academy|careers|esports|shop|tickets|partners|heritage|drivers)/",
    },
    {
        # 品牌站，需要按关键词筛出 F1 相关
        "name": "team-audi",
        "label": "Audi",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://www.audi-mediacenter.com/sitemap.xml",
        "include": r"/media-releases/.+",
        "keyword": r"(formula[- ]?1|formel[- ]?1|f1|grand[- ]prix|\bgp\b)",
    },
    {
        # WordPress，sitemap 是 index，需要展开 post-sitemap*
        "name": "team-alpine",
        "label": "Alpine",
        "type": "sitemap",
        "limit": 8,
        "max_age_days": 14,
        "sitemap": "https://media.alpinecars.com/wp-sitemap.xml",
        "sitemap_filter": r"/post-sitemap\d*\.xml$",
        "insecure": True,
        "keyword": r"(formula[- ]?1|formel[- ]?1|f1|grand[- ]prix|\bgp\b)",
    },
    {
        # 少数有静态列表页的站点
        "name": "team-mclaren",
        "label": "McLaren",
        "type": "html",
        "limit": 8,
        "url": "https://www.mclaren.com/racing/latest-news/",
        "base": "https://www.mclaren.com",
        "link_re": r'href="(/racing/formula-1/articles/[^"]+)"[^>]*>(.*?)</a>',
    },
    # Ferrari：纯客户端渲染，无 sitemap 文章、无静态链接，暂缺（见 README）
]
