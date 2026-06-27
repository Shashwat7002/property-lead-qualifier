"""
Generate Sprint Lead Generation — Scoring Explainer PDF
Uses reportlab only (no LibreOffice required).
Output: ~/Desktop/Sprint_Lead_Scoring_Explained.pdf
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import (
    HexColor, white, black
)
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, NextPageTemplate
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Flowable
import os

# ── Brand colors ──────────────────────────────────────────────────────────────
NAVY       = HexColor("#1E3A5F")
BLUE       = HexColor("#2563EB")
BLUE_LIGHT = HexColor("#EFF6FF")
RED        = HexColor("#DC2626")
RED_LIGHT  = HexColor("#FEF2F2")
GREEN      = HexColor("#059669")
GREEN_LIGHT= HexColor("#ECFDF5")
AMBER      = HexColor("#D97706")
AMBER_LIGHT= HexColor("#FEF3C7")
GRAY       = HexColor("#6B7280")
GRAY_LIGHT = HexColor("#F3F4F6")
BORDER     = HexColor("#E5E7EB")
PURPLE     = HexColor("#7C3AED")
PURPLE_LIGHT = HexColor("#F5F3FF")

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    return {
        "cover_title": ParagraphStyle("cover_title",
            fontName="Helvetica-Bold", fontSize=32, textColor=white,
            leading=40, alignment=TA_CENTER),
        "cover_sub": ParagraphStyle("cover_sub",
            fontName="Helvetica", fontSize=14, textColor=HexColor("#BFDBFE"),
            leading=20, alignment=TA_CENTER),
        "cover_date": ParagraphStyle("cover_date",
            fontName="Helvetica", fontSize=11, textColor=HexColor("#93C5FD"),
            leading=14, alignment=TA_CENTER),

        "h1": ParagraphStyle("h1",
            fontName="Helvetica-Bold", fontSize=20, textColor=NAVY,
            leading=26, spaceAfter=4),
        "h2": ParagraphStyle("h2",
            fontName="Helvetica-Bold", fontSize=14, textColor=NAVY,
            leading=18, spaceBefore=12, spaceAfter=4),
        "h3": ParagraphStyle("h3",
            fontName="Helvetica-Bold", fontSize=11, textColor=BLUE,
            leading=15, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=10.5, textColor=HexColor("#1F2937"),
            leading=16, spaceAfter=6),
        "body_small": ParagraphStyle("body_small",
            fontName="Helvetica", fontSize=9.5, textColor=HexColor("#374151"),
            leading=14, spaceAfter=4),
        "caption": ParagraphStyle("caption",
            fontName="Helvetica-Oblique", fontSize=9, textColor=GRAY,
            leading=13, alignment=TA_CENTER),
        "mono": ParagraphStyle("mono",
            fontName="Courier-Bold", fontSize=10, textColor=NAVY,
            leading=15, spaceAfter=3),
        "mono_sm": ParagraphStyle("mono_sm",
            fontName="Courier", fontSize=9, textColor=HexColor("#374151"),
            leading=13),
        "tag_red": ParagraphStyle("tag_red",
            fontName="Helvetica-Bold", fontSize=9, textColor=RED, leading=12),
        "tag_blue": ParagraphStyle("tag_blue",
            fontName="Helvetica-Bold", fontSize=9, textColor=BLUE, leading=12),
        "tag_green": ParagraphStyle("tag_green",
            fontName="Helvetica-Bold", fontSize=9, textColor=GREEN, leading=12),
        "tag_gray": ParagraphStyle("tag_gray",
            fontName="Helvetica", fontSize=9, textColor=GRAY, leading=12),
        "label": ParagraphStyle("label",
            fontName="Helvetica-Bold", fontSize=8.5, textColor=GRAY,
            leading=11, spaceAfter=3),
        "note_box": ParagraphStyle("note_box",
            fontName="Helvetica-Oblique", fontSize=9.5, textColor=HexColor("#374151"),
            leading=14),
        "cell": ParagraphStyle("cell",
            fontName="Helvetica", fontSize=9.5, textColor=HexColor("#1F2937"),
            leading=13),
        "cell_bold": ParagraphStyle("cell_bold",
            fontName="Helvetica-Bold", fontSize=9.5, textColor=HexColor("#1F2937"),
            leading=13),
        "pts_pos": ParagraphStyle("pts_pos",
            fontName="Helvetica-Bold", fontSize=9.5, textColor=GREEN,
            leading=13, alignment=TA_RIGHT),
        "pts_neg": ParagraphStyle("pts_neg",
            fontName="Helvetica-Bold", fontSize=9.5, textColor=RED,
            leading=13, alignment=TA_RIGHT),
        "tier_score": ParagraphStyle("tier_score",
            fontName="Helvetica-Bold", fontSize=22, textColor=white,
            leading=26, alignment=TA_CENTER),
        "tier_name": ParagraphStyle("tier_name",
            fontName="Helvetica-Bold", fontSize=11, textColor=white,
            leading=14, alignment=TA_CENTER),
        "strat_trigger": ParagraphStyle("strat_trigger",
            fontName="Helvetica-Bold", fontSize=9, textColor=NAVY, leading=12),
        "strat_label": ParagraphStyle("strat_label",
            fontName="Helvetica-Oblique", fontSize=9, textColor=GRAY, leading=12),
    }


# ── Custom flowable: colored section banner ───────────────────────────────────
class SectionBanner(Flowable):
    def __init__(self, number, title, color=NAVY, width=CONTENT_W):
        super().__init__()
        self.number = number
        self.title  = title
        self.color  = color
        self.width  = width
        self.height = 32

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        c.setFillColor(HexColor("#93C5FD"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(10, 11, f"SECTION {self.number}")
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, 10, self.title)


class ColorBox(Flowable):
    """A rounded rectangle background box wrapping a block of content."""
    def __init__(self, content_height, bg_color, border_color=None, width=CONTENT_W, radius=6):
        super().__init__()
        self.content_height = content_height
        self.bg_color = bg_color
        self.border_color = border_color
        self.width = width
        self.radius = radius
        self.height = content_height

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg_color)
        if self.border_color:
            c.setStrokeColor(self.border_color)
            c.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=1)
        else:
            c.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=0)


# ── Header / Footer ───────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        # Header
        canvas.setFillColor(NAVY)
        canvas.rect(MARGIN, PAGE_H - 0.5*inch, CONTENT_W, 1, fill=1, stroke=0)
        canvas.setFillColor(GRAY)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, PAGE_H - 0.42*inch, "SPRINT LEAD GENERATION — SCORING SYSTEM EXPLAINED")
        canvas.drawRightString(MARGIN + CONTENT_W, PAGE_H - 0.42*inch, f"Page {doc.page}")

        # Footer line
        canvas.setFillColor(BORDER)
        canvas.rect(MARGIN, 0.45*inch, CONTENT_W, 0.5, fill=1, stroke=0)
        canvas.setFillColor(GRAY)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, 0.32*inch, "For licensed realtor use — North Fulton & Forsyth County, GA")
    canvas.restoreState()


# ── Document builder ──────────────────────────────────────────────────────────
def build():
    out_path = os.path.expanduser("~/Desktop/Sprint_Lead_Scoring_Explained.pdf")
    doc = BaseDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.65*inch, bottomMargin=0.6*inch,
    )

    # Cover has no header/footer; content pages do
    cover_frame   = Frame(0, 0, PAGE_W, PAGE_H, leftPadding=0, rightPadding=0,
                          topPadding=0, bottomPadding=0)
    content_frame = Frame(MARGIN, 0.6*inch, CONTENT_W, PAGE_H - 1.25*inch)

    doc.addPageTemplates([
        PageTemplate(id="Cover",   frames=[cover_frame]),
        PageTemplate(id="Content", frames=[content_frame], onPage=on_page),
    ])

    S = make_styles()
    story = []

    # ═══════════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════════════════════════════════════
    class CoverBackground(Flowable):
        def draw(self):
            c = self.canv
            # Full navy background
            c.setFillColor(NAVY)
            c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
            # Blue accent strip at top
            c.setFillColor(BLUE)
            c.rect(0, PAGE_H - 0.6*inch, PAGE_W, 0.6*inch, fill=1, stroke=0)
            # Decorative diagonal band
            c.setFillColor(HexColor("#1A3356"))
            from reportlab.graphics.shapes import Drawing
            c.saveState()
            c.transform(1, 0, 0, 1, 0, 0)
            c.beginPath()
            c.moveTo(0, PAGE_H * 0.45)
            c.lineTo(PAGE_W, PAGE_H * 0.35)
            c.lineTo(PAGE_W, PAGE_H * 0.42)
            c.lineTo(0, PAGE_H * 0.52)
            c.closePath()
            c.fill()
            c.restoreState()
        @property
        def width(self): return PAGE_W
        @property
        def height(self): return PAGE_H

    class CoverPage(Flowable):
        """Single flowable that draws the entire cover page."""
        def __init__(self):
            super().__init__()
            self._w = PAGE_W
            self._h = PAGE_H

        def wrap(self, availW, availH):
            return (self._w, self._h)

        def draw(self):
            c = self.canv
            # Full navy background
            c.setFillColor(NAVY)
            c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
            # Blue accent strip at top
            c.setFillColor(BLUE)
            c.rect(0, PAGE_H - 0.6*inch, PAGE_W, 0.6*inch, fill=1, stroke=0)
            # Decorative diagonal band
            from reportlab.graphics.shapes import Polygon
            c.setFillColor(HexColor("#1A3356"))
            p = c.beginPath()
            p.moveTo(0, PAGE_H * 0.45)
            p.lineTo(PAGE_W, PAGE_H * 0.35)
            p.lineTo(PAGE_W, PAGE_H * 0.42)
            p.lineTo(0, PAGE_H * 0.52)
            p.close()
            c.drawPath(p, fill=1, stroke=0)

            # Top label
            c.setFillColor(HexColor("#60A5FA"))
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(PAGE_W/2, PAGE_H - 1.2*inch, "NORTH FULTON & FORSYTH COUNTY, GA")

            # Main title
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 38)
            c.drawCentredString(PAGE_W/2, PAGE_H - 2.0*inch, "Sprint Lead")
            c.drawCentredString(PAGE_W/2, PAGE_H - 2.6*inch, "Generation")

            # Subtitle
            c.setFillColor(HexColor("#93C5FD"))
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(PAGE_W/2, PAGE_H - 3.2*inch, "How the Scoring System Works")

            # Divider line
            c.setStrokeColor(BLUE)
            c.setLineWidth(2)
            c.line(PAGE_W/2 - 1.5*inch, PAGE_H - 3.5*inch, PAGE_W/2 + 1.5*inch, PAGE_H - 3.5*inch)

            # Description
            c.setFillColor(HexColor("#BFDBFE"))
            c.setFont("Helvetica", 12)
            c.drawCentredString(PAGE_W/2, PAGE_H - 3.9*inch, "A plain-English guide to how the platform")
            c.drawCentredString(PAGE_W/2, PAGE_H - 4.15*inch, "finds and ranks your best listing leads")

            # Three pillars
            pillars = [
                (RED,   "MOTIVATION", "Does the owner\nwant to sell?",     "60%"),
                (BLUE,  "FIT",        "Is it the right\ntype of listing?", "25%"),
                (GREEN, "CONFIDENCE", "How sure are\nwe in the data?",     "15%"),
            ]
            box_w = 1.4*inch
            gap   = 0.25*inch
            total = len(pillars)*box_w + (len(pillars)-1)*gap
            start_x = (PAGE_W - total) / 2

            for i, (col, name, desc, pct) in enumerate(pillars):
                x = start_x + i*(box_w + gap)
                y = PAGE_H - 6.2*inch
                c.setFillColor(HexColor("#0F2A4A"))
                c.roundRect(x, y, box_w, 1.5*inch, 6, fill=1, stroke=0)
                c.setFillColor(col)
                c.roundRect(x, y + 1.2*inch, box_w, 0.3*inch, 6, fill=1, stroke=0)
                c.rect(x, y + 1.2*inch, box_w, 0.15*inch, fill=1, stroke=0)
                c.setFillColor(white)
                c.setFont("Helvetica-Bold", 14)
                c.drawCentredString(x + box_w/2, y + 1.25*inch, pct)
                c.setFont("Helvetica-Bold", 9)
                c.drawCentredString(x + box_w/2, y + 1.02*inch, name)
                c.setFillColor(HexColor("#93C5FD"))
                c.setFont("Helvetica", 8)
                lines = desc.split("\n")
                for j, line in enumerate(lines):
                    c.drawCentredString(x + box_w/2, y + 0.72*inch - j*0.14*inch, line)

            # Bottom note
            c.setFillColor(HexColor("#64748B"))
            c.setFont("Helvetica-Oblique", 9)
            c.drawCentredString(PAGE_W/2, 0.7*inch, "For licensed realtor use only — Sprint Lead Generation Platform")

    story.append(CoverPage())
    story.append(NextPageTemplate("Content"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — THE BIG PICTURE
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("1", "The Big Picture — What Does This System Do?"))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Imagine you're a college football coach looking for players to recruit. "
        "You can't personally visit every high school in the country, so you use a "
        "<b>scouting system</b> — one that automatically reviews thousands of players "
        "and flags the best ones for you to call.",
        S["body"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Sprint Lead Generation does the exact same thing — but for homeowners who "
        "might be ready to sell. It automatically reviews properties from the MLS, "
        "pulls in extra data from six different sources, and gives every home a "
        "<b>score from 0 to 100</b>. The higher the score, the more likely that "
        "owner is a great listing client for you.",
        S["body"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Every property gets scored on <b>three separate questions</b>, which are "
        "then combined into one final number:",
        S["body"]))

    story.append(Spacer(1, 8))

    # Three pillars table
    pillar_data = [
        [
            Paragraph("🔥", S["h2"]),
            Paragraph("🎯", S["h2"]),
            Paragraph("✅", S["h2"]),
        ],
        [
            Paragraph("Motivation", S["h3"]),
            Paragraph("Fit", S["h3"]),
            Paragraph("Confidence", S["h3"]),
        ],
        [
            Paragraph('<font color="#DC2626"><b>60% of the score</b></font>', S["body_small"]),
            Paragraph('<font color="#2563EB"><b>25% of the score</b></font>', S["body_small"]),
            Paragraph('<font color="#059669"><b>15% of the score</b></font>', S["body_small"]),
        ],
        [
            Paragraph("Does the owner <b>actually want</b> to sell? Do they have a reason to move?", S["body_small"]),
            Paragraph("Is this the <b>right kind of property</b> in the right area at the right price?", S["body_small"]),
            Paragraph("How <b>reliable</b> is the data we have? Are we reading the signals correctly?", S["body_small"]),
        ],
    ]
    pillar_col = CONTENT_W / 3
    pillar_tbl = Table(pillar_data, colWidths=[pillar_col]*3)
    pillar_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (0,-1), RED_LIGHT),
        ("BACKGROUND",  (1,0), (1,-1), BLUE_LIGHT),
        ("BACKGROUND",  (2,0), (2,-1), GREEN_LIGHT),
        ("TOPPADDING",  (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING",(0,0), (-1,-1), 12),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",       (0,0), (-1,1),  "CENTER"),
        ("GRID",        (0,0), (-1,-1), 0.5, BORDER),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(pillar_tbl)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<b>Why does Motivation count for 60%?</b> Because the best-located, "
        "most beautiful home in Alpharetta is useless to you as a listing agent "
        "if the owner has zero interest in selling. Seller motivation is the "
        "hardest thing to find — and the most valuable.",
        S["note_box"]))

    story.append(Spacer(1, 14))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — DATA SOURCES
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("2", "Where Does the Data Come From? (6 Sources)"))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "The system connects to six different data sources automatically. Think of "
        "them like six different investigators, each digging up a different piece "
        "of information about the homeowner:",
        S["body"]))
    story.append(Spacer(1, 8))

    sources = [
        (NAVY,         "🏠", "FMLS — First MLS",
         "The starting point. This is the Multiple Listing Service database — "
         "the same system realtors use to list homes. It provides the property "
         "address, list price, property type (house vs. condo), year it was built, "
         "number of bedrooms, owner name, and county. <b>Every other data source "
         "builds on top of this.</b>"),

        (AMBER,        "📈", "FRED — Federal Reserve Bank of St. Louis",
         "Three national economic signals, fetched once per scan (not per property): "
         "<b>(1) The 30-year mortgage rate</b> — if rates are high (above 6.25%), "
         "absentee landlords feel more pressure to sell. "
         "<b>(2) Atlanta's unemployment rate</b> — low unemployment means a healthy "
         "market; high unemployment can push owners to sell. "
         "<b>(3) Fulton County home price growth</b> — strong appreciation over the "
         "past 12 months confirms that equity is building."),

        (GREEN,        "🗺️", "Census ACS — U.S. Census Bureau",
         "The Census Bureau tracks detailed statistics for every census tract "
         "(roughly 4,000 people). For each property, the system geocodes the address "
         "to find its tract, then pulls: <b>median household income, median home value, "
         "owner-occupancy rate, vacancy rate, and the percentage of residents aged 65+.</b> "
         "A high 65+ rate signals an older neighborhood — more owners may be downsizing soon."),

        (HexColor("#9A3412"), "📍", "OSM — OpenStreetMap / Overpass API",
         "OpenStreetMap is like Google Maps, but free and open to everyone. "
         "The system searches a <b>one-mile radius</b> around each property for: "
         "grocery stores, parks, and major highways. A home that's walkable to groceries "
         "and parks is more desirable to buyers — which means it sells faster. "
         "A home right next to a major highway? That's a problem that hurts the listing."),

        (HexColor("#14532D"), "🎓", "GOSA — Governor's Office of Student Achievement",
         "Georgia publishes a school performance score called the CCRPI "
         "(College and Career Ready Performance Index) for every school, from 0 to 100. "
         "The system has pre-loaded scores for <b>14 ZIP codes</b> in North Fulton and "
         "Forsyth County. A score above 92 means premium school zone — homes in "
         "Cambridge HS or Northview HS zones can command a $150,000–$200,000 "
         "premium from buyers."),

        (PURPLE,       "⚖️", "GSCCCA — Georgia Deed Index",
         "This is the most powerful optional source. GSCCCA (Georgia Superior Court "
         "Clerks' Cooperative Authority) is a free statewide database of every recorded "
         "deed in Georgia since 1990. The system looks up each owner by name and county "
         "to find <b>when they bought the property</b> (which tells us how many years "
         "they've owned it) and <b>how they bought it</b> (warranty deed = normal "
         "purchase; quit claim deed might mean a divorce or estate transfer; "
         "sheriff's deed means foreclosure). This requires a free account."),
    ]

    for color, icon, name, desc in sources:
        row_data = [[
            Paragraph(f"{icon}  {name}", ParagraphStyle("sh", fontName="Helvetica-Bold",
                fontSize=11, textColor=color, leading=15)),
            Paragraph(desc, S["body_small"]),
        ]]
        row_tbl = Table(row_data, colWidths=[1.7*inch, CONTENT_W - 1.7*inch])
        row_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), GRAY_LIGHT),
            ("TOPPADDING",   (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0), (-1,-1), 8),
            ("LEFTPADDING",  (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LINEBELOW",    (0,0), (-1,-1), 0.5, BORDER),
        ]))
        story.append(row_tbl)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — THE THREE SCORES
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("3", "The Three Scores — What Goes Into Each One?", BLUE))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Each of the three dimensions — Motivation, Fit, and Confidence — is calculated "
        "separately before they're combined. Here's exactly what pushes each score "
        "up or down:",
        S["body"]))
    story.append(Spacer(1, 10))

    # ── MOTIVATION ────────────────────────────────────────────────────────────
    story.append(Paragraph("🔥  MOTIVATION SCORE  (60% of final score)", S["h2"]))
    story.append(Paragraph(
        "This is the most important score. It asks: <b>does the owner have a real "
        "reason to want to sell?</b> Think of it like checking if a student is "
        "actually motivated to apply to college vs. just going because their parents "
        "told them to. The signals below each add or subtract points from the "
        "motivation total.",
        S["body"]))
    story.append(Spacer(1, 6))

    mot_signals = [
        ("Tax delinquency or foreclosure",         "+18", "Owner is behind on taxes or facing foreclosure — high urgency to sell"),
        ("Estate / probate confirmed",             "+18", "Owner name shows ESTATE, HEIRS, EXECUTOR — property being settled"),
        ("Free and clear (no mortgage)",           "+15", "Owner has no loan — nothing holding them to the home"),
        ("High equity (owns 60%+ of home value)",  "+15", "Owner has built up a lot of wealth in the home"),
        ("Out-of-state absentee owner",            "+14", "Owner lives in another state — not using or attached to the property"),
        ("Owned 15+ years",                        "+10", "Long tenure increases the odds they're ready for a change"),
        ("Empty-nest (3+ bedrooms, 20+ years owned)","+8","Kids are likely grown and gone — owners might downsize"),
        ("Vacant property",                         "+8", "Nobody living there — owner has less reason to hold on"),
        ("Ownership transfer anomaly",              "+8", "Deed type suggests divorce, estate, or non-standard sale"),
        ("Mom-and-Pop landlord (2–5 properties)",   "+8", "Small landlords often want to cash out of their portfolio"),
        ("In-state absentee owner",                 "+6", "Lives elsewhere in Georgia — not owner-occupied"),
        ("Senior exemption on file",                "+6", "County records confirm owner qualifies for senior tax exemption"),
        ("Living trust (no other signals)",         "+6", "Possible succession planning, but needs more evidence"),
        ("Owned 8–14 years",                        "+6", "Good tenure — owner has built equity and may be ready"),
        ("Owned 5–7 years",                         "+3", "Moderate tenure — early but possible motivation"),
        ("Rate-lock homestead (2020–2022 mortgage)","-6", "Locked in a low rate — strong financial disincentive to sell"),
        ("Homestead exemption, no other flags",    "-12", "Confirmed owner-occupant with no urgency signals"),
        ("Short tenure — under 3 years",           "-18", "Bought recently — very unlikely to sell so soon"),
    ]

    mot_rows = []
    for signal, pts, explanation in mot_signals:
        pts_style = S["pts_pos"] if pts.startswith("+") else S["pts_neg"]
        mot_rows.append([
            Paragraph(signal, S["cell_bold"]),
            Paragraph(pts, pts_style),
            Paragraph(explanation, S["cell"]),
        ])

    mot_tbl = Table(mot_rows, colWidths=[2.0*inch, 0.45*inch, CONTENT_W - 2.45*inch])
    mot_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), RED_LIGHT),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [RED_LIGHT, HexColor("#FFF5F5")]),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LINEBELOW",    (0,0), (-1,-1), 0.3, BORDER),
        ("BOX",          (0,0), (-1,-1), 0.5, RED),
    ]))
    story.append(mot_tbl)

    story.append(Spacer(1, 14))

    # ── FIT ───────────────────────────────────────────────────────────────────
    story.append(Paragraph("🎯  FIT SCORE  (25% of final score)", S["h2"]))
    story.append(Paragraph(
        "This score asks: <b>is this even the right kind of property for you to list?</b> "
        "A motivated seller who owns a commercial warehouse in Marietta is not your "
        "client. Fit makes sure you're only looking at residential homes in your target "
        "counties at the right price points.",
        S["body"]))
    story.append(Spacer(1, 6))

    fit_signals = [
        ("Target geography (North Fulton or Forsyth)", "+12", "In your service area — Alpharetta, Milton, Johns Creek, Roswell, Sandy Springs, or Forsyth County"),
        ("Single family residential home",             "+8",  "The strongest fit — detached SFR is your core listing type"),
        ("2005–2020 build year",                       "+6",  "Prime retail-buyer lifecycle band for North Fulton / South Forsyth — newer layouts buyers want"),
        ("2021+ or 1995–2004 build year",              "+4",  "Modern or established inventory with broad retail buyer appeal"),
        ("Prime submarket price band",                 "+4",  "Price sits in the city's sweet-spot band (sweet-spot / stretch / luxury, per submarket)"),
        ("Pre-1985 build year",                        "−1",  "Older systems/layouts can narrow the retail buyer pool (no longer rewarded)"),
        ("Premium school zone (CCRPI ≥ 92)",           "+3",  "Top school zone adds significant buyer demand and faster sales"),
        ("High-income census tract (≥$180K income)",  "+2",  "Affluent neighborhood — strong buyer pool"),
        ("Premium tract home values (≥$650K median)", "+2",  "Area already commands high prices — supports premium listing"),
        ("Townhouse or condo",                         "+6",  "Attached residential — still a solid listing, slightly less than SFR"),
        ("Good amenity access (grocery, parks)",       "+1–2","Walkable amenities make the listing more appealing"),
        ("Major highway within 150 meters",            "−3",  "Noise and traffic exposure — a known listing challenge"),
        ("Value under $200,000",                       "−8",  "Below minimum GCI threshold — not worth pursuing"),
        ("Commercial / industrial / non-residential",  "−20", "Not a listing type for a residential realtor"),
        ("Outside target geography",                  "−18", "Outside your counties — automatic disqualification"),
        ("Institutional entity owner (REIT, bank, builder)", "−15", "Large corporations don't list with individual agents"),
    ]

    fit_rows = []
    for signal, pts, explanation in fit_signals:
        pts_style = S["pts_pos"] if pts.startswith("+") else S["pts_neg"]
        fit_rows.append([
            Paragraph(signal, S["cell_bold"]),
            Paragraph(pts, pts_style),
            Paragraph(explanation, S["cell"]),
        ])

    fit_tbl = Table(fit_rows, colWidths=[2.1*inch, 0.45*inch, CONTENT_W - 2.55*inch])
    fit_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [BLUE_LIGHT, HexColor("#F8FAFF")]),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LINEBELOW",    (0,0), (-1,-1), 0.3, BORDER),
        ("BOX",          (0,0), (-1,-1), 0.5, BLUE),
    ]))
    story.append(fit_tbl)

    story.append(Spacer(1, 14))

    # ── CONFIDENCE ────────────────────────────────────────────────────────────
    story.append(Paragraph("✅  CONFIDENCE SCORE  (15% of final score)", S["h2"]))
    story.append(Paragraph(
        "This score starts at <b>72 out of 100 by default</b> — because MLS data "
        "and public county records are already pretty reliable. Confidence doesn't "
        "measure whether an owner wants to sell; it measures <b>how trustworthy "
        "our information is.</b> Think of it like the difference between a rumor "
        "and a verified fact.",
        S["body"]))
    story.append(Spacer(1, 6))

    conf_signals = [
        ("Homestead status verified in records",    "+3", "County confirmed this owner filed for homestead — strong data"),
        ("Target city confirmed in FMLS data",      "+2", "Address verified in your core market"),
        ("Senior exemption on county record",       "+2", "County confirmed the filing — not just an assumption"),
        ("Fulton County HPI growth ≥ 20% (year)",  "+2", "Strong appreciation confirmed by Federal Reserve data"),
        ("Fulton County HPI growth ≥ 10% (year)",  "+1", "Positive market appreciation confirmed"),
        ("Atlanta unemployment ≤ 3.5%",            "+1", "Stable job market — confident buyers in the area"),
        ("Atlanta unemployment ≥ 5.0%",            "+3", "Stressed job market may accelerate seller decisions"),
    ]

    conf_rows = []
    for signal, pts, explanation in conf_signals:
        pts_style = S["pts_pos"] if pts.startswith("+") else S["pts_neg"]
        conf_rows.append([
            Paragraph(signal, S["cell_bold"]),
            Paragraph(pts, pts_style),
            Paragraph(explanation, S["cell"]),
        ])

    conf_tbl = Table(conf_rows, colWidths=[2.1*inch, 0.45*inch, CONTENT_W - 2.55*inch])
    conf_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [GREEN_LIGHT, HexColor("#F8FFFC")]),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LINEBELOW",    (0,0), (-1,-1), 0.3, BORDER),
        ("BOX",          (0,0), (-1,-1), 0.5, GREEN),
    ]))
    story.append(conf_tbl)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — THE MATH
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("4", "The Math — Step by Step", GREEN))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Here's the exact calculation the system performs for every single property. "
        "You don't need to do this yourself — the platform handles it automatically "
        "— but understanding the math helps you trust the results.",
        S["body"]))
    story.append(Spacer(1, 10))

    # Step 1
    story.append(Paragraph("Step 1 — Collect the Raw Points", S["h2"]))
    story.append(Paragraph(
        "The system goes through every signal in Section 3 and adds up the points "
        "for each dimension separately. Let's call these the <b>raw scores</b>: "
        "motivation_raw, fit_raw, and confidence_raw.",
        S["body"]))
    story.append(Spacer(1, 6))

    # Step 2
    story.append(Paragraph("Step 2 — Convert Raw Points to a 0–100 Scale", S["h2"]))
    story.append(Paragraph(
        "Raw points are converted to a 0–100 scale using three formulas. "
        "Each formula has a different <b>starting point</b> and a different <b>multiplier</b>:",
        S["body"]))
    story.append(Spacer(1, 6))

    formulas = [
        (RED,   "🔥 Motivation Score", "100 / (1 + e^(−0.076 × (motivation_raw − 11.1)))",
         "A logistic (S-shaped) curve. One strong signal lands around 55–65; stacked "
         "signals climb toward ~95 without everyone pinning at 100. This lets the top "
         "leads be ranked against each other instead of all looking identical."),
        (BLUE,  "🎯 Fit Score",        "100 / (1 + e^(−0.11 × (fit_raw − 20)))",
         "Also logistic. The old linear formula saturated at 100 for any ordinary "
         "target-market home, so good and excellent listings looked the same. The curve "
         "spreads adequate, good, and excellent listings apart so ranking stays useful."),
        (GREEN, "✅ Confidence Score", "72 + (confidence_raw × 4)",
         "Starts at 72 — already high because MLS data is reliable. Every raw point "
         "is worth 4 final points. Confirmed homestead (+3) and HPI growth (+2) = "
         "5 raw → 72 + (5 × 4) = <b>92</b>."),
    ]

    for color, label, formula, explanation in formulas:
        formula_data = [[
            Paragraph(label, ParagraphStyle("fl", fontName="Helvetica-Bold",
                fontSize=11, textColor=color, leading=14)),
            Paragraph(formula, ParagraphStyle("ff", fontName="Courier-Bold",
                fontSize=11, textColor=NAVY, leading=14)),
        ]]
        f_tbl = Table(formula_data, colWidths=[2.2*inch, CONTENT_W - 2.2*inch])
        f_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), GRAY_LIGHT),
            ("TOPPADDING",   (0,0),(-1,-1), 7),
            ("BOTTOMPADDING",(0,0),(-1,-1), 7),
            ("LEFTPADDING",  (0,0),(-1,-1), 10),
            ("LINEABOVE",    (0,0),(-1,0),  1, color),
        ]))
        story.append(f_tbl)
        story.append(Paragraph(explanation, S["body_small"]))
        story.append(Spacer(1, 6))

    story.append(Paragraph(
        "<b>All three scores are clamped to the 0–100 range.</b> "
        "If the math produces a number above 100, it's set to 100. "
        "If it goes below 0, it's set to 0.",
        S["note_box"]))

    story.append(Spacer(1, 10))

    # Step 3
    story.append(Paragraph("Step 3 — Blend the Three Scores", S["h2"]))
    story.append(Paragraph(
        "The three scores are combined into one final blended score using a weighted average:",
        S["body"]))
    story.append(Spacer(1, 6))

    blend_data = [[
        Paragraph("Final Score  =", ParagraphStyle("bl", fontName="Helvetica-Bold",
            fontSize=12, textColor=NAVY, leading=16)),
        Paragraph("(Motivation × 0.60)  +  (Fit × 0.25)  +  (Confidence × 0.15)",
            ParagraphStyle("bf", fontName="Courier-Bold", fontSize=11, textColor=NAVY, leading=16)),
    ]]
    blend_tbl = Table(blend_data, colWidths=[1.4*inch, CONTENT_W - 1.4*inch])
    blend_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), BLUE_LIGHT),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("BOX",          (0,0),(-1,-1), 1.5, BLUE),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(blend_tbl)
    story.append(Spacer(1, 8))

    # Worked example
    story.append(Paragraph("Worked Example — A Real Lead", S["h3"]))
    story.append(Paragraph(
        "Imagine a property in Alpharetta. The owner bought it 18 years ago, "
        "lives in Florida, owns it free and clear, and the deed shows a living trust. "
        "There's a Publix 0.8 miles away and the school zone scores 94 on CCRPI. "
        "Here's what the math looks like:",
        S["body_small"]))
    story.append(Spacer(1, 5))

    example_data = [
        ["Signal", "Dimension", "Raw Points"],
        ["Out-of-state owner (Florida)",       "Motivation", "+14"],
        ["Owned 18 years",                     "Motivation", "+10"],
        ["Free and clear",                     "Motivation", "+15"],
        ["Trust name + OOS + 15+ yr (2 of 4)","Motivation", "+18"],
        ["Target city (Alpharetta)",           "Fit",        "+12"],
        ["Single family residential",          "Fit",        "+8"],
        ["Within Alpharetta price ceiling",    "Fit",        "+4"],
        ["1998 build year (renovation cycle)", "Fit",        "+5"],
        ["School zone CCRPI 94",               "Fit",        "+3"],
        ["Grocery within 1 mile",              "Fit",        "+1"],
        ["City confirmed in FMLS",             "Confidence", "+2"],
        ["", "", ""],
        ["motivation_raw = 57  →  30 + (57 × 2.4) = 30 + 136.8  →  capped at 100", "", ""],
        ["fit_raw = 33  →  45 + (33 × 2.1) = 45 + 69.3  →  114.3  →  capped at 100",  "", ""],
        ["confidence_raw = 2  →  72 + (2 × 4) = 80", "", ""],
        ["Final = (100 × 0.60) + (100 × 0.25) + (80 × 0.15) = 60 + 25 + 12 = 97  →  HOT 🔥", "", ""],
    ]

    ex_tbl = Table(example_data, colWidths=[3.0*inch, 1.2*inch, 1.2*inch])
    ex_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), NAVY),
        ("TEXTCOLOR",    (0,0),(-1,0), white),
        ("FONTNAME",     (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),(-1,0), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,11), [GRAY_LIGHT, white]),
        ("BACKGROUND",   (0,12),(-1,12), HexColor("#F9FAFB")),
        ("BACKGROUND",   (0,13),(-1,-1), BLUE_LIGHT),
        ("FONTNAME",     (0,13),(-1,-1), "Courier"),
        ("FONTSIZE",     (0,13),(-1,-1), 8.5),
        ("SPAN",         (0,12),(-1,12)),
        ("SPAN",         (0,13),(-1,13)),
        ("SPAN",         (0,14),(-1,14)),
        ("SPAN",         (0,15),(-1,15)),
        ("SPAN",         (0,16),(-1,16)),
        ("FONTNAME",     (0,16),(-1,16), "Courier-Bold"),
        ("TEXTCOLOR",    (0,16),(-1,16), NAVY),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("BOX",          (0,0),(-1,-1), 0.5, BORDER),
        ("LINEBELOW",    (0,0),(-1,-2), 0.3, BORDER),
        ("ALIGN",        (2,0),(-1,-1), "CENTER"),
    ]))
    story.append(ex_tbl)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — HARD CAPS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("5", "Hard Caps — Automatic Disqualifiers", RED))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Some situations are automatic <b>no</b> — no matter how good the other signals "
        "are. Think of these like eligibility rules in a sport: it doesn't matter how "
        "talented a player is, if they're not eligible, they can't play. "
        "These hard caps lock the final score at 39 or below, which means the lead "
        "is automatically discarded as PASS.",
        S["body"]))
    story.append(Spacer(1, 8))

    caps = [
        ("Outside target geography",
         "The property is not in North Fulton (Alpharetta, Milton, Johns Creek, Roswell, Sandy Springs) "
         "or Forsyth County. Hard cap → 39."),
        ("Commercial or industrial property type",
         "Offices, warehouses, retail stores, hotels, churches — not a residential listing. "
         "Hard cap → 39."),
        ("Value under $200,000",
         "Below the minimum price threshold for your target market. "
         "The commission would not justify the effort. Hard cap → 39."),
        ("Institutional entity owner",
         "A REIT, bank, mortgage company, builder, developer, or any entity owning more "
         "than 10 properties. These owners don't work with individual listing agents. Hard cap → 39."),
        ("No seller motivation signals at all",
         "If the system finds zero positive motivation signals and the motivation raw score "
         "is 5 or below, the score is capped at 38 — just below the COOL tier cutoff."),
        ("Out-of-state absentee, but tenure under 10 years",
         "An absentee owner who hasn't owned long enough to have accumulated strong motivation "
         "gets a softer cap at 54 — which keeps them out of the HOT tier until more evidence builds."),
    ]

    for trigger, desc in caps:
        cap_data = [[
            Paragraph(f"⛔  {trigger}", ParagraphStyle("ct", fontName="Helvetica-Bold",
                fontSize=10.5, textColor=RED, leading=14)),
        ], [
            Paragraph(desc, S["body_small"]),
        ]]
        cap_tbl = Table(cap_data, colWidths=[CONTENT_W])
        cap_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0), RED_LIGHT),
            ("BACKGROUND",   (0,1),(-1,1), HexColor("#FFFAFA")),
            ("TOPPADDING",   (0,0),(-1,-1), 7),
            ("BOTTOMPADDING",(0,0),(-1,-1), 7),
            ("LEFTPADDING",  (0,0),(-1,-1), 12),
            ("BOX",          (0,0),(-1,-1), 0.5, HexColor("#FCA5A5")),
            ("LINEBELOW",    (0,0),(0,0), 0.3, HexColor("#FCA5A5")),
        ]))
        story.append(cap_tbl)
        story.append(Spacer(1, 5))

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6 — TIERS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("6", "The Four Tiers — What Your Score Means", NAVY))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Once the blended score is calculated (and capped if needed), the lead "
        "falls into one of four tiers. Only HOT, WARM, and COOL leads appear "
        "in your results — PASS leads are automatically discarded.",
        S["body"]))
    story.append(Spacer(1, 10))

    tier_data = [[
        [Paragraph("≥ 70", S["tier_score"]), Paragraph("HOT 🔥", S["tier_name"])],
        [Paragraph("≥ 55", S["tier_score"]), Paragraph("WARM", S["tier_name"])],
        [Paragraph("≥ 40", S["tier_score"]), Paragraph("COOL", S["tier_name"])],
        [Paragraph("< 40", S["tier_score"]), Paragraph("PASS", S["tier_name"])],
    ]]

    tier_colors = [RED, AMBER, BLUE, GRAY]
    tier_descriptions = [
        "Multiple strong motivation signals confirmed. Call these owners first — "
        "urgency indicators like distress, estate, or long-tenure absentee are present.",
        "Good motivation with solid property fit. Worth a direct mail campaign or "
        "a personal outreach call in the near term.",
        "Some positive signals but not enough to prioritize. Good for a nurture "
        "campaign — reconnect in 6–12 months.",
        "Does not meet minimum criteria. Outside geography, wrong property type, "
        "recent buyer, or institutional owner. Automatically removed from results.",
    ]

    tier_display = []
    for i, (score_p, name_p) in enumerate(tier_data[0]):
        col_data = [
            [score_p],
            [name_p],
        ]
        col_tbl = Table(col_data, colWidths=[1.4*inch])
        col_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), tier_colors[i]),
            ("TOPPADDING",   (0,0),(-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("ALIGN",        (0,0),(-1,-1), "CENTER"),
        ]))
        tier_display.append(col_tbl)

    # Lay them out in a single-row table
    tier_row = Table([tier_display], colWidths=[CONTENT_W/4]*4)
    tier_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    story.append(tier_row)
    story.append(Spacer(1, 8))

    desc_rows = [[Paragraph(d, S["body_small"]) for d in tier_descriptions]]
    desc_tbl = Table(desc_rows, colWidths=[CONTENT_W/4]*4)
    desc_tbl.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ("RIGHTPADDING", (0,0),(-1,-1), 6),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [HexColor("#FAFAFA")]),
        ("LINEBELOW",    (0,0),(-1,-1), 0.5, BORDER),
        ("BOX",          (0,0),(-1,-1), 0.5, BORDER),
    ]))
    story.append(desc_tbl)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7 — STRATEGY LABELS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(SectionBanner("7", "Outreach Strategy — What to Do With Each Lead", PURPLE))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Every lead that passes the PASS filter also gets an <b>outreach strategy label</b> "
        "— a plain-English action description based on which flags fired. Compound situations "
        "(two high-urgency flags together) get the most urgent labels:",
        S["body"]))
    story.append(Spacer(1, 8))

    strategies = [
        ("🔴  Estate + Distress flags both fire",
         "Estate in distress — highest urgency listing",
         "An estate or probate situation AND the owner is behind on taxes or in foreclosure. "
         "This is the highest-urgency lead possible — the estate needs to sell quickly."),
        ("🔴  Estate + Out-of-State flags both fire",
         "Estate + absentee — call today",
         "A probate or estate property owned by someone out of state. "
         "The family is managing the estate remotely — they want this resolved."),
        ("🔴  Distress + Out-of-State flags both fire",
         "Distressed absentee — urgent outreach",
         "Tax or foreclosure distress on a property the owner doesn't live in. "
         "Maximum motivation to sell."),
        ("🟡  Estate / probate flag only",
         "Estate transition — listing opportunity",
         "The owner name shows ESTATE, HEIRS, or EXECUTOR. "
         "Property needs to be sold as part of estate settlement."),
        ("🟡  Tax or foreclosure flag only",
         "Motivated seller — timeline pressure",
         "Financial pressure is building. Owner needs to sell before the situation escalates."),
        ("🟡  Mom-and-Pop landlord flag",
         "Portfolio exit — listing conversion",
         "Individual owner with 2–5 properties. Many small landlords eventually want to "
         "cash out. Position yourself as their listing agent for the whole portfolio."),
        ("🟡  Absentee owner (OOS or in-state)",
         "Absentee owner — listing outreach",
         "Owner doesn't live in the home. No emotional attachment. "
         "Easier conversation to have than with an owner-occupant."),
        ("🟢  Empty-nest flag (3+ bedrooms, 20+ years)",
         "Empty-nest downsizer — listing opportunity",
         "Big house, long tenure, kids are likely grown. "
         "Classic move-down conversation."),
        ("🟢  Free and clear or high-equity flag",
         "Equity-rich seller — strong listing position",
         "Owner has built up significant wealth in the home. "
         "They can price confidently and net a large check."),
        ("🟢  Premium school zone flag",
         "Premium school zone — fast-sale listing",
         "Top-rated school zone drives fast sales and strong buyer competition. "
         "Strong marketing angle for the listing presentation."),
        ("🟢  Senior exemption flag",
         "Senior downsizer — listing opportunity",
         "County-confirmed senior owner. Often considering a move to a smaller home, "
         "retirement community, or closer to family."),
    ]

    for trigger, label, explanation in strategies:
        strat_data = [
            [Paragraph(trigger, S["strat_trigger"]),
             Paragraph(f'"{label}"', ParagraphStyle("sl", fontName="Helvetica-BoldOblique",
                fontSize=9.5, textColor=NAVY, leading=13))],
            [Paragraph("", S["body_small"]),
             Paragraph(explanation, S["body_small"])],
        ]
        strat_tbl = Table(strat_data, colWidths=[2.0*inch, CONTENT_W - 2.0*inch])
        strat_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), GRAY_LIGHT),
            ("BACKGROUND",   (0,0),(0,-1),  HexColor("#F0F4FF")),
            ("TOPPADDING",   (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",  (0,0),(-1,-1), 8),
            ("VALIGN",       (0,0),(-1,-1), "TOP"),
            ("LINEBELOW",    (0,0),(-1,-1), 0.4, BORDER),
        ]))
        story.append(strat_tbl)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width=CONTENT_W, color=BORDER))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Quick Reference: The Complete Formula", S["h2"]))
    story.append(Spacer(1, 6))

    summary_lines = [
        "motivation_score  =  100 / (1 + e^(−0.076 × (motivation_raw − 11.1)))   ← logistic",
        "fit_score         =  100 / (1 + e^(−0.11 × (fit_raw − 20)))             ← logistic",
        "confidence_score  =  clamp( 72 + confidence_raw × 4,      0, 100 )",
        "",
        "blended  =  (motivation_score × 0.60) + (fit_score × 0.25) + (confidence_score × 0.15)",
        "final    =  min( blended,  score_cap )   ← capped by any hard disqualifiers",
        "",
        "HOT ≥ 70  |  WARM ≥ 55  |  COOL ≥ 40  |  REVIEW (intent unknown)  |  PASS < 40",
        "HOT also requires independent intent evidence (the HOT evidence gate).",
        "COMPLIANCE_HOLD = already-listed owners — never solicited (NAR Art. 16).",
    ]

    formula_block = Table(
        [[Paragraph(line, ParagraphStyle("fb", fontName="Courier", fontSize=9,
            textColor=NAVY if line else NAVY, leading=14))]
         for line in summary_lines],
        colWidths=[CONTENT_W]
    )
    formula_block.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), BLUE_LIGHT),
        ("TOPPADDING",   (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("BOX",          (0,0),(-1,-1), 1, BLUE),
    ]))
    story.append(formula_block)

    doc.build(story)
    print(f"PDF saved to: {out_path}")
    return out_path


if __name__ == "__main__":
    build()
