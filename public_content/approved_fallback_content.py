"""Approved public-site fallback content for the one-time Wagtail import."""

SERVICES = (
    {
        "slug": "web-digital",
        "title": "Web & Digital",
        "summary": (
            "Bespoke websites and digital experiences for research groups, "
            "organisations and scientific projects."
        ),
        "hero_asset": "web-digital",
        "hero_alt": "A LaBio Media website project",
        "capabilities": (
            ("Web design", "Clear, editorial digital systems."),
            ("Development", "Responsive, maintainable websites."),
            ("Digital strategy", "Structure built around audiences and goals."),
        ),
        "cta_label": "Discuss a web project",
        "cta_url": "https://labiomedia.com/contact",
    },
    {
        "slug": "video-production",
        "title": "Video Production",
        "summary": (
            "Research films, interviews and visual storytelling that make "
            "complex ideas easier to understand."
        ),
        "hero_asset": "video-production",
        "hero_alt": "Research video production",
        "capabilities": (
            ("Research films", "Stories grounded in scientific context."),
            ("Interviews", "Human, confident on-camera communication."),
            ("Editing", "A clear narrative from complex material."),
        ),
        "cta_label": "Discuss a video project",
        "cta_url": "https://labiomedia.com/contact",
    },
    {
        "slug": "photography",
        "title": "Photography",
        "summary": (
            "People, laboratories, events and environments captured with "
            "purpose and attention to detail."
        ),
        "hero_asset": "photography",
        "hero_alt": "Photography in a research laboratory",
        "capabilities": (
            ("People", "Natural portraits in real working environments."),
            ("Laboratories", "Credible images of research in practice."),
            ("Events", "Purposeful coverage and visual documentation."),
        ),
        "cta_label": "Discuss photography",
        "cta_url": "https://labiomedia.com/contact",
    },
    {
        "slug": "brand-design",
        "title": "Brand & Design",
        "summary": (
            "Visual identities, publications, infographics and digital "
            "materials that make complex information clear."
        ),
        "hero_asset": "brand-design",
        "hero_alt": "Scientific communication design",
        "capabilities": (
            ("Visual identity", "Distinct systems with scientific credibility."),
            ("Publications", "Clear editorial design for detailed information."),
            ("Infographics", "Complex ideas made easier to understand."),
        ),
        "cta_label": "Discuss a design project",
        "cta_url": "https://labiomedia.com/contact",
    },
)


CASE_STUDIES = (
    {
        "slug": "turku-bioscience",
        "title": "Turku Bioscience",
        "category": "Web / Digital",
        "summary": (
            "A digital platform for presenting research, people and scientific "
            "work at Turku Bioscience."
        ),
        "challenge": (
            "Present a large and diverse research community online in a way "
            "that is clear, accessible and visually engaging."
        ),
        "approach": (
            "A clean digital structure was developed around the people, "
            "research groups and scientific work that make up Turku Bioscience."
        ),
        "hero_asset": "web-digital",
        "gallery": (
            ("web-digital", "Turku Bioscience website"),
            ("turku-bioscience-barrier", "Turku Bioscience project"),
            ("turku-bioscience-inflames", "Turku Bioscience research"),
            ("turku-bioscience-ivaska", "Turku Bioscience website"),
        ),
        "service_slugs": ("web-digital", "brand-design"),
    },
    {
        "slug": "research-storytelling",
        "title": "Research Storytelling",
        "category": "Video / Science communication",
        "summary": (
            "Visual storytelling created to make complex research easier to "
            "understand and remember."
        ),
        "challenge": (
            "Communicate scientific ideas in a way that is understandable, "
            "engaging and memorable beyond the research community."
        ),
        "approach": (
            "Research stories were translated into visual narratives using "
            "filming, interviews, editing and graphic elements."
        ),
        "hero_asset": "video-production",
        "gallery": (
            ("video-production", "Research video"),
            ("research-storytelling-barrier", "Research storytelling"),
            ("research-storytelling-bc", "Research video production"),
            ("research-storytelling-tpc", "Research communication"),
        ),
        "service_slugs": ("video-production",),
    },
    {
        "slug": "laboratory-photography",
        "title": "Laboratory Photography",
        "category": "Photography",
        "summary": (
            "Photography capturing people, environments and everyday work "
            "within scientific research."
        ),
        "challenge": (
            "Show the people and environments behind scientific research in "
            "an authentic and visually engaging way."
        ),
        "approach": (
            "Photography focused on people, research environments and the "
            "details that make scientific work human."
        ),
        "hero_asset": "photography",
        "gallery": (
            ("photography", "Research laboratory"),
            ("laboratory-photography-filming", "Filming in a research environment"),
            ("laboratory-photography-bee", "Photography"),
            ("laboratory-photography-flower", "Scientific photography"),
        ),
        "service_slugs": ("photography", "brand-design"),
    },
)


ABOUT = {
    "title": "Science\nunderstanding.\nCreative\ncommunication.",
    "intro": (
        "LaBio Media helps research organisations turn complex ideas into "
        "clear, credible and engaging communication."
    ),
    "hero_asset": "about",
    "hero_alt": "LaBio Media",
    "body": (
        (
            "heading",
            {"text": "Bridging science and storytelling", "level": "h2"},
        ),
        (
            "rich_text",
            "<p>Research deserves communication that respects its complexity "
            "while giving people a clear way into the story. LaBio Media works "
            "at that intersection, combining scientific context with thoughtful "
            "visual and editorial craft.</p><p>The work spans websites, video, "
            "photography and design for research groups, scientific "
            "organisations and innovation projects. Each format is shaped around "
            "the subject, audience and purpose rather than a fixed template.</p>",
        ),
        (
            "quote",
            {
                "quote": (
                    "Effective communication does not simplify science. It gives "
                    "complex ideas a clear way into the world."
                ),
                "attribution": "LaBio Media",
            },
        ),
        (
            "heading",
            {"text": "Clarity with scientific context", "level": "h2"},
        ),
        (
            "rich_text",
            "<p>Close collaboration makes the difference. Understanding the "
            "people, methods and aims behind a project helps the final "
            "communication stay accurate, human and useful.</p><p>The goal is not "
            "simply to make research look good. It is to help important work "
            "become visible, understood and remembered by the audiences it needs "
            "to reach.</p>",
        ),
    ),
    "seo_title": "About — LaBio Media",
    "search_description": (
        "LaBio Media brings scientific understanding and creative communication "
        "together."
    ),
}


PRICING = {
    "title": "Pricing",
    "intro": (
        "Every LaBio Media project is shaped around its audience, goals and "
        "production needs."
    ),
    "positioning_message": "Every project starts with a conversation.",
}


MOCK_PRICING_ITEMS = (
    {
        "title": "[MOCK] Web & Digital starting point",
        "price_label": "[MOCK] From €1,500",
        "description": (
            "Mock pricing content for CMS layout validation. Replace before "
            "public launch."
        ),
        "features": (
            "[MOCK] Discovery and scope planning",
            "[MOCK] Editorial design direction",
            "[MOCK] Responsive implementation",
        ),
    },
    {
        "title": "[MOCK] Video Production starting point",
        "price_label": "[MOCK] From €1,200",
        "description": (
            "Mock pricing content for CMS layout validation. Replace before "
            "public launch."
        ),
        "features": (
            "[MOCK] Production planning",
            "[MOCK] Filming session",
            "[MOCK] Edited delivery",
        ),
    },
    {
        "title": "[MOCK] Photography starting point",
        "price_label": "[MOCK] From €600",
        "description": (
            "Mock pricing content for CMS layout validation. Replace before "
            "public launch."
        ),
        "features": (
            "[MOCK] Shoot planning",
            "[MOCK] Photography session",
            "[MOCK] Edited image selection",
        ),
    },
)


COLLABORATORS = (
    {
        "organization_name": "Turku Bioscience Centre",
        "asset": "collaborator-tbc",
        "logo_alt": "Turku Bioscience Centre logo",
        "url": "https://bioscience.fi",
        "display_order": 1,
    },
    {
        "organization_name": "InFLAMES",
        "asset": "collaborator-inflames",
        "logo_alt": "InFLAMES logo",
        "url": "https://inflames.utu.fi",
        "display_order": 2,
    },
    {
        "organization_name": "Nordic Metabolomics Society",
        "asset": "collaborator-nms",
        "logo_alt": "Nordic Metabolomics Society logo",
        "url": "https://nordicmetsoc.org",
        "display_order": 3,
    },
    {
        "organization_name": "BioCity Turku",
        "asset": "collaborator-biocity",
        "logo_alt": "BioCity Turku logo",
        "url": "https://biocityturku.fi",
        "display_order": 4,
    },
    {
        "organization_name": "INITIALISE",
        "asset": "collaborator-initialise",
        "logo_alt": "INITIALISE logo",
        "url": "https://initialise-project.eu/",
        "display_order": 5,
    },
)


MOCK_TESTIMONIALS = (
    {
        "person": "[MOCK] Client name 01",
        "quote": (
            "[MOCK TESTIMONIAL — replace before launch] LaBio Media helped us "
            "give a complex research story a clear and confident digital form."
        ),
        "role": "Mock role",
        "organization": "Mock organisation",
        "related_service_slug": "web-digital",
    },
    {
        "person": "[MOCK] Client name 02",
        "quote": (
            "[MOCK TESTIMONIAL — replace before launch] The production process "
            "was thoughtful, collaborative and grounded in the research."
        ),
        "role": "Mock role",
        "organization": "Mock organisation",
        "related_service_slug": "video-production",
    },
    {
        "person": "[MOCK] Client name 03",
        "quote": (
            "[MOCK TESTIMONIAL — replace before launch] The final images made "
            "our scientific work feel credible, human and approachable."
        ),
        "role": "Mock role",
        "organization": "Mock organisation",
        "related_case_study_slug": "laboratory-photography",
    },
)


ASSETS = {
    "web-digital": (
        "public/images/work/webdesignDev/thumb-bioscience.webp",
        "Approved public content — Web and Digital",
    ),
    "video-production": (
        "public/images/work/videos/thumb-inflames.JPG",
        "Approved public content — Video Production",
    ),
    "photography": (
        "public/images/work/photos/pia_lab.jpg",
        "Approved public content — Photography",
    ),
    "brand-design": (
        "public/images/work/webprintdesign/Euro BioImaging Poster EMBL_2.webp",
        "Approved public content — Brand and Design",
    ),
    "about": (
        "public/images/work/team/hk.jpg",
        "Approved public content — About LaBio Media",
    ),
    "turku-bioscience-barrier": (
        "public/images/work/webdesignDev/thumb-barrier.JPG",
        "Approved public content — Turku Bioscience barrier project",
    ),
    "turku-bioscience-inflames": (
        "public/images/work/webdesignDev/thumb-inflames.JPG",
        "Approved public content — Turku Bioscience InFLAMES project",
    ),
    "turku-bioscience-ivaska": (
        "public/images/work/webdesignDev/thumb-ivaska.JPG",
        "Approved public content — Turku Bioscience Ivaska project",
    ),
    "research-storytelling-barrier": (
        "public/images/work/videos/thumb-barrier.JPG",
        "Approved public content — Research Storytelling barrier film",
    ),
    "research-storytelling-bc": (
        "public/images/work/videos/thumb-bc.JPG",
        "Approved public content — Research Storytelling BioCity film",
    ),
    "research-storytelling-tpc": (
        "public/images/work/videos/thumb-tpc.JPG",
        "Approved public content — Research Storytelling TPC film",
    ),
    "laboratory-photography-filming": (
        "public/images/work/photos/filming-henok.jpg",
        "Approved public content — Laboratory filming",
    ),
    "laboratory-photography-bee": (
        "public/images/work/photos/Bumbel_bee.jpg",
        "Approved public content — Bumblebee photography",
    ),
    "laboratory-photography-flower": (
        "public/images/work/photos/Yellow_flower.jpg",
        "Approved public content — Flower photography",
    ),
    "collaborator-tbc": (
        "public/images/logos/tbc-logo.svg",
        "Approved collaborator — Turku Bioscience Centre",
    ),
    "collaborator-inflames": (
        "public/images/logos/InFlames_logo.svg",
        "Approved collaborator — InFLAMES",
    ),
    "collaborator-nms": (
        "public/images/logos/nms-logo.svg",
        "Approved collaborator — Nordic Metabolomics Society",
    ),
    "collaborator-biocity": (
        "public/images/logos/BioCityLogoRGB.svg",
        "Approved collaborator — BioCity Turku",
    ),
    "collaborator-initialise": (
        "public/images/logos/initialise-logo.svg",
        "Approved collaborator — INITIALISE",
    ),
}


SITE_SETTINGS = {
    "address": "Turku, Finland",
    "default_cta_label": "Start a conversation",
    "default_cta_url": "https://labiomedia.com/#contact",
}
