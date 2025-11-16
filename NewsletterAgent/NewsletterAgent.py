#!/usr/bin/env python3
"""
NewsletterAgent
Processes ASX healthcare announcements and generates newsletter summaries for Jason Segal.
"""

from agency_swarm import Agent
from .tools.GenerateNewsletterTool import GenerateNewsletterTool


class NewsletterAgent(Agent):
    """
    ASX Healthcare Newsletter Agent

    This agent processes ASX healthcare sector announcements and generates
    concise, information-dense summaries following Jason's newsletter style.

    Capabilities:
    - Fetches ASX announcements from QuoteAPI
    - Filters for healthcare sector (175+ stocks)
    - Processes PDF announcements with text extraction
    - Generates AI-powered summaries (30 words max)
    - Returns formatted newsletter sorted by priority
    """

    def __init__(self):
        super().__init__(
            name="NewsletterAgent",
            description=(
                "Generates ASX healthcare newsletter by processing PDF announcements. "
                "Fetches data from QuoteAPI, extracts text from PDFs, and creates concise "
                "30-word summaries. "
            ),
            instructions="./instructions.md",
            tools=[GenerateNewsletterTool],
        )


if __name__ == "__main__":
    # Test the agent
    agent = NewsletterAgent()
    print(f"✅ {agent.name} initialized successfully")
    print(f"📝 Description: {agent.description}")
    print(f"🔧 Tools: {[tool.__name__ for tool in agent.tools]}")
