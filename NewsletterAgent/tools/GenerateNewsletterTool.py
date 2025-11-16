#!/usr/bin/env python3
"""
GenerateNewsletterTool
Processes ASX healthcare announcements and generates structured newsletter summaries.
"""

from typing import Optional, List
from enum import Enum
from pydantic import Field, model_validator
from agency_swarm.tools import BaseTool
from utils.news_letter_tool.asx_fetcher import fetch_announcements, group_healthcare_announcements
from utils.news_letter_tool.pdf_processor import process_announcement_pdf
from utils.news_letter_tool.healthcare_stocks import HEALTHCARE_STOCKS
from datetime import datetime


class Action(str, Enum):
    """Available actions for the newsletter tool"""
    LIST_STOCKS = "list_stocks"
    GENERATE_NEWSLETTER = "generate_newsletter"


class GenerateNewsletterTool(BaseTool):
    """
    Generates ASX healthcare newsletter by processing PDF announcements.

    Actions:
    - list_stocks: Show all available healthcare stock codes
    - generate_newsletter: Process announcements and generate newsletter
    """

    action: Action = Field(
        default=Action.GENERATE_NEWSLETTER,
        description="Action to perform: 'list_stocks' to show available codes, 'generate_newsletter' to create newsletter"
    )

    stock_codes: Optional[List[str]] = Field(
        default=None,
        description="List of stock codes to process (e.g., ['ACL', 'AGH']). If None, processes all healthcare stocks."
    )

    pdf_limit: Optional[int] = Field(
        default=None,
        description="Maximum number of PDFs to process. If None, processes all announcements."
    )

    min_priority_score: int = Field(
        default=1,
        description="Minimum priority score (1-10) to include in results."
    )

    @model_validator(mode='after')
    def validate_all_fields(self):
        """Validate and normalize all fields in a single validator"""

        # 1. Normalize stock codes to uppercase
        if self.stock_codes is not None:
            self.stock_codes = [code.upper() for code in self.stock_codes]

        # 2. Validate pdf_limit is positive
        if self.pdf_limit is not None and self.pdf_limit <= 0:
            raise ValueError("pdf_limit must be a positive integer")

        # 3. Validate priority score range
        if not 1 <= self.min_priority_score <= 10:
            raise ValueError("min_priority_score must be between 1 and 10")

        # 4. Validate stock codes exist in healthcare database
        if self.action == Action.GENERATE_NEWSLETTER and self.stock_codes:
            invalid_codes = [code for code in self.stock_codes if code not in HEALTHCARE_STOCKS]
            if invalid_codes:
                valid_codes = [code for code in self.stock_codes if code in HEALTHCARE_STOCKS]
                error_msg = (
                    f"Invalid stock code(s): {', '.join(invalid_codes)}\n"
                    f"Valid codes: {', '.join(valid_codes) if valid_codes else 'None'}\n\n"
                    f"Use action='list_stocks' to see all available healthcare stock codes."
                )
                raise ValueError(error_msg)

        return self

    def run(self) -> str:
        """Execute the requested action."""
        try:
            if self.action == Action.LIST_STOCKS:
                return self._list_stocks()
            else:
                return self._generate_newsletter()

        except Exception as e:
            return f"Error: {str(e)}"

    def _list_stocks(self) -> str:
        """List all available healthcare stock codes."""
        output_lines = [
            "# ASX Healthcare Stock Codes\n",
            f"**Total:** {len(HEALTHCARE_STOCKS)} healthcare companies\n",
            "## Available Stock Codes:\n"
        ]

        # Group by first letter
        codes_by_letter = {}
        for code, name in sorted(HEALTHCARE_STOCKS.items()):
            first_letter = code[0]
            if first_letter not in codes_by_letter:
                codes_by_letter[first_letter] = []
            codes_by_letter[first_letter].append(f"**{code}**: {name}")

        for letter in sorted(codes_by_letter.keys()):
            output_lines.append(f"### {letter}")
            output_lines.extend(codes_by_letter[letter])
            output_lines.append("")

        return "\n".join(output_lines)

    def _generate_newsletter(self) -> str:
        """Generate newsletter from announcements."""
        # Fetch announcements
        announcements = fetch_announcements()
        if not announcements:
            return "No announcements found. The API may be unavailable or there are no announcements today."

        # Filter for healthcare
        healthcare_announcements = group_healthcare_announcements(announcements)
        if not healthcare_announcements:
            return "No healthcare sector announcements found today."

        # Filter by specific stock codes if provided
        if self.stock_codes:
            healthcare_announcements = {
                code: anns for code, anns in healthcare_announcements.items()
                if code in self.stock_codes
            }
            if not healthcare_announcements:
                return f"No announcements found for: {', '.join(self.stock_codes)}"

        # Collect PDFs to process
        pdfs_to_process = self._collect_pdfs(healthcare_announcements)
        if not pdfs_to_process:
            return "No PDFs found to process."

        # Process PDFs and generate summaries
        results = self._process_pdfs(pdfs_to_process)

        # Sort by priority and format output
        results.sort(key=lambda x: x['priority_score'], reverse=True)
        return self._format_output(results, len(pdfs_to_process))

    def _collect_pdfs(self, healthcare_announcements: dict) -> list:
        """Collect PDFs to process from announcements."""
        pdfs_to_process = []

        for code in sorted(healthcare_announcements.keys()):
            for announcement in healthcare_announcements[code]:
                file_id = announcement.get('fileId', '')
                if file_id:
                    pdfs_to_process.append({
                        'code': code,
                        'announcement': announcement
                    })
                if self.pdf_limit and len(pdfs_to_process) >= self.pdf_limit:
                    break
            if self.pdf_limit and len(pdfs_to_process) >= self.pdf_limit:
                break

        return pdfs_to_process

    def _process_pdfs(self, pdfs_to_process: list) -> list:
        """Process each PDF and generate summaries."""
        results = []

        for item in pdfs_to_process:
            code = item['code']
            ann = item['announcement']
            file_id = ann.get('fileId')
            title = ann.get('heading', 'Unknown')
            date_time = ann.get('datetime', 'Unknown')
            pdf_url = f"https://quoteapi.com/files/stocksdigital/announcements/{code.lower()}.asx/{file_id}.pdf"

            summary = process_announcement_pdf(
                pdf_url=pdf_url,
                announcement_title=title,
                company_code=code,
                verbose=False
            )

            if summary and summary.priority_score >= self.min_priority_score:
                results.append({
                    'company_code': code,
                    'title': title,
                    'datetime': date_time,
                    'pdf_url': pdf_url,
                    'summary': summary.summary,
                    'priority_score': summary.priority_score
                })

        return results

    def _format_output(self, results: list, total_processed: int) -> str:
        """Format results into clean markdown output."""
        if not results:
            return "No announcements found matching the criteria."

        output_lines = []
        output_lines.append(f"# ASX Healthcare Newsletter - {datetime.now().strftime('%Y-%m-%d')}\n")
        output_lines.append(f"**Processed:** {total_processed} announcements | **Showing:** {len(results)} results\n")

        for i, result in enumerate(results, 1):
            output_lines.append(f"{i}. {result['summary']} [Announcement: {result['company_code']}]({result['pdf_url']})")

        return "\n".join(output_lines)


if __name__ == "__main__":
    # Test the tool
    print("Test 1: List stocks")
    tool = GenerateNewsletterTool(action=Action.LIST_STOCKS)
    result = tool.run()
    print(result[:300] + "...\n")

    print("Test 2: Generate newsletter with limit")
    tool = GenerateNewsletterTool(action=Action.GENERATE_NEWSLETTER, pdf_limit=2)
    result = tool.run()
    print(result)
