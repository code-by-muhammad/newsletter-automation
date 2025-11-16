from dotenv import load_dotenv
from agency_swarm import Agency
from NewsletterAgent import NewsletterAgent

import asyncio

load_dotenv()

# Initialize the NewsletterAgent
newsletter_agent = NewsletterAgent()

# do not remove this method, it is used in the main.py file to deploy the agency (it has to be a method)
def create_agency(load_threads_callback=None):
    """
    Creates the ASX Healthcare Newsletter Agency.

    The agency consists of a single NewsletterAgent that:
    - Takes user requests for newsletter generation
    - Calls GenerateNewsletterTool to process ASX healthcare announcements
    - Returns formatted newsletter with AI-generated summaries
    """
    agency = Agency(
        newsletter_agent,
        name="ASX Healthcare Newsletter Agency",
        load_threads_callback=load_threads_callback,
    )

    return agency

if __name__ == "__main__":
    agency = create_agency()

    # test 1 message
    # async def main():
    #     response = await agency.get_response("Generate newsletter for 3 PDFs")
    #     print(response)
    # asyncio.run(main())

    # run in terminal
    agency.terminal_demo()