#!/usr/bin/env python3
"""
ASX Healthcare Newsletter Generator
Complete workflow: Fetch announcements → Process PDFs → Generate newsletter
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.fetch_asx_news_today import fetch_announcements, group_healthcare_announcements
from scripts.pdf_summarizer import process_announcement_pdf

# Load environment variables
load_dotenv()


def generate_newsletter(
    max_announcements_per_company: int = 3,
    min_priority_score: int = 1,
    output_json: bool = True,
    output_markdown: bool = True
) -> Dict:
    """
    Complete workflow to generate ASX healthcare newsletter

    Args:
        max_announcements_per_company: Max announcements to process per company
        min_priority_score: Minimum priority score to include (1-10)
        output_json: Save results as JSON
        output_markdown: Save results as Markdown

    Returns:
        Dictionary with all processed results
    """

    print("=" * 80)
    print("🚀 ASX HEALTHCARE NEWSLETTER GENERATOR")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Step 1: Fetch all announcements
    print("\n📡 STEP 1: Fetching ASX announcements...")
    try:
        all_announcements = fetch_announcements()
        print(f"✅ Fetched {len(all_announcements)} total ASX announcements")
    except Exception as e:
        print(f"❌ Error fetching announcements: {e}")
        return {"error": str(e), "results": []}

    # Step 2: Group by healthcare companies
    print("\n🏥 STEP 2: Filtering for healthcare sector...")
    grouped = group_healthcare_announcements(all_announcements)
    total_healthcare = sum(len(v) for v in grouped.values())
    print(f"✅ Found {total_healthcare} healthcare announcements across {len(grouped)} companies")

    if not grouped:
        print("❌ No healthcare announcements found!")
        return {"error": "No healthcare announcements", "results": []}

    # Step 3: Process each PDF one by one
    print("\n📄 STEP 3: Processing PDFs and generating summaries...")
    print(f"Processing up to {max_announcements_per_company} announcement(s) per company")
    print("=" * 80)

    results = []
    processed_count = 0
    failed_count = 0

    for company_code in sorted(grouped.keys()):
        company_announcements = grouped[company_code][:max_announcements_per_company]

        print(f"\n📋 Processing {company_code} ({len(company_announcements)} announcement(s))...")

        for announcement in company_announcements:
            processed_count += 1

            # Extract announcement details
            file_id = announcement.get('fileId', '')
            title = announcement.get('heading', 'Unknown')
            date_time = announcement.get('dateTime', '')

            if not file_id:
                print(f"   ⚠️  Skipping: No fileId for '{title}'")
                failed_count += 1
                continue

            # Build PDF URL
            pdf_url = f"https://quoteapi.com/files/stocksdigital/announcements/{company_code.lower()}.asx/{file_id}.pdf"

            print(f"\n   📄 [{processed_count}] {title[:60]}...")
            print(f"      Time: {date_time}")

            # Process PDF and generate summary
            try:
                summary = process_announcement_pdf(
                    pdf_url=pdf_url,
                    announcement_title=title,
                    company_code=company_code
                )

                if summary:
                    # Check if meets priority threshold
                    if summary.priority_score >= min_priority_score:
                        result = {
                            'company_code': company_code,
                            'title': title,
                            'date_time': date_time,
                            'pdf_url': pdf_url,
                            'file_id': file_id,
                            'summary': summary.summary,
                            'priority_score': summary.priority_score,
                            'announcement_type': summary.announcement_type,
                            'key_takeaway': summary.key_takeaway,
                            'financial_details': [
                                {
                                    'amount': fd.amount,
                                    'currency': fd.currency,
                                    'context': fd.context
                                }
                                for fd in summary.financial_details
                            ],
                            'key_entities': [
                                {
                                    'entity_type': ke.entity_type,
                                    'name': ke.name,
                                    'context': ke.context
                                }
                                for ke in summary.key_entities
                            ]
                        }

                        results.append(result)

                        print(f"      ✅ Success! Priority: {summary.priority_score}/10")
                        print(f"      📝 {summary.summary[:80]}...")
                    else:
                        print(f"      ⚠️  Priority too low: {summary.priority_score}/10 (threshold: {min_priority_score})")
                else:
                    print(f"      ❌ Failed to generate summary")
                    failed_count += 1

            except Exception as e:
                print(f"      ❌ Error: {e}")
                failed_count += 1

    # Sort results by priority (highest first)
    results.sort(key=lambda x: x['priority_score'], reverse=True)

    # Step 4: Generate outputs
    print("\n" + "=" * 80)
    print("📊 PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total Processed: {processed_count}")
    print(f"Successful: {len(results)}")
    print(f"Failed: {failed_count}")
    print(f"Success Rate: {(len(results)/processed_count*100):.1f}%")

    # Create output object
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'statistics': {
            'total_announcements': len(all_announcements),
            'healthcare_announcements': total_healthcare,
            'companies': len(grouped),
            'processed': processed_count,
            'successful': len(results),
            'failed': failed_count
        },
        'results': results
    }

    # Save outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if output_json:
        json_filename = f"newsletter_{timestamp}.json"
        json_path = os.path.join('output', json_filename)
        os.makedirs('output', exist_ok=True)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 JSON saved: {json_path}")

    if output_markdown:
        md_filename = f"newsletter_{timestamp}.md"
        md_path = os.path.join('output', md_filename)
        os.makedirs('output', exist_ok=True)

        markdown_content = generate_markdown_newsletter(output_data)

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"📄 Markdown saved: {md_path}")

    return output_data


def generate_markdown_newsletter(data: Dict) -> str:
    """Generate clean markdown newsletter matching client's format"""

    lines = []

    # Header
    lines.append("# ASX Healthcare Daily Newsletter")
    lines.append(f"\n**Date:** {data['date']}")
    lines.append(f"**Generated:** {data['generated_at']}")
    lines.append("\n---\n")

    # Statistics
    stats = data['statistics']
    lines.append("## Summary")
    lines.append(f"- **Total ASX Announcements:** {stats['total_announcements']}")
    lines.append(f"- **Healthcare Sector:** {stats['healthcare_announcements']} announcements")
    lines.append(f"- **Companies Covered:** {stats['companies']}")
    lines.append(f"- **Processed Successfully:** {stats['successful']}/{stats['processed']}")
    lines.append("\n---\n")

    # Group results by priority
    high_priority = [r for r in data['results'] if r['priority_score'] >= 7]
    medium_priority = [r for r in data['results'] if 4 <= r['priority_score'] < 7]
    low_priority = [r for r in data['results'] if r['priority_score'] < 4]

    # High Priority Stories
    if high_priority:
        lines.append("## 🔥 Top Stories (Priority 7-10)")
        lines.append("")

        for i, result in enumerate(high_priority, 1):
            lines.append(f"### {i}. {result['summary']}")
            lines.append(f"   [Announcement: {result['company_code']}]({result['pdf_url']})")
            lines.append("")

    # Medium Priority
    if medium_priority:
        lines.append("## 📰 Notable Announcements (Priority 4-6)")
        lines.append("")

        for result in medium_priority:
            lines.append(f"- {result['summary']}")
            lines.append(f"  [Announcement: {result['company_code']}]({result['pdf_url']})")
            lines.append("")

    # Low Priority (optional, can be commented out)
    if low_priority and False:  # Set to True to include low priority
        lines.append("## 📋 Other Announcements (Priority 1-3)")
        lines.append("")

        for result in low_priority:
            lines.append(f"- {result['summary']}")
            lines.append(f"  [Announcement: {result['company_code']}]({result['pdf_url']})")
            lines.append("")

    # Footer
    lines.append("\n---\n")
    lines.append("*Generated with ASX Healthcare Newsletter Automation*")

    return "\n".join(lines)


def main():
    """Run the newsletter generator"""

    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY not found in .env file!")
        print("Please add: OPENAI_API_KEY=your-key-here")
        return

    # Get user preferences
    print("\n🔧 Newsletter Generation Settings")
    print("=" * 80)

    try:
        max_per_company = int(input("Max announcements per company (default: 3): ").strip() or "3")
        min_priority = int(input("Minimum priority score 1-10 (default: 1): ").strip() or "1")
    except ValueError:
        max_per_company = 3
        min_priority = 1

    print(f"\n✅ Settings:")
    print(f"   Max per company: {max_per_company}")
    print(f"   Min priority: {min_priority}/10")
    print(f"   Output formats: JSON + Markdown")
    print("")

    # Run workflow
    result = generate_newsletter(
        max_announcements_per_company=max_per_company,
        min_priority_score=min_priority,
        output_json=True,
        output_markdown=True
    )

    if result.get('error'):
        print(f"\n❌ Newsletter generation failed: {result['error']}")
    else:
        print("\n" + "=" * 80)
        print("✅ NEWSLETTER GENERATION COMPLETE!")
        print("=" * 80)
        print(f"\n📊 Results:")
        print(f"   • {result['statistics']['successful']} summaries generated")
        print(f"   • Saved to output/ directory")
        print(f"   • Check JSON for structured data")
        print(f"   • Check Markdown for formatted newsletter")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
