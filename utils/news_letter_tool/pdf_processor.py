#!/usr/bin/env python3
"""
ASX Announcement PDF Summarizer
Downloads authenticated PDFs, extracts text with PyMuPDF, and generates structured summaries using OpenAI API
"""

import os
import warnings
import requests
from typing import Optional, List
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

# Suppress PyMuPDF SWIG deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='importlib._bootstrap')
warnings.filterwarnings('ignore', message='builtin type.*has no __module__ attribute')

import fitz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# API Configuration from environment
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUT
# ============================================================================

class KeyEntity(BaseModel):
    """Important entity extracted from announcement"""
    entity_type: str = Field(description="Type of entity: company, person, commodity, location, drug, technology")
    name: str = Field(description="Name of the entity")
    context: str = Field(description="Brief context about this entity in the announcement")


class FinancialDetail(BaseModel):
    """Financial information extracted"""
    amount: str = Field(description="Dollar amount or percentage (e.g., '$2.2M', '5.02%', 'USD5.8B')")
    currency: Optional[str] = Field(default="AUD", description="Currency code")
    context: str = Field(description="What this amount relates to (e.g., 'R&D tax incentive', 'stake acquisition')")


class AnnouncementSummary(BaseModel):
    """Structured summary of ASX announcement following Jason's style requirements"""

    summary: str = Field(
        description=(
            "Concise 30-word maximum summary in Jason's newsletter style. "
            "MUST include: **company names in bold**, dollar amounts, important numbers, "
            "and the commodity/underlying asset. Write in active voice, information-dense format. "
            "Example: '**Control Bionics** secures permission from **Apple** to integrate its NeuroNode "
            "technology with Apple's Brain Computer Interface Protocol.'"
        )
    )

    key_entities: List[KeyEntity] = Field(
        description="List of important entities mentioned (companies, people, commodities, technologies)"
    )

    financial_details: List[FinancialDetail] = Field(
        description="List of financial amounts, percentages, or stakes mentioned"
    )

    announcement_type: str = Field(
        description=(
            "Category of announcement: partnership, acquisition, funding, clinical_trial, "
            "regulatory, shareholder_update, technology, product_launch, financial_results, or other"
        )
    )

    priority_score: int = Field(
        description=(
            "Priority score 1-10 based on importance. High priority (8-10): major partnerships, "
            "large funding, clinical trial results, regulatory approvals. Medium (5-7): smaller deals, "
            "updates. Low (1-4): administrative, routine updates."
        )
    )

    key_takeaway: str = Field(
        description=(
            "Single sentence capturing the most important insight for investors. "
            "Focus on: Why does this matter? What changed? What's the impact?"
        )
    )


# ============================================================================
# SYSTEM PROMPT FOR AI SUMMARIZATION
# ============================================================================

SYSTEM_PROMPT = """
You are an expert financial analyst specializing in ASX healthcare and biotech announcements for Jason's daily newsletter.

Your job is to analyze company announcements and create ultra-concise, information-dense summaries that help investors quickly understand what matters.

**STRICT REQUIREMENTS FOR SUMMARY:**

1. **Length**: Maximum 30 words. Every word must count.

2. **Format**:
   - Use **bold** for ALL company names (e.g., **Control Bionics**, **Apple**)
   - Include ALL dollar amounts, percentages, and important numbers
   - CRITICAL: Include the specific commodity, drug, technology, product, or underlying asset being discussed (e.g., "THC beverages", "NeuroNode technology", "heavy rare earth oxides")
   - Use markdown formatting

3. **Content Priority** (what to include):
   - Company names involved (all parties in bold)
   - Dollar amounts with proper units ($2.2M, USD5.8B, etc.)
   - **CRITICAL - Commodity/Asset**: Always identify and include the commodity, product, technology, or underlying asset being discussed. This is REQUIRED per client specifications. Examples: "THC beverages", "diagnostic services", "NeuroNode technology", "heavy rare earth oxides", "clinical trials for drug X"
   - Key action/event (secured, acquires, expands, receives, etc.)
   - Important percentages or stakes (e.g., "5.02% stake")
   - Geographic locations if relevant (Brisbane, Missouri, etc.)
   - Broker names for financial transactions (e.g., **Evans & Partners**, **Macquarie**)

4. **Price Range Handling** (CRITICAL):
   - When multiple transaction prices exist (e.g., buybacks, trades with different prices), ALWAYS specify the range: "at prices between $X-$Y" or "ranging $X-$Y"
   - NEVER use "at $X each" if there's a price range - this implies a single price
   - Only use "at $X" when there is genuinely ONE price for all transactions
   - Example WRONG: "buys back 200,000 shares at AUD 2.73 each" (when prices ranged 2.67-2.73)
   - Example CORRECT: "buys back 200,000 shares for AUD 539,640 at prices between AUD 2.67-2.73"

5. **Style Guidelines**:
   - Active voice only
   - Present tense for recent events
   - No fluff or filler words
   - Maximum information density
   - Match the tone of financial news (professional but accessible)

6. **Examples of GOOD summaries** (study these closely):
   - "**IonicRE** signed non-binding MOU with **US Strategic Metals** to deploy magnet recycling technology at fully permitted **Missouri** site producing **NdPr** and **heavy rare earth oxides**."
   - "**Control Bionics** secures permission from **Apple** to integrate its NeuroNode technology with Apple's Brain Computer Interface Protocol."
   - "**Proteomics** receives $2.2M in R&D tax incentives."
   - "Top 20 shareholder **Paul Ehrlich** moved to substantial on **CQL** with 5.02% stake."
   - "**SoftBank** offloads USD5.8B **Nvidia** stake to fund **OpenAI** and Stargate AI initiatives."
   - "**Australian Clinical Labs** buys back 200,000 shares for AUD 539,640 at prices between AUD 2.67-2.73 via **Evans & Partners**."

7. **Priority Scoring**:
   - 9-10: Major partnerships, large funding rounds (>$10M), significant clinical trial results, regulatory approvals
   - 7-8: Medium partnerships/deals, notable shareholder moves, technology agreements
   - 5-6: Smaller funding, updates on existing projects, minor announcements
   - 3-4: Administrative updates, routine compliance
   - 1-2: Boilerplate, presentations, minor admin

**IMPORTANT**: Extract ALL relevant financial numbers, entity names, technical terms, and especially the commodity/product/technology being discussed. The summary must be complete enough that Jason can publish it directly or add minimal commentary.
"""


# ============================================================================
# PDF PROCESSING FUNCTIONS
# ============================================================================

def download_pdf(pdf_url: str, username: str, password: str, verbose: bool = False) -> Optional[bytes]:
    """
    Download PDF from authenticated QuoteAPI endpoint

    Args:
        pdf_url: Full URL to the PDF
        username: QuoteAPI username
        password: QuoteAPI password
        verbose: If True, print progress messages

    Returns:
        PDF content as bytes, or None if download failed
    """
    try:
        session = requests.Session()
        session.auth = (username, password)
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/pdf'
        })

        response = session.get(pdf_url, timeout=30)
        response.raise_for_status()

        if response.status_code == 200:
            return response.content
        return None

    except Exception as e:
        if verbose:
            print(f"❌ Error downloading PDF: {e}")
        return None


def extract_text_from_pdf(pdf_bytes: bytes, verbose: bool = False) -> str:
    """
    Extract text from PDF using PyMuPDF (fitz)

    Args:
        pdf_bytes: PDF file content as bytes
        verbose: If True, print progress messages

    Returns:
        Extracted text as string
    """
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_content = []

        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            text = page.get_text()
            text_content.append(text)

        pdf_document.close()
        full_text = "\n\n".join(text_content).strip()
        return full_text

    except Exception as e:
        if verbose:
            print(f"❌ Error extracting text from PDF: {e}")
        return ""


# ============================================================================
# OPENAI STRUCTURED OUTPUT FUNCTION
# ============================================================================

def generate_structured_summary(
    extracted_text: str,
    announcement_title: str,
    company_code: str,
    openai_api_key: str,
    model: str = "gpt-5.1",
    verbose: bool = False
) -> Optional[AnnouncementSummary]:
    """
    Generate structured summary using OpenAI's Response API with Pydantic models

    Args:
        extracted_text: Text extracted from PDF
        announcement_title: Title of the announcement
        company_code: ASX stock code
        openai_api_key: OpenAI API key
        model: OpenAI model to use
        verbose: If True, print progress messages

    Returns:
        AnnouncementSummary object or None if generation failed
    """
    try:
        client = OpenAI(api_key=openai_api_key)

        user_prompt = f"""Analyze this ASX announcement and create a structured summary.

        **Company Code**: {company_code}
        **Announcement Title**: {announcement_title}

        **Full Announcement Text**:
        {extracted_text[:8000]}

        Generate a comprehensive structured summary following all the requirements."""

        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            text_format=AnnouncementSummary,
            reasoning={"effort": "medium"}
        )

        summary = response.output_parsed
        return summary

    except Exception as e:
        if verbose:
            print(f"❌ Error generating summary: {e}")
        return None


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_announcement_pdf(
    pdf_url: str,
    announcement_title: str = "Unknown Announcement",
    company_code: str = "UNKNOWN",
    verbose: bool = False
) -> Optional[AnnouncementSummary]:
    """
    Complete pipeline: Download PDF -> Extract Text -> Generate Structured Summary

    Args:
        pdf_url: URL to the PDF announcement
        announcement_title: Title of the announcement
        company_code: ASX stock code
        verbose: If True, print progress messages

    Returns:
        AnnouncementSummary object or None if processing failed
    """
    # Get credentials from environment
    username = os.getenv('QUOTEAPI_USERNAME')
    password = os.getenv('QUOTEAPI_PASSWORD')
    openai_api_key = os.getenv('OPENAI_API_KEY')

    if not openai_api_key:
        logger.error("❌ OPENAI_API_KEY not found in environment variables!")
        return None

    # Download PDF
    logger.info(f"Downloading PDF from {pdf_url}...")
    pdf_bytes = download_pdf(pdf_url, username, password, verbose)
    if not pdf_bytes:
        logger.error("Failed to download PDF. Aborting.")
        return None

    # Extract text
    logger.info(f"Extracting text from PDF...")
    extracted_text = extract_text_from_pdf(pdf_bytes, verbose)
    if not extracted_text or len(extracted_text) < 50:
        logger.error("Failed to extract text from PDF. Aborting.")
        return None
    # Generate summary
    logger.info(f"Generating structured summary...")
    summary = generate_structured_summary(
        extracted_text=extracted_text,
        announcement_title=announcement_title,
        company_code=company_code,
        openai_api_key=openai_api_key,
        verbose=verbose
    )
    logger.info(f"Structured summary generated successfully")

    return summary


def print_summary_report(summary: AnnouncementSummary, company_code: str):
    """Pretty print the structured summary"""
    print("\n" + "=" * 80)
    print("📊 STRUCTURED SUMMARY REPORT")
    print("=" * 80)

    print(f"\n🏢 Company: {company_code}")
    print(f"📁 Type: {summary.announcement_type}")
    print(f"⭐ Priority: {summary.priority_score}/10")

    print(f"\n📝 SUMMARY (30-word max):")
    print(f"   {summary.summary}")

    print(f"\n💡 KEY TAKEAWAY:")
    print(f"   {summary.key_takeaway}")

    if summary.financial_details:
        print(f"\n💰 FINANCIAL DETAILS:")
        for detail in summary.financial_details:
            print(f"   • {detail.amount} ({detail.currency}): {detail.context}")

    if summary.key_entities:
        print(f"\n🔑 KEY ENTITIES:")
        for entity in summary.key_entities:
            print(f"   • {entity.name} ({entity.entity_type}): {entity.context}")

    print("\n" + "=" * 80)


# ============================================================================
# MAIN FUNCTION FOR TESTING
# ============================================================================

def main():
    """Test the PDF summarizer with a sample announcement"""

    # Example: You can provide a PDF URL from an ASX announcement
    # Format: https://quoteapi.com/files/stocksdigital/announcements/{code}.asx/{fileId}.pdf

    print("🧪 ASX PDF Summarizer - Test Mode")
    print("=" * 80)

    # Example usage (replace with actual announcement)
    pdf_url = input("\nEnter PDF URL (or press Enter for demo): ").strip()

    if not pdf_url:
        print("\n💡 No URL provided. Please provide a PDF URL from QuoteAPI.")
        print("Example format: https://quoteapi.com/files/stocksdigital/announcements/cbl.asx/12345.pdf")
        return

    company_code = input("Enter company code (e.g., CBL): ").strip().upper()
    announcement_title = input("Enter announcement title: ").strip()

    # Process the announcement
    summary = process_announcement_pdf(
        pdf_url=pdf_url,
        announcement_title=announcement_title,
        company_code=company_code
    )

    if summary:
        print_summary_report(summary, company_code)
        print("\n✅ Processing completed successfully!")
    else:
        print("\n❌ Processing failed!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
