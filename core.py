import csv
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import requests
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PUBMED_API_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Academic indicators to filter out
ACADEMIC_INDICATORS = {
    "university", "college", "institute", "school", 
    "hospital", "lab", "laboratory", "academy", 
    "government", "ministry", "clinic"
}

# Common pharmaceutical/biotech company names (partial matches)
PHARMA_BIOTECH_KEYWORDS = {
    "pharma", "biotech", "genentech", "novartis", "pfizer", 
    "roche", "sanofi", "merck", "gilead", "astrazeneca",
    "bristol", "johnson", "johnson & johnson", "eli lilly",
    "abbvie", "amgen", "biogen", "moderna", "bayer"
}

@dataclass
class PaperRecord:
    pubmed_id: str
    title: str
    publication_date: str
    non_academic_authors: List[str]
    company_affiliations: List[str]
    corresponding_author_email: Optional[str]

def is_pharma_biotech_affiliation(affiliation: str) -> bool:
    """Check if an affiliation string suggests pharmaceutical/biotech company."""
    if not affiliation:
        return False
    
    affiliation_lower = affiliation.lower()
    return any(keyword in affiliation_lower for keyword in PHARMA_BIOTECH_KEYWORDS)

def is_academic_affiliation(affiliation: str) -> bool:
    """Check if an affiliation string suggests academic institution."""
    if not affiliation:
        return False
    
    affiliation_lower = affiliation.lower()
    return any(indicator in affiliation_lower for indicator in ACADEMIC_INDICATORS)

def fetch_pubmed_ids(query: str, max_results: int = 100) -> List[str]:
    """Fetch PubMed IDs based on a search query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    }
    
    try:
        response = requests.get(PUBMED_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except RequestException as e:
        logger.error(f"Error fetching PubMed IDs: {e}")
        return []
    except ValueError as e:
        logger.error(f"Error parsing PubMed response: {e}")
        return []

def fetch_paper_details(pubmed_id: str) -> Optional[Dict]:
    """Fetch detailed information for a single paper."""
    params = {
        "db": "pubmed",
        "id": pubmed_id,
        "retmode": "xml"
    }
    
    try:
        response = requests.get(PUBMED_FETCH_URL, params=params)
        response.raise_for_status()
        return response.text  # Return XML as text for parsing
    except RequestException as e:
        logger.error(f"Error fetching details for PubMed ID {pubmed_id}: {e}")
        return None

def parse_paper_details(xml_content: str) -> Optional[PaperRecord]:
    """Parse XML content to extract paper details."""
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(xml_content, "xml")
        
        # Extract basic information
        pubmed_id = soup.find("PMID").text if soup.find("PMID") else None
        title = soup.find("ArticleTitle").text if soup.find("ArticleTitle") else "No title"
        
        # Extract publication date
        pub_date = soup.find("PubDate")
        if pub_date:
            year = pub_date.find("Year").text if pub_date.find("Year") else "Unknown"
            month = pub_date.find("Month").text if pub_date.find("Month") else ""
            day = pub_date.find("Day").text if pub_date.find("Day") else ""
            publication_date = f"{year}-{month}-{day}"
        else:
            publication_date = "Unknown"
        
        # Process authors and affiliations
        non_academic_authors = []
        company_affiliations = []
        corresponding_author_email = None
        
        authors = soup.find_all("Author")
        for author in authors:
            if author.find("CollectiveName"):  # Skip collective names
                continue
                
            last_name = author.find("LastName").text if author.find("LastName") else ""
            fore_name = author.find("ForeName").text if author.find("ForeName") else ""
            author_name = f"{fore_name} {last_name}".strip()
            
            # Check for corresponding author email
            if not corresponding_author_email:
                email = author.find("Email")
                if email:
                    corresponding_author_email = email.text
            
            # Process affiliations
            affiliations = author.find_all("Affiliation")
            for affil in affiliations:
                affiliation_text = affil.text.strip()
                
                # Check if affiliation is from pharma/biotech
                if is_pharma_biotech_affiliation(affiliation_text):
                    if author_name and author_name not in non_academic_authors:
                        non_academic_authors.append(author_name)
                    
                    # Add company name if not already listed
                    company_name = extract_company_name(affiliation_text)
                    if company_name and company_name not in company_affiliations:
                        company_affiliations.append(company_name)
                
                # Also check for non-academic authors even if not explicitly pharma/biotech
                elif not is_academic_affiliation(affiliation_text):
                    if author_name and author_name not in non_academic_authors:
                        non_academic_authors.append(author_name)
        
        # Only include if there are company affiliations
        if company_affiliations:
            return PaperRecord(
                pubmed_id=pubmed_id,
                title=title,
                publication_date=publication_date,
                non_academic_authors=non_academic_authors,
                company_affiliations=company_affiliations,
                corresponding_author_email=corresponding_author_email
            )
        return None
    
    except Exception as e:
        logger.error(f"Error parsing paper details: {e}")
        return None

def extract_company_name(affiliation: str) -> str:
    """Extract company name from affiliation string."""
    # This is a simple heuristic - could be enhanced
    for keyword in PHARMA_BIOTECH_KEYWORDS:
        if keyword in affiliation.lower():
            # Try to find the full company name
            words = affiliation.split()
            for i, word in enumerate(words):
                if keyword in word.lower():
                    # Return the next few words as company name
                    return " ".join(words[i:i+3]).strip(" ,;")
    return affiliation.split(",")[0].strip()

def search_papers(query: str, max_results: int = 100) -> List[PaperRecord]:
    """Search PubMed for papers matching query with pharma/biotech affiliations."""
    pubmed_ids = fetch_pubmed_ids(query, max_results)
    if not pubmed_ids:
        logger.warning("No papers found for the given query")
        return []
    
    papers = []
    for pid in pubmed_ids:
        xml_content = fetch_paper_details(pid)
        if xml_content:
            paper = parse_paper_details(xml_content)
            if paper:
                papers.append(paper)
    
    return papers

def save_to_csv(papers: List[PaperRecord], filename: str) -> None:
    """Save paper records to a CSV file."""
    if not papers:
        logger.warning("No papers to save")
        return
    
    try:
        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow([
                "PubmedID", "Title", "Publication Date",
                "Non-academic Author(s)", "Company Affiliation(s)",
                "Corresponding Author Email"
            ])
            
            # Write data
            for paper in papers:
                writer.writerow([
                    paper.pubmed_id,
                    paper.title,
                    paper.publication_date,
                    "; ".join(paper.non_academic_authors),
                    "; ".join(paper.company_affiliations),
                    paper.corresponding_author_email or "Not available"
                ])
        logger.info(f"Successfully saved results to {filename}")
    except IOError as e:
        logger.error(f"Error writing to CSV file: {e}")

def print_to_console(papers: List[PaperRecord]) -> None:
    """Print paper records to console in a readable format."""
    if not papers:
        print("No papers found with the specified criteria")
        return
    
    for i, paper in enumerate(papers, 1):
        print(f"\nPaper {i}:")
        print(f"PubMed ID: {paper.pubmed_id}")
        print(f"Title: {paper.title}")
        print(f"Publication Date: {paper.publication_date}")
        print("Non-academic Authors:", "; ".join(paper.non_academic_authors) or "None")
        print("Company Affiliations:", "; ".join(paper.company_affiliations))
        print("Corresponding Author Email:", paper.corresponding_author_email or "Not available")
    print(f"\nTotal papers found: {len(papers)}")
