"""Backfill latitude/longitude for all PPs."""

import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.models import PP, create_db_engine, create_session
from scraper import repository
from pipeline.geocode import geocode_pp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    engine = create_db_engine()
    session = create_session(engine)

    pps = session.query(PP).order_by(PP.pp_number).all()
    logger.info("Processing %d PPs", len(pps))

    by_address = 0
    by_lga = 0
    failed = 0

    for pp in pps:
        if pp.latitude is not None:
            logger.info("  %s: already geocoded (%.4f, %.4f) [%s]", pp.pp_number, pp.latitude, pp.longitude, pp.geo_source)
            continue

        result = geocode_pp(session, pp)

        if result:
            lat, lng, source = result
            repository.update_pp_geocode(session, pp.pp_number, lat, lng, source)
            logger.info("  %s: %.4f, %.4f [%s]", pp.pp_number, lat, lng, source)
            if source == "address":
                by_address += 1
            else:
                by_lga += 1
        else:
            failed += 1
            logger.warning("  %s: FAILED to geocode", pp.pp_number)

        time.sleep(1.1)  # Nominatim rate limit

    total = by_address + by_lga
    logger.info("\nResults: %d geocoded (%d by address, %d by LGA centroid), %d failed",
                total, by_address, by_lga, failed)

    session.close()


if __name__ == "__main__":
    main()
