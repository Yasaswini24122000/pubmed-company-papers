import argparse
import logging
from typing import Optional
from pathlib import Path
from .core import search_papers, save_to_csv, print_to_console

def setup_logging(debug: bool) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

def validate_output_file(filename: str) -> bool:
    """Check if the output file can be created."""
    try:
        path = Path(filename)
        if path.exists():
            return path.is_file() and os.access(path, os.W_OK)
        # Check if directory is writable
        return path.parent.exists() and os.access(path.parent, os.W_OK)
    except Exception:
        return False

def main():
    """Command-line interface for the PubMed paper fetcher."""
    parser = argparse.ArgumentParser(
        description="Fetch PubMed papers with authors affiliated with pharmaceutical/biotech companies."
    )
    parser.add_argument(
        "query",
        type=str,
        help="PubMed search query to filter papers"
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="Filename to save results as CSV (default: print to console)"
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "-m", "--max",
        type=int,
        default=100,
        help="Maximum number of papers to fetch (default: 100)"
    )
    
    args = parser.parse_args()
    setup_logging(args.debug)
    
    if args.file and not validate_output_file(args.file):
        logging.error(f"Cannot write to output file: {args.file}")
        return
    
    try:
        papers = search_papers(args.query, args.max)
        
        if args.file:
            save_to_csv(papers, args.file)
        else:
            print_to_console(papers)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        if args.debug:
            logging.exception("Full error traceback:")

if __name__ == "__main__":
    main()
